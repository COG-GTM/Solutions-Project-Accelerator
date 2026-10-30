"""Guarded matching for regex patterns read back from project data.

Linked-text templates keep their ``regex_string`` in the project database, and a
project can be imported from an untrusted archive, so a stored pattern must not
be able to hang the UI with catastrophic backtracking. Patterns are validated
(length cap, no backreferences, no repeated group that itself repeats or
alternates) and then matched with the ``regex`` engine under a timeout. A
pattern that fails either check is remembered and never run again.
"""
import logging
import re

import regex

try:
    from re import _constants as _sre_constants
    from re import _parser as _sre_parse
except ImportError:  # Python < 3.11
    import sre_constants as _sre_constants
    import sre_parse as _sre_parse


MAX_PATTERN_LENGTH = 4096
MATCH_TIMEOUT_SECONDS = 0.5
_MAX_REJECTED_PATTERNS = 1024

_REPEAT_OPS = {_sre_constants.MAX_REPEAT, _sre_constants.MIN_REPEAT}
if hasattr(_sre_constants, 'POSSESSIVE_REPEAT'):
    _REPEAT_OPS.add(_sre_constants.POSSESSIVE_REPEAT)
_BACKREFERENCE_OPS = {_sre_constants.GROUPREF, _sre_constants.GROUPREF_EXISTS}

_rejected_patterns = {}


class UnsafeRegexError(ValueError):
    pass


def _subpatterns(op, av):
    if op in _REPEAT_OPS:
        return [av[2]]
    if op == _sre_constants.SUBPATTERN:
        return [av[3]]
    if op == _sre_constants.BRANCH:
        return list(av[1])
    if op in (_sre_constants.ASSERT, _sre_constants.ASSERT_NOT):
        return [av[1]]
    if op == getattr(_sre_constants, 'ATOMIC_GROUP', None):
        return [av]
    if op == _sre_constants.GROUPREF_EXISTS:
        return [p for p in av[1:] if p is not None]
    return []


def _can_backtrack(parsed):
    """True when ``parsed`` holds a variable-width repeat or an alternation."""
    for op, av in parsed:
        if op in _REPEAT_OPS and av[0] != av[1]:
            return True
        if op == _sre_constants.BRANCH:
            return True
        if any(_can_backtrack(sub) for sub in _subpatterns(op, av)):
            return True
    return False


def _check_tree(parsed):
    for op, av in parsed:
        if op in _BACKREFERENCE_OPS:
            raise UnsafeRegexError('backreferences are not allowed')
        if op in _REPEAT_OPS and av[1] > 1 and _can_backtrack(av[2]):
            raise UnsafeRegexError('nested quantifiers are not allowed')
        for sub in _subpatterns(op, av):
            _check_tree(sub)


def validate_pattern(pattern):
    """Raise ``UnsafeRegexError`` unless ``pattern`` is safe to run on page text."""
    if not isinstance(pattern, str):
        raise UnsafeRegexError('pattern must be a string')
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise UnsafeRegexError(f'pattern is longer than {MAX_PATTERN_LENGTH} characters')
    try:
        parsed = _sre_parse.parse(pattern)
    except (re.error, RecursionError, OverflowError) as error:
        raise UnsafeRegexError(f'invalid pattern: {error}') from error
    _check_tree(parsed)
    return pattern


def _reject(pattern, reason):
    if len(_rejected_patterns) >= _MAX_REJECTED_PATTERNS:
        _rejected_patterns.clear()
    _rejected_patterns[pattern] = reason
    logging.warning('Skipping stored regex %.80r: %s', pattern, reason)


def _compile(pattern):
    key = pattern if isinstance(pattern, str) else repr(pattern)
    if key in _rejected_patterns:
        return None
    try:
        validate_pattern(pattern)
        return regex.compile(pattern)
    except (UnsafeRegexError, regex.error) as error:
        _reject(key, str(error))
        return None


def is_safe_pattern(pattern):
    return _compile(pattern) is not None


def _run(pattern, method, string, default):
    compiled = _compile(pattern)
    if compiled is None:
        return default
    try:
        result = getattr(compiled, method)(string, timeout=MATCH_TIMEOUT_SECONDS)
        return list(result) if method == 'finditer' else result
    except TimeoutError:
        _reject(pattern, f'matching took longer than {MATCH_TIMEOUT_SECONDS}s')
        return default


def search(pattern, string):
    """``re.search`` for stored patterns; ``None`` if the pattern is rejected."""
    return _run(pattern, 'search', string, None)


def finditer(pattern, string):
    """All matches as a list; empty if the pattern is rejected."""
    return _run(pattern, 'finditer', string, [])


def findall(pattern, string):
    """``re.findall`` for stored patterns; empty if the pattern is rejected."""
    return _run(pattern, 'findall', string, [])
