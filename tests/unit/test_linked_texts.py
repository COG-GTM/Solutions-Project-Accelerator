"""Unit tests for bin/logic_linked_texts.py — GivenTextLink equality/overlap and enums."""

import pytest

from bin.logic_linked_texts import (
    GivenTextLink,
    LinkType,
    TagnameParameterRelationship,
    TargetTextType,
)


def make_link(indexes=(0, 5), **overrides):
    defaults = dict(
        text="TIC-401",
        indexes=indexes,
        path="projects/P/drawings/a.pdf",
        pno=0,
        roi=[0, 0, 10, 10],
        doc_type="Drawing",
        axis=0,
    )
    defaults.update(overrides)
    return GivenTextLink(**defaults)


class TestGivenTextLinkEquality:
    def test_identical_links_are_equal(self):
        assert make_link() == make_link()

    def test_not_equal_to_other_types(self):
        assert make_link() != "TIC-401"
        assert make_link() != None  # noqa: E711 — exercises the isinstance guard

    @pytest.mark.parametrize("field,value", [
        ("text", "FIT-205"),
        ("path", "projects/P/drawings/b.pdf"),
        ("pno", 1),
        ("roi", [5, 5, 15, 15]),
        ("doc_type", "Table"),
        ("axis", 1),
    ])
    def test_any_identity_field_difference_breaks_equality(self, field, value):
        assert make_link() != make_link(**{field: value})

    def test_ignores_non_identity_fields(self):
        # linked/regex_string/in_table are state, not identity.
        assert make_link(linked=True, regex_string=r"\d+") == make_link(linked=False)

    def test_different_index_ranges_are_not_equal(self):
        assert make_link(indexes=(0, 5)) != make_link(indexes=(2, 7))


class TestGivenTextLinkIsCloseMatch:
    def test_overlapping_ranges_match(self):
        assert make_link(indexes=(0, 5)).is_close_match(make_link(indexes=(3, 8))) is True

    def test_containment_matches(self):
        assert make_link(indexes=(0, 10)).is_close_match(make_link(indexes=(4, 6))) is True

    def test_touching_ranges_match(self):
        # Bounds are inclusive on both sides, so a shared endpoint counts as overlap.
        assert make_link(indexes=(0, 5)).is_close_match(make_link(indexes=(5, 9))) is True

    def test_disjoint_ranges_do_not_match(self):
        assert make_link(indexes=(0, 4)).is_close_match(make_link(indexes=(6, 9))) is False

    def test_is_symmetric(self):
        a, b = make_link(indexes=(0, 5)), make_link(indexes=(3, 8))
        assert a.is_close_match(b) == b.is_close_match(a)

        c, d = make_link(indexes=(0, 2)), make_link(indexes=(7, 9))
        assert c.is_close_match(d) == d.is_close_match(c)

    def test_is_reflexive(self):
        link = make_link(indexes=(2, 6))
        assert link.is_close_match(link) is True

    @pytest.mark.parametrize("field,value", [
        ("path", "projects/P/drawings/b.pdf"),
        ("pno", 1),
        ("roi", [5, 5, 15, 15]),
        ("doc_type", "Table"),
        ("axis", 1),
    ])
    def test_overlap_alone_is_not_enough_across_different_locations(self, field, value):
        a = make_link(indexes=(0, 5))
        b = make_link(indexes=(3, 8), **{field: value})
        assert a.is_close_match(b) is False

    def test_missing_indexes_never_match(self):
        assert make_link(indexes=None).is_close_match(make_link()) is False
        assert make_link().is_close_match(make_link(indexes=None)) is False

    def test_not_a_link_never_matches(self):
        assert make_link().is_close_match("TIC-401") is False


class TestEnumFallbacks:
    """All four enums define _missing_, so unknown DB values must not raise."""

    @pytest.mark.parametrize("value,expected", [
        ("object", TargetTextType.OBJECT),
        ("real", TargetTextType.REAL),
        ("integer", TargetTextType.INT),
        ("string", TargetTextType.STRING),
    ])
    def test_target_text_type_known_values(self, value, expected):
        assert TargetTextType(value) is expected

    @pytest.mark.parametrize("value", ["bogus", "", "OBJECT", None, 42])
    def test_target_text_type_falls_back_to_string(self, value):
        assert TargetTextType(value) is TargetTextType.STRING

    @pytest.mark.parametrize("value", ["bogus", "", None])
    def test_relationship_falls_back_to_undefined(self, value):
        assert TagnameParameterRelationship(value) is TagnameParameterRelationship.UNDEFINED

    def test_relationship_known_values(self):
        assert TagnameParameterRelationship("in_table") is TagnameParameterRelationship.IN_TABLE
        assert TagnameParameterRelationship("list_header") is TagnameParameterRelationship.LIST_HEADER

    @pytest.mark.parametrize("value", ["bogus", "", None])
    def test_link_type_falls_back_to_text(self, value):
        assert LinkType(value) is LinkType.TEXT

    def test_link_type_selector(self):
        assert LinkType("selector") is LinkType.SELECTOR

    def test_enums_are_str_subclasses_so_they_serialise_to_json_cleanly(self):
        assert TargetTextType.REAL == "real"
        assert LinkType.SELECTOR == "selector"
