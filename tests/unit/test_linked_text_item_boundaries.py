"""Regression tests for linked-text templates over-matching across list items.

Page text is a flat character stream with the line breaks stripped, so a
template wildcard used to run past the end of its bullet and swallow the next
one, producing values such as ``switch LSHH2002 healthy*Discharge pressure PI-2008``.
"""

import re

import pytest

from bin.logic_linked_texts import (
    GivenTextLink,
    LinkedText,
    Linked_Texts,
    TargetTextType,
    contains_item_separator,
)


BULLET = '\u2022'

# Two bullets of the demo control philosophy, as they appear once the page
# characters are concatenated without line breaks.
MERGED_LIST_TEXT = (
    'Tank high high level switch LSHH-2002 healthy'
    + BULLET
    + 'Discharge pressure PI-2008 > LoLo'
)

SINGLE_LIST_ITEM_TEXT = 'Suction tank level LIC-2001 > Lo'


def build_regex_for(given_text_string, key_and_ignore_indexes, key_indexes_only=None,
                    text_type=TargetTextType.STRING):
    linked_texts = object.__new__(Linked_Texts)
    given_text = GivenTextLink(linked=True
                               ,text=given_text_string
                               ,key_and_ignore_indexes=list(key_and_ignore_indexes)
                               ,in_list=True)
    linked_text = LinkedText(text='LIC2001.Sts_LoDev'
                             ,text_type=text_type
                             ,given_text={'id': given_text})

    key_indexes = key_and_ignore_indexes if key_indexes_only is None else key_indexes_only
    linked_texts._Linked_Texts__build_regex_string(linked_text, 'id', key_indexes)
    return linked_text.given_text['id'].regex_string


class TestContainsItemSeparator:

    @pytest.mark.parametrize('text', ['a' + BULLET + 'b', 'a\nb', 'a\u00b7b', 'a\uf0b7b'])
    def test_detects_separators(self, text):
        assert contains_item_separator(text) is True

    def test_plain_value_has_no_separator(self):
        assert contains_item_separator('LIC2001.Sts_LoDev') is False


class TestTemplateRegexStopsAtItemBoundary:

    def test_template_does_not_cross_a_bullet(self):
        # ' level LIC-2001 > Lo' with 'LIC' and '2001' as the key texts.
        regex = build_regex_for(' level LIC-2001 > Lo', [[7, 10], [11, 15]])

        assert re.search(regex, MERGED_LIST_TEXT) is None

    def test_template_still_matches_its_own_item(self):
        regex = build_regex_for(' level LIC-2001 > Lo', [[7, 10], [11, 15]])

        match = re.search(regex, SINGLE_LIST_ITEM_TEXT)

        assert match is not None
        assert match.group(1) == 'LIC'
        assert match.group(2) == '2001'

    def test_ignored_text_wildcard_does_not_cross_a_bullet(self):
        # Only 'LIC' is a key text, so '2001' becomes an ignored-text wildcard.
        regex = build_regex_for(' level LIC-2001 > Lo', [[7, 10], [11, 15]], key_indexes_only=[[7, 10]])

        assert re.search(regex, MERGED_LIST_TEXT) is None
        assert re.search(regex, SINGLE_LIST_ITEM_TEXT) is not None
