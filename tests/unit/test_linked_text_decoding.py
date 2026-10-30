"""Stored ``links``/``given_text`` strings come from project archives and must never be evaluated."""

import math

import pytest

from bin.logic_linked_texts import (
    GivenTextLink,
    LinkedText,
    LinkedTextDecodeError,
    TargetTextLink,
    TargetTextType,
    decode_link_map,
)


def stored_record(**overrides):
    linked_text = LinkedText(
        text="TIC-401",
        text_type=TargetTextType.OBJECT,
        linked=True,
        links={"0-7": TargetTextLink(target_text_indexes=(0, 7), given_text_id="g1",
                                     given_text_indexes=[(0, 7), (-1, float("inf"))])},
        given_text={"g1": GivenTextLink(linked=True, text="TIC-401", indexes=(12, float("inf")),
                                        path="projects/P/docs/cp.pdf", pno=3, roi=[0, 0, 10, 10],
                                        table_shape=(2, 3), table_bbox=(1.5, -2.0, 3.0, 4.0))},
    )
    record = linked_text.dict()
    record.update(overrides)
    return record


class TestRoundTrip:
    def test_stored_record_decodes_to_dataclasses(self):
        linked_text = LinkedText.from_dict(stored_record())

        link = linked_text.links["0-7"]
        assert isinstance(link, TargetTextLink)
        assert link.target_text_indexes == (0, 7)
        assert link.given_text_indexes[1][0] == -1
        assert math.isinf(link.given_text_indexes[1][1])

        given = linked_text.given_text["g1"]
        assert isinstance(given, GivenTextLink)
        assert given.indexes[0] == 12 and math.isinf(given.indexes[1])
        assert given.table_shape == (2, 3)
        assert given.table_bbox == (1.5, -2.0, 3.0, 4.0)
        assert given.roi == [0, 0, 10, 10]

    def test_none_values_stay_none(self):
        linked_text = LinkedText.from_dict(LinkedText(text="x").dict())
        assert linked_text.links is None
        assert linked_text.given_text is None

    def test_empty_maps_decode(self):
        assert decode_link_map("{}", TargetTextLink) == {}


PAYLOADS = [
    "__import__('os').system('echo pwned')",
    "{'a': __import__('os').system('echo pwned')}",
    "{'a': {'given_text_id': open('/etc/passwd').read()}}",
    "{'a': {'given_text_id': ().__class__.__mro__}}",
    "{'a': {'given_text_id': [x for x in ()]}}",
    "{'a': {'given_text_id': (lambda: 1)}}",
    "{**{}}",
    "{'a': {'target_text_indexes': (float('inf'), 1), 'given_text_id': 'g', 'given_text_indexes': []}}",
    "{'a': {'given_text_id': 1 + 1}}",
    "{'a': {'given_text_id': -'x'}}",
]


class TestRejectsCode:
    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_expressions_are_rejected(self, payload):
        with pytest.raises(LinkedTextDecodeError):
            decode_link_map(payload, TargetTextLink)

    def test_payload_is_never_executed(self, tmp_path):
        marker = tmp_path / "pwned"
        payload = "__import__('pathlib').Path(%r).write_text('x')" % str(marker)
        with pytest.raises(LinkedTextDecodeError):
            LinkedText.from_dict(stored_record(links=payload))
        assert not marker.exists()

    def test_given_text_payload_rejected(self):
        with pytest.raises(LinkedTextDecodeError):
            LinkedText.from_dict(stored_record(given_text="exec('import os')"))


class TestRejectsBadShape:
    @pytest.mark.parametrize("payload", [
        "[1, 2]",
        "'just a string'",
        "{'a': [1, 2]}",
        "{1: {}}",
        "not valid python (",
        "{'a': {'unknown_field': 1, 'target_text_indexes': (0, 1), 'given_text_id': 'g', 'given_text_indexes': []}}",
        "{'a': {'given_text_id': 'g'}}",
    ])
    def test_invalid_structures_raise(self, payload):
        with pytest.raises(LinkedTextDecodeError):
            decode_link_map(payload, TargetTextLink)

    def test_deep_nesting_is_rejected(self):
        payload = "{'a': {'given_text_id': " + "[" * 200 + "]" * 200 + "}}"
        with pytest.raises(LinkedTextDecodeError):
            decode_link_map(payload, TargetTextLink)

    def test_non_dict_record_raises(self):
        with pytest.raises(LinkedTextDecodeError):
            LinkedText.from_dict("TIC-401")

    def test_unknown_record_keys_are_ignored(self):
        linked_text = LinkedText.from_dict(stored_record(processed_pages={"x": [1]}))
        assert linked_text.text == "TIC-401"
