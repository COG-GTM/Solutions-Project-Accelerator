"""Handlebar expressions in HMI symbol XML come from ACM libraries in the project folder.

``parse_handlebars`` must only evaluate arithmetic: anything that reaches attributes,
strings or other objects is left as literal text instead of being executed.
"""

import pytest

from bin.logic_gfx_to_svg import evaluate_arithmetic, parse_handlebars


INJECTION_PAYLOADS = [
    "{().__class__.__base__.__subclasses__()}",
    "{().__claſs__.__baſe__.__ſubclaſſes__()}",
    "{().__ｃlass__.__ｂase__.__ｓubclasses__()}",
    "{'\\143\\155\\144'}",
    "{__claſs__}",
    "{Calc(().__class__)}",
    "{Max(*().__class__.__mro__)}",
    "{Round(x=1)}",
    "{(lambda: 1)()}",
    "{[1, 2][0]}",
]


@pytest.mark.parametrize("replace_unknown_vars", [True, False])
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_non_arithmetic_expressions_are_left_as_literal_text(payload, replace_unknown_vars):
    xml = f'<text name="t" caption="{payload}" />'
    assert parse_handlebars(xml, replace_unknown_vars=replace_unknown_vars) == xml


@pytest.mark.parametrize("payload", [
    "().__class__",
    "().__claſs__",
    "'\\143\\155\\144'",
    "__import__",
    "abs.__self__",
    "Calc(1)[0]",
])
def test_evaluate_arithmetic_rejects_non_arithmetic_nodes(payload):
    with pytest.raises((ValueError, SyntaxError)):
        evaluate_arithmetic(payload, {}, {"Calc": lambda x: x})


def test_acm_parameter_values_are_not_evaluated_as_code():
    xml = '<rect left="{Calc(10 + {X1})}" caption="{Label}" />'
    variables = {"X1": "().__class__.__base__.__subclasses__()", "Label": "1+1"}
    assert parse_handlebars(xml, variables=variables, replace_unknown_vars=False) == (
        '<rect left="{Calc(10 + ().__class__.__base__.__subclasses__())}" caption="1+1" />'
    )


def test_position_calc_still_evaluates():
    assert parse_handlebars('left="{Calc(41 + {Fn_PositionX})}"') == 'left="41"'


def test_library_symbol_expressions_still_evaluate():
    xml = (
        '<line top="{Calc(15 + {SymbolHeight}*{TopIndex})}" '
        'width="{Abs({X1}-{X2})}" height="{Max(3, {Y1})}" left="{Calc({CenterX} - 0)}" />'
    )
    assert parse_handlebars(xml, variables={"X1": "30", "X2": "10", "Y1": "7"}) == (
        '<line top="15" width="20" height="7" left="0" />'
    )


def test_unknown_names_become_zero_only_when_requested():
    xml = '<rect width="{Width}" left="{Calc(5 + Offset)}" />'
    assert parse_handlebars(xml) == '<rect width="0" left="5" />'
    assert parse_handlebars(xml, replace_unknown_vars=False) == xml


def test_string_variables_are_substituted_verbatim():
    xml = '<group name="{ObjectName}_PageLink"><text caption="{Label}" /></group>'
    variables = {"ObjectName": "P-101", "Label": "Feed Pump"}
    assert parse_handlebars(xml, variables=variables, replace_unknown_vars=False) == (
        '<group name="P-101_PageLink"><text caption="Feed Pump" /></group>'
    )


def test_invalid_arithmetic_is_left_as_literal_text():
    xml = '<rect left="{1/0}" top="{Calc(1, 2)}" />'
    assert parse_handlebars(xml) == xml


@pytest.mark.parametrize("payload", [
    "{" + "*".join(["99999999"] * 60) + "}",
    "{Calc(int(1e300) * int(1e300))}",
    "{1e999}",
    "{Max(1e308 * 10, 1)}",
])
def test_oversized_intermediate_values_are_rejected(payload):
    xml = f'<rect left="{payload}" />'
    assert parse_handlebars(xml) == xml
