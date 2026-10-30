"""Unit tests for bin/logic_safe_regex.py — guarded object assignment regex matching."""

import time

import pandas as pd
import pytest

from bin.logic_safe_regex import (
    MAX_NAME_LENGTH,
    MAX_PATTERN_LENGTH,
    UnsafeRegexError,
    is_safe_object_assignment_regex,
    match_object_names,
    validate_object_assignment_regex,
)


class TestValidateObjectAssignmentRegex:
    @pytest.mark.parametrize("pattern", [
        "PUMP_101",
        "PUMP_([^.]*?)",
        "([^.]*?)_VALVE_([^.]*?)",
        "TIC_\\d{3}",
        "(ABC)?_X",
        "(TIC|FIC)_101",
        "[A-Z]+_[0-9]+",
    ])
    def test_accepts_patterns_built_by_the_assign_type_view(self, pattern):
        validate_object_assignment_regex(pattern)
        assert is_safe_object_assignment_regex(pattern)

    @pytest.mark.parametrize("pattern", [
        "(a+)+$",
        "(\\w+\\s?)+$",
        "(a*)*b",
        "((ab)*c)+",
        "(a{1,5}){1,5}",
        "(a|aa)+$",
        "(ab|a)*c",
        "(?:x+y?)+",
        "(?=(a+)+)b",
        "(a)\\1",
        "(",
        "a" * (MAX_PATTERN_LENGTH + 1),
        None,
        42,
    ])
    def test_rejects_unsafe_or_invalid_patterns(self, pattern):
        with pytest.raises(UnsafeRegexError):
            validate_object_assignment_regex(pattern)
        assert not is_safe_object_assignment_regex(pattern)


class TestMatchObjectNames:
    def test_matches_like_str_match_for_safe_patterns(self):
        names = pd.Series(["PUMP_101", "PUMP_102", "VALVE_1", "XPUMP_1"], index=[3, 7, 9, 11])
        pattern = "PUMP_([^.]*?)"
        mask = match_object_names(names, pattern)
        assert mask.tolist() == names.str.match(pattern).tolist()
        assert list(mask.index) == [3, 7, 9, 11]

    def test_unsafe_pattern_matches_nothing_and_returns_promptly(self):
        names = pd.Series(["a" * 40 + "!"] * 200)
        start = time.monotonic()
        mask = match_object_names(names, "(a+)+$")
        assert time.monotonic() - start < 1
        assert not mask.any()

    def test_overlong_and_non_string_names_never_match(self):
        names = pd.Series(["A" * (MAX_NAME_LENGTH + 1), None, float("nan"), "A"])
        assert match_object_names(names, "A+").tolist() == [False, False, False, True]

    def test_time_budget_skips_the_pattern(self):
        names = pd.Series(["PUMP_1"] * 10)
        assert not match_object_names(names, "PUMP_1", time_budget=-1).any()

    def test_polynomial_backtracking_is_cut_off_by_the_time_budget(self):
        pattern = "a*" * 10 + "b"
        validate_object_assignment_regex(pattern)
        names = pd.Series(["PUMP_1", "a" * MAX_NAME_LENGTH])
        start = time.monotonic()
        mask = match_object_names(names, pattern, time_budget=0.5)
        assert time.monotonic() - start < 3
        assert not mask.any()

    def test_empty_series(self):
        mask = match_object_names(pd.Series([], dtype=object), "PUMP")
        assert mask.empty
