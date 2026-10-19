"""Unit tests for the pure helpers in bin/logic_text_document_llm_processors.py."""

import pytest

from bin.logic_text_document_llm_processors import (
    TAGNAME_REGEX,
    _normalize_annotation_field,
    annotation_dedupe_key,
    is_bbox_within_bbox,
    is_rectangle_overlap,
    match_substring_indexes,
    text_indent_remove,
)


class TestNormalizeAnnotationField:
    @pytest.mark.parametrize("raw,expected", [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("TIC-401", "tic-401"),
        ("  TIC-401  ", "tic-401"),
        ("Setpoint", "setpoint"),
        (42, "42"),
        (3.5, "3.5"),
        (True, "true"),
    ])
    def test_normalisation(self, raw, expected):
        assert _normalize_annotation_field(raw) == expected


class TestAnnotationDedupeKey:
    def test_case_and_whitespace_variants_collapse(self):
        a = annotation_dedupe_key("TIC-401", "Setpoint", "200")
        b = annotation_dedupe_key("  tic-401 ", "SETPOINT", " 200  ")
        assert a == b

    def test_none_and_empty_are_the_same_key(self):
        assert annotation_dedupe_key("TIC-401", None, None) == annotation_dedupe_key("TIC-401", "", "")

    @pytest.mark.parametrize("args", [
        ("FIT-205", "Setpoint", "200"),
        ("TIC-401", "HiHi", "200"),
        ("TIC-401", "Setpoint", "201"),
    ])
    def test_different_triples_produce_different_keys(self, args):
        assert annotation_dedupe_key("TIC-401", "Setpoint", "200") != annotation_dedupe_key(*args)

    def test_key_is_hashable_so_it_can_back_a_set(self):
        seen = {
            annotation_dedupe_key("TIC-401", "Setpoint", "200"),
            annotation_dedupe_key("tic-401", "setpoint", "200"),
        }
        assert len(seen) == 1

    def test_returns_a_three_tuple(self):
        assert annotation_dedupe_key("a", "b", "c") == ("a", "b", "c")


class TestMatchSubstringIndexes:
    def test_identical_strings_match_completely(self):
        assert match_substring_indexes("ABC", "ABC") == ([[0, 2]], [[0, 2]])

    def test_finds_longest_common_run(self):
        # "WORLD" is the longest shared run.
        assert match_substring_indexes("HELLO WORLD", "WORLD PEACE") == ([[6, 10]], [[0, 4]])

    def test_returns_inclusive_end_indices(self):
        ranges1, _ = match_substring_indexes("AB", "ABC")
        assert ranges1 == [[0, 1]]

    @pytest.mark.parametrize("a,b", [
        ("ABC", "XYZ"),   # nothing in common
        ("", "ABC"),      # empty input
        ("ABC", ""),
        ("A", "ABC"),     # only 1 char in common, below min_threshold=2
    ])
    def test_returns_none_when_there_is_no_qualifying_match(self, a, b):
        assert match_substring_indexes(a, b) is None

    def test_is_case_sensitive(self):
        assert match_substring_indexes("abc", "ABC") is None

    def test_min_threshold_is_honoured(self):
        assert match_substring_indexes("AXY", "ABC", min_threshold=1) is not None
        assert match_substring_indexes("AXY", "ABC", min_threshold=2) is None

    def test_tag_number_match(self):
        # Real-world shape: an OCR'd tag against its fully qualified form.
        ranges1, ranges2 = match_substring_indexes("TI00143", "55-TI-00143")
        assert "".join("TI00143"[s:e + 1] for s, e in ranges1) == "00143"
        assert "".join("55-TI-00143"[s:e + 1] for s, e in ranges2) == "00143"

    @pytest.mark.xfail(
        reason="Docstring promises a split match ([[0,6]], [[3,4],[6,10]]) but the "
               "implementation only ever returns one contiguous run for text1.",
        strict=True,
    )
    def test_documented_example_from_the_docstring(self):
        assert match_substring_indexes("TI00143", "55-TI-00143") == ([[0, 6]], [[3, 4], [6, 10]])


class TestIsRectangleOverlap:
    #                       x0  y0  x1  y1
    BASE = (10, 10, 20, 20)

    @pytest.mark.parametrize("other", [
        (15, 15, 25, 25),   # corner overlap
        (12, 12, 18, 18),   # fully contained
        (0, 0, 30, 30),     # fully containing
        (10, 10, 20, 20),   # identical
        (19, 19, 21, 21),   # 1px overlap
    ])
    def test_overlapping(self, other):
        assert is_rectangle_overlap(self.BASE, other) is True

    @pytest.mark.parametrize("other", [
        (30, 30, 40, 40),   # far away
        (20, 10, 30, 20),   # shares only the right edge
        (0, 10, 10, 20),    # shares only the left edge
        (10, 20, 20, 30),   # shares only the bottom edge
        (10, 0, 20, 10),    # shares only the top edge
    ])
    def test_touching_edges_do_not_count_as_overlap(self, other):
        assert is_rectangle_overlap(self.BASE, other) is False

    @pytest.mark.parametrize("other", [
        (15, 15, 25, 25), (30, 30, 40, 40), (0, 0, 30, 30), (20, 10, 30, 20),
    ])
    def test_is_commutative(self, other):
        assert is_rectangle_overlap(self.BASE, other) == is_rectangle_overlap(other, self.BASE)

    def test_accepts_floats_by_truncating(self):
        # Text extraction hands back float bboxes; the helper int()s them.
        assert is_rectangle_overlap((10.9, 10.9, 20.1, 20.1), (15.5, 15.5, 25.5, 25.5)) is True


class TestIsBboxWithinBbox:
    OUTER = (0, 0, 100, 100)

    @pytest.mark.parametrize("inner", [
        (10, 10, 20, 20),
        (0, 0, 100, 100),    # identical counts as within
        (0, 0, 1, 1),        # flush against the top-left
        (99, 99, 100, 100),  # flush against the bottom-right
    ])
    def test_contained(self, inner):
        assert is_bbox_within_bbox(inner, self.OUTER) is True

    @pytest.mark.parametrize("inner", [
        (-1, 0, 20, 20),      # spills left
        (0, -1, 20, 20),      # spills up
        (90, 90, 101, 100),   # spills right
        (90, 90, 100, 101),   # spills down
        (200, 200, 300, 300), # entirely outside
    ])
    def test_not_contained(self, inner):
        assert is_bbox_within_bbox(inner, self.OUTER) is False

    def test_containment_implies_overlap(self):
        inner = (10, 10, 20, 20)
        assert is_bbox_within_bbox(inner, self.OUTER) is True
        assert is_rectangle_overlap(inner, self.OUTER) is True


class TestTextIndentRemove:
    def test_strips_leading_whitespace_per_line(self):
        assert text_indent_remove("  a\n    b\nc") == "a\nb\nc"

    def test_preserves_trailing_whitespace(self):
        assert text_indent_remove("  a  ") == "a  "

    def test_empty_string(self):
        assert text_indent_remove("") == ""

    def test_drops_the_trailing_newline(self):
        # splitlines()/join round-trip loses a final newline.
        assert text_indent_remove("a\n") == "a"


class TestTagnameRegex:
    import re as _re

    @pytest.mark.parametrize("text,expected", [
        ("Reading from 55-TI-00143 now", "55-TI-00143"),
        ("tag ABC_DEF_123 here", "ABC_DEF_123"),
        ("valve XV-101 open", "XV-101"),
        ("pump PU_42 running", "PU_42"),
    ])
    def test_extracts_industrial_tagnames(self, text, expected):
        match = self._re.search(TAGNAME_REGEX, text)
        assert match is not None
        assert match.group(0) == expected

    @pytest.mark.parametrize("text", [
        "no tags in this sentence",
        "lower-case-thing",
        "A-1",
        "P_42",  # the prefix must be at least 2 chars
    ])
    def test_ignores_non_tagnames(self, text):
        assert self._re.search(TAGNAME_REGEX, text) is None
