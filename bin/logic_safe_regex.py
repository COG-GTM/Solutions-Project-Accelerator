"""Guarded matching for object assignment regexes stored in the project database.

Patterns in the ``object_assignment_regexes`` table come from the project file, which
may have been imported from an untrusted archive. Python's ``re`` has no timeout, so a
pattern such as ``(a+)+$`` run over long names can backtrack for minutes. Patterns are
therefore checked before use (length cap, compile check, no nested or alternating
quantifiers, no backreferences) and names longer than a PLC tag can be are skipped.
"""

import logging
import re
import time

import pandas as pd

try:
    import re._parser as _sre_parse
except ImportError:  # Python < 3.11
    import sre_parse as _sre_parse

logger = logging.getLogger(__name__)

MAX_PATTERN_LENGTH = 512
MAX_NAME_LENGTH = 256
MATCH_TIME_BUDGET_SECONDS = 2.0

_REPEAT_OPS = {
    getattr(_sre_parse, name)
    for name in ('MAX_REPEAT', 'MIN_REPEAT', 'POSSESSIVE_REPEAT')
    if hasattr(_sre_parse, name)
}
_GROUPREF_OPS = {
    getattr(_sre_parse, name)
    for name in ('GROUPREF', 'GROUPREF_IGNORE', 'GROUPREF_LOC_IGNORE', 'GROUPREF_UNI_IGNORE', 'GROUPREF_EXISTS')
    if hasattr(_sre_parse, name)
}


class UnsafeRegexError(ValueError):
    pass


def _children(op, av):
    if op in _REPEAT_OPS:
        return [av[2]]
    if op == _sre_parse.SUBPATTERN:
        return [av[-1]]
    if op == _sre_parse.BRANCH:
        return list(av[1])
    if op in (_sre_parse.ASSERT, _sre_parse.ASSERT_NOT):
        return [av[1]]
    if op == getattr(_sre_parse, 'ATOMIC_GROUP', object()):
        return [av]
    return []


def _check(subpattern, inside_repeat):
    for op, av in subpattern:
        if op in _GROUPREF_OPS:
            raise UnsafeRegexError('backreferences are not allowed')
        if op in _REPEAT_OPS:
            repeats = av[1] > 1
            if repeats and inside_repeat:
                raise UnsafeRegexError('nested quantifiers are not allowed')
            _check(av[2], inside_repeat or repeats)
            continue
        if op == _sre_parse.BRANCH and inside_repeat:
            raise UnsafeRegexError('alternation inside a quantified group is not allowed')
        for child in _children(op, av):
            _check(child, inside_repeat)


def validate_object_assignment_regex(pattern):
    """Raise ``UnsafeRegexError`` if ``pattern`` is not safe to run over object names."""
    if not isinstance(pattern, str):
        raise UnsafeRegexError('pattern must be a string')
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise UnsafeRegexError('pattern is longer than %d characters' % MAX_PATTERN_LENGTH)
    try:
        parsed = _sre_parse.parse(pattern)
    except Exception as error:
        raise UnsafeRegexError('pattern does not compile: %s' % error) from error
    _check(parsed, False)


def is_safe_object_assignment_regex(pattern):
    try:
        validate_object_assignment_regex(pattern)
    except UnsafeRegexError:
        return False
    return True


def match_object_names(names, pattern, time_budget=MATCH_TIME_BUDGET_SECONDS):
    """Boolean mask of ``names`` that ``re.match`` ``pattern``; all False if the pattern is unsafe.

    Names longer than ``MAX_NAME_LENGTH`` never match. If matching exceeds ``time_budget``
    seconds the remaining names are left unmatched.
    """
    matches = [False] * len(names)
    try:
        validate_object_assignment_regex(pattern)
    except UnsafeRegexError as error:
        logger.warning('Skipping object assignment regex %r: %s', str(pattern)[:80], error)
        return pd.Series(matches, index=names.index, dtype=bool)

    compiled = re.compile(pattern)
    deadline = time.monotonic() + time_budget
    for position, name in enumerate(names):
        if not isinstance(name, str) or len(name) > MAX_NAME_LENGTH:
            continue
        if time.monotonic() > deadline:
            logger.warning('Object assignment regex %r exceeded its time budget; remaining names skipped',
                           pattern[:80])
            break
        matches[position] = compiled.match(name) is not None
    return pd.Series(matches, index=names.index, dtype=bool)
