"""Restricted evaluators for ACM IncludeCondition text and handlebar arithmetic.

Library XML and ACM parameter values can come from imported project archives
or third-party libraries, so these must never fall back to ``eval()``.
"""

import os
from types import SimpleNamespace

import pytest

from bin.logic_safe_expression import (
    UnsafeExpressionError,
    condition_variable_names,
    evaluate_arithmetic,
    evaluate_include_condition,
)

PAYLOAD = '__import__("os").system("calc")'


@pytest.fixture
def no_import(monkeypatch):
    """Fail the test if the payload ever reaches os.system."""
    calls = []
    monkeypatch.setattr(os, 'system', lambda command: calls.append(command) or 0)
    yield calls
    assert calls == []


class TestIncludeCondition:

    CONDITION = '{SymbolStyle} = 0 AND {SymbolOrientation} = 0 AND ({SymbolType} = 0 OR {SymbolType} = 1)'

    @pytest.mark.parametrize('values, expected', [
        ({'SymbolStyle': '0', 'SymbolOrientation': '0', 'SymbolType': '1'}, True),
        ({'SymbolStyle': '0', 'SymbolOrientation': '0', 'SymbolType': '2'}, False),
        ({'SymbolStyle': '1', 'SymbolOrientation': '0', 'SymbolType': '0'}, False),
        ({'SymbolStyle': 0, 'SymbolOrientation': 0.0, 'SymbolType': 0}, True),
    ])
    def test_acm_library_condition(self, values, expected):
        assert evaluate_include_condition(self.CONDITION, values) is expected

    @pytest.mark.parametrize('condition, expected', [
        ('({SymbolOrientation} = 2)', True),
        ('({SymbolOrientation} = 0) OR ({SymbolOrientation} = 1) OR ({SymbolOrientation} = 3)', False),
        ('Always', True),
        ('{SymbolOrientation} <> 2', False),
        ('{SymbolOrientation} != 1', True),
        ('{SymbolOrientation} >= 2 and {SymbolOrientation} <= 2', True),
        ('{SymbolOrientation} > 2', False),
        ('NOT {SymbolOrientation} = 1', True),
        ('{SymbolOrientation} == 2.0', True),
    ])
    def test_operators(self, condition, expected):
        assert evaluate_include_condition(condition, {'SymbolOrientation': '2'}) is expected

    def test_string_and_missing_values(self):
        assert evaluate_include_condition('{Mode} = "Auto"', {'Mode': 'Auto'}) is True
        assert evaluate_include_condition('{Mode} = 0', {'Mode': 'Auto'}) is False
        assert evaluate_include_condition('{Missing} = 0', {'Missing': None}) is False
        assert evaluate_include_condition('{Missing} = 0', {}) is False

    def test_callable_lookup(self):
        seen = []
        assert evaluate_include_condition('{A} = 1', lambda name: seen.append(name) or '1') is True
        assert seen == ['A']

    @pytest.mark.parametrize('value', [
        PAYLOAD,
        '0 or __import__("os").system("calc")',
        '1) OR (1',
        '().__class__.__base__.__subclasses__()',
        '0 == 0',
    ])
    def test_parameter_values_are_data_not_code(self, value, no_import):
        # The value is compared as an opaque string, so it can never match 0.
        assert evaluate_include_condition('{SymbolStyle} = 0', {'SymbolStyle': value}) is False

    @pytest.mark.parametrize('condition', [
        PAYLOAD + ' == 0 AND {SymbolStyle} = 0',
        '__import__("os")',
        'open("x")',
        '{SymbolStyle}.__class__',
        '{SymbolStyle} = 0 AND',
        '({SymbolStyle} = 0',
        '{SymbolStyle} = 0 ; 1',
        '',
        'lambda: 0',
        '[1][0]',
    ])
    def test_malicious_or_malformed_conditions_are_rejected(self, condition, no_import):
        with pytest.raises(UnsafeExpressionError):
            evaluate_include_condition(condition, {'SymbolStyle': '0'})

    def test_variable_names(self):
        assert condition_variable_names(self.CONDITION) == ['SymbolStyle', 'SymbolOrientation', 'SymbolType']


class TestArithmetic:

    @pytest.mark.parametrize('expr, expected', [
        ('41 + 0', 41),
        ('(10 - 4) * 2 / 3', 4.0),
        ('-5 + 7 // 2 % 2', -4),
        ('max(3, 4) - min(1, 2)', 3),
        ('round(2.6) + abs(-1) + int(3.9) + float(1)', 8.0),
        ('2 ** 10', 1024),
    ])
    def test_numeric_expressions(self, expr, expected):
        assert evaluate_arithmetic(expr) == expected

    @pytest.mark.parametrize('expr', [
        PAYLOAD,
        '().__class__.__base__.__subclasses__()',
        '(1).__class__',
        'abs.__self__',
        '"a" * 3',
        'x + 1',
        'max(*[1, 2])',
        'round(1.5, ndigits=1)',
        '9 ** 9999999',
        '10 ** 18 * 10 ** 18',
        '1 / 0',
        '(lambda: 1)()',
        '[1, 2]',
        '1 if 1 else 0',
        '(' * 500 + '1' + ')' * 500,
    ])
    def test_rejects_anything_else(self, expr, no_import):
        with pytest.raises(UnsafeExpressionError):
            evaluate_arithmetic(expr)


class TestGfxCallers:
    """End-to-end through the two former eval() sinks."""

    def test_parse_handlebars_does_not_execute_parameter_values(self, no_import):
        gfx_to_svg = pytest.importorskip('bin.logic_gfx_to_svg')
        text = '<text left="{Calc(41 + {Fn_PositionX})}" caption="{Desc}" top="{Payload}"/>'
        out = gfx_to_svg.parse_handlebars(
            text,
            variables={'Desc': 'Pump 1', 'Payload': '().__class__.__base__.__subclasses__()'},
            replace_unknown_vars=False)
        assert 'left="41"' in out
        assert 'caption="Pump 1"' in out
        assert '().__class__.__base__.__subclasses__()' in out

    def _editor(self, gfx_file_editor, parameters):
        editor = gfx_file_editor.GfxFileEditor.__new__(gfx_file_editor.GfxFileEditor)
        editor.element_map = {'P101': SimpleNamespace(library_id='lib', object_id=7, xml_element=None,
                                                      hmi_symbol=None)}
        editor.use_express = False
        editor.acm_data_handler = SimpleNamespace(
            get_parameter_in_object=lambda object_id, name: parameters.get(name))
        return editor

    def _symbols(self, condition):
        return {'lib': [{'Name': 'GO_Bad', 'IncludeCondition': condition, 'Lines': 1, 'Value': ''},
                        {'Name': 'GO_Default', 'IncludeCondition': 'Always', 'Lines': 1, 'Value': ''}]}

    def test_matches_symbol_by_condition(self):
        gfx_file_editor = pytest.importorskip('bin.logic_gfx_file_editor')
        editor = self._editor(gfx_file_editor, {'SymbolStyle': '0', 'SymbolOrientation': '1'})
        editor.match_elements_to_library_symbols(
            self._symbols('{SymbolStyle} = 0 AND ({SymbolOrientation} = 0 OR {SymbolOrientation} = 1)'))
        assert editor.element_map['P101'].hmi_symbol == 'GO_Bad'

    def test_parameter_payload_is_not_executed(self, no_import):
        gfx_file_editor = pytest.importorskip('bin.logic_gfx_file_editor')
        editor = self._editor(gfx_file_editor, {'SymbolStyle': PAYLOAD})
        editor.match_elements_to_library_symbols(self._symbols('{SymbolStyle} = 0'))
        assert editor.element_map['P101'].hmi_symbol == 'GO_Default'

    def test_library_payload_is_rejected_and_logged(self, no_import, caplog):
        gfx_file_editor = pytest.importorskip('bin.logic_gfx_file_editor')
        editor = self._editor(gfx_file_editor, {'SymbolStyle': '0'})
        with caplog.at_level('WARNING'):
            editor.match_elements_to_library_symbols(self._symbols(PAYLOAD + ' == 0 AND {SymbolStyle} = 0'))
        assert editor.element_map['P101'].hmi_symbol == 'GO_Default'
        assert 'Rejected IncludeCondition' in caplog.text
