"""Stored linked-text patterns must not be able to hang page processing (ReDoS)."""

import time

import pytest

from bin import logic_safe_regex as safe_regex
from bin.logic_linked_texts import (
    GivenTextLink,
    LinkedText,
    Linked_Texts,
    TargetTextType,
)


@pytest.fixture(autouse=True)
def _fresh_rejections():
    safe_regex._rejected_patterns.clear()
    safe_regex._timed_out_inputs.clear()
    safe_regex._timeout_counts.clear()
    yield
    safe_regex._rejected_patterns.clear()
    safe_regex._timed_out_inputs.clear()
    safe_regex._timeout_counts.clear()


def build_regex_for(given_text_string, key_and_ignore_indexes, text_type, in_table=False):
    linked_texts = object.__new__(Linked_Texts)
    given_text = GivenTextLink(linked=True
                               ,text=given_text_string
                               ,key_and_ignore_indexes=list(key_and_ignore_indexes)
                               ,in_table=in_table)
    linked_text = LinkedText(text='LIC2001.Sts_LoDev'
                             ,text_type=text_type
                             ,given_text={'id': given_text})
    linked_texts._Linked_Texts__build_regex_string(linked_text, 'id', key_and_ignore_indexes[:1])
    return linked_text.given_text['id'].regex_string


class TestValidatePattern:

    @pytest.mark.parametrize('pattern', [
        r'(a+)+$',
        r'(a*)*b',
        r'(?:a+){2,}',
        r'(a|aa)*$',
        r'(\w+\s?)+$',
        r'((ab)*c)*',
        r'(?=(a+)+)',
    ])
    def test_rejects_nested_quantifiers(self, pattern):
        with pytest.raises(safe_regex.UnsafeRegexError, match='nested quantifiers'):
            safe_regex.validate_pattern(pattern)

    @pytest.mark.parametrize('pattern', [r'(a)\1', r'(?P<x>a)(?P=x)', r'(a)?(?(1)b|c)'])
    def test_rejects_backreferences(self, pattern):
        with pytest.raises(safe_regex.UnsafeRegexError, match='backreferences'):
            safe_regex.validate_pattern(pattern)

    def test_rejects_overlong_pattern(self):
        with pytest.raises(safe_regex.UnsafeRegexError, match='longer than'):
            safe_regex.validate_pattern('a' * (safe_regex.MAX_PATTERN_LENGTH + 1))

    @pytest.mark.parametrize('pattern', ['(unclosed', None, 42])
    def test_rejects_invalid_pattern(self, pattern):
        with pytest.raises(safe_regex.UnsafeRegexError):
            safe_regex.validate_pattern(pattern)

    @pytest.mark.parametrize('pattern', [
        r'(\d+)',
        r'(\d+(\.\d+)?)',
        r'([a-zA-Z0-9_]*)',
        r'(a|b)*',
        r'(ab){3}',
        r'Tank level LIC\-2001 > Lo',
    ])
    def test_accepts_linear_patterns(self, pattern):
        assert safe_regex.validate_pattern(pattern) == pattern


class TestGeneratedTemplatesStayValid:

    @pytest.mark.parametrize('text_type', list(TargetTextType))
    @pytest.mark.parametrize('in_table', [False, True])
    def test_built_regex_strings_pass_validation(self, text_type, in_table):
        text = 'Suction tank level LIC-2001 > Lo, setpoint 12.5 bar'
        pattern = build_regex_for(text, [[19, 27], [34, 42]], text_type, in_table)
        assert safe_regex.is_safe_pattern(pattern), pattern
        if text_type == TargetTextType.STRING:
            assert safe_regex.search(pattern, text) is not None


class TestGuardedMatching:

    def test_redos_pattern_returns_promptly_and_is_remembered(self, caplog):
        page = 'a' * 50000 + '!'
        started = time.monotonic()
        assert safe_regex.search(r'(a+)+$', page) is None
        assert safe_regex.finditer(r'(a+)+$', page) == []
        assert safe_regex.findall(r'(a+)+$', page) == []
        assert time.monotonic() - started < 1
        assert r'(a+)+$' in safe_regex._rejected_patterns
        assert sum('Skipping stored regex' in r.message for r in caplog.records) == 1

    def test_timeout_is_scoped_to_the_slow_input(self, monkeypatch):
        calls = []

        class SlowOnLongInput:
            def search(self, string, timeout):
                calls.append(string)
                if len(string) > 100:
                    raise TimeoutError('regex timed out')
                return 'match'

        monkeypatch.setattr(safe_regex.regex, 'compile', lambda pattern: SlowOnLongInput())
        long_page = '1' * 1000
        assert safe_regex.search(r'(\d*)x', long_page) is None
        assert safe_regex.search(r'(\d*)x', long_page) is None
        assert calls == [long_page]
        assert safe_regex.search(r'(\d*)x', '1x') == 'match'
        assert r'(\d*)x' not in safe_regex._rejected_patterns

    def test_timeout_in_one_method_does_not_skip_another(self, monkeypatch):
        class SlowEnumeration:
            def finditer(self, string, timeout):
                raise TimeoutError('regex timed out')

            def search(self, string, timeout):
                return 'first match'

        monkeypatch.setattr(safe_regex.regex, 'compile', lambda pattern: SlowEnumeration())
        page = 'a' * 1000
        assert safe_regex.finditer('a', page) == []
        assert safe_regex.search('a', page) == 'first match'

    def test_pattern_rejected_after_repeated_timeouts(self, monkeypatch):
        calls = []

        class AlwaysSlow:
            def search(self, string, timeout):
                calls.append(string)
                raise TimeoutError('regex timed out')

        monkeypatch.setattr(safe_regex.regex, 'compile', lambda pattern: AlwaysSlow())
        cells = [f'cell {i}' for i in range(10)]
        for cell in cells:
            assert safe_regex.search(r'(\d*)x', cell) is None
        assert calls == cells[:safe_regex.MAX_TIMEOUTS_PER_PATTERN]
        assert r'(\d*)x' in safe_regex._rejected_patterns
        assert not safe_regex.is_safe_pattern(r'(\d*)x')

    def test_matches_like_re_for_safe_patterns(self):
        text = 'Pump P-101 runs at 12.5 bar; Pump P-102 runs at 7 bar'
        pattern = r'Pump P\-(\d+) runs at (\d+(\.\d+)?)'
        assert safe_regex.search(pattern, text).group(1) == '101'
        assert [m.group(2) for m in safe_regex.finditer(pattern, text)] == ['12.5', '7']
        assert safe_regex.findall(pattern, text) == [('101', '12.5', '.5'), ('102', '7', '')]


class TestLinkedTextsUseGuardedMatching:

    def test_get_regex_group_skips_redos_pattern(self):
        linked_texts = object.__new__(Linked_Texts)
        get_group = linked_texts._Linked_Texts__get_regex_group
        assert get_group('a' * 50000 + '!', r'(a+)+$', [0, 1]) is None
        assert get_group('Level LIC-2001 > Lo', r'Level ([^.]*?) > Lo', [6, 14]) == 1


class TestPreviewHighlightPattern:

    def test_full_matches_for_pattern_at_length_cap(self):
        pattern = 'a' * safe_regex.MAX_PATTERN_LENGTH
        page = 'x' + pattern + 'y'
        assert [m.group(0) for m in safe_regex.finditer(pattern, page)] == [pattern]
