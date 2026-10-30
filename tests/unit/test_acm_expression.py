"""ACM library expressions are evaluated by a whitelisting AST interpreter, not eval/exec."""

import importlib
import sys
import types

import pandas as pd
import pytest

from bin.logic_acm_expression import (
    AcmExpressionError,
    evaluate_acm_expression,
    evaluate_conditional_function,
)

ESCAPE = "().__class__.__base__.__subclasses__()"


def func_xml(body, ftype="Conditional"):
    return f'<Func Name="fn" Scope="Object" FType="{ftype}" ResType="Numeric">{body}</Func>'


class TestExpressions:
    def test_quoted_string_comparison(self):
        expr = "'{EventLogging_Style}' = 'EdgeGateway'"
        assert evaluate_acm_expression(expr, {"EventLogging_Style": "EdgeGateway"}) is True
        assert evaluate_acm_expression(expr, {"EventLogging_Style": "Local"}) is False

    def test_numeric_comparison(self):
        assert evaluate_acm_expression("{IO_Map_Strategy}=5", {"IO_Map_Strategy": "5"}) is True
        assert evaluate_acm_expression("{IO_Map_Strategy}=5", {"IO_Map_Strategy": "3"}) is False

    def test_acm_operators(self):
        values = {"A": "1", "B": "0", "S": "x"}
        assert evaluate_acm_expression("{A} AND {B}", values) == 0
        assert evaluate_acm_expression("{A} Or {B}", values) == 1
        assert evaluate_acm_expression("NOT {B}", values) is True
        assert evaluate_acm_expression("{A} <> {B}", values) is True
        assert evaluate_acm_expression("{A} >= {B}", values) is True
        assert evaluate_acm_expression("{A} <= {B}", values) is False
        assert evaluate_acm_expression("'{S}' & '_suffix'", values) == "x_suffix"
        assert evaluate_acm_expression("'pre_{S}'", values) == "pre_x"

    def test_shipped_library_calculations(self):
        values = {"X1": "10", "X2": "35", "Width": "40"}
        assert evaluate_acm_expression("{Abs({X1}-{X2})}", values) == 25
        assert evaluate_acm_expression("{Width} / 2", values) == 20
        assert evaluate_acm_expression("{Abs({X1}-{X2})} < {Width}", values) is True
        assert evaluate_acm_expression("Round(2.6) + Int(3.9) + Length('abc')", {}) == 9

    def test_braced_group_without_placeholders(self):
        assert evaluate_acm_expression("{Abs(5)}") == 5
        assert evaluate_acm_expression("{Abs(-2)} + {N}", {"N": "1"}) == 3

    def test_escaped_quotes_and_backslashes_in_literals(self):
        assert evaluate_acm_expression("'a\\'b' = 'a\\'b'") is True
        assert evaluate_acm_expression("'a\\'b'") == "a'b"
        assert evaluate_acm_expression("'c:\\\\dir'") == "c:\\dir"
        assert evaluate_acm_expression("'{P}'", {"P": "x\\' + 1 + '"}) == "x\\' + 1 + '"

    def test_oversized_parameter_value_raises(self):
        with pytest.raises(AcmExpressionError):
            evaluate_acm_expression("'{P}'", {"P": "a" * 10_000_000})
        with pytest.raises(AcmExpressionError):
            evaluate_acm_expression("{P}", {"P": "a" * 10_000_000})

    def test_constant_without_placeholders(self):
        assert evaluate_acm_expression("99999999999") == 99999999999

    def test_parameter_values_are_data_not_code(self):
        payload = "__import__('os').system('id')"
        assert evaluate_acm_expression("{P}", {"P": payload}) == payload
        assert evaluate_acm_expression("'{P}'", {"P": "x' + " + ESCAPE + " + '"}) == "x' + " + ESCAPE + " + '"
        assert evaluate_acm_expression("{P} = 5", {"P": ESCAPE}) is False

    @pytest.mark.parametrize("expr", [
        ESCAPE,
        "().__class__",
        "''.join(['a'])",
        "{A}[0]",
        "(lambda: 1)()",
        "[x for x in (1,)]",
        "__import__('os')",
        "open('x')",
        "abs(x=1)",
        "2 ** 1000",
        "'a' * 100000000",
        "{A}.__class__",
        "unknown_name",
        "1; 2",
    ])
    def test_disallowed_constructs_raise(self, expr):
        with pytest.raises(AcmExpressionError):
            evaluate_acm_expression(expr, {"A": "abc"})

    def test_division_by_zero_raises(self):
        with pytest.raises(AcmExpressionError):
            evaluate_acm_expression("{A} / 0", {"A": "1"})


class TestConditionalFunctions:
    def test_event_limit(self):
        xml = func_xml("<ifcond Value=\"32767\"><![CDATA['{EventLogging_Style}' = 'EdgeGateway']]></ifcond>"
                       "<else Value=\"15\" />")
        assert evaluate_conditional_function(xml, {"EventLogging_Style": "EdgeGateway"}) == 32767
        assert evaluate_conditional_function(xml, {"EventLogging_Style": "Local"}) == 15

    def test_redundant(self):
        xml = func_xml('<ifcond Value="1"><![CDATA[{Has_Redundant} AND {Cfg_HasSecNotRdyAlm}]]></ifcond>'
                       '<else Value="0" />')
        assert evaluate_conditional_function(xml, {"Has_Redundant": "1", "Cfg_HasSecNotRdyAlm": "1"}) == 1
        assert evaluate_conditional_function(xml, {"Has_Redundant": "1", "Cfg_HasSecNotRdyAlm": "0"}) == 0

    def test_nested_conditions(self):
        xml = func_xml('<ifcond><![CDATA[True]]><ifcond Value="1"><![CDATA[False]]></ifcond>'
                       '<ifcond Value="2"><![CDATA[True]]></ifcond><else Value="3" /></ifcond>'
                       '<else Value="4" />')
        assert evaluate_conditional_function(xml, {}) == 2

    def test_shipped_process_line_width(self):
        xml = func_xml('<ifcond Value="{Width}"><![CDATA[{Abs({X1}-{X2})} < {Width}]]></ifcond>'
                       '<else Value="{Abs({X1}-{X2})}" />')
        assert evaluate_conditional_function(xml, {"X1": "0", "X2": "10", "Width": "40"}) == 40
        assert evaluate_conditional_function(xml, {"X1": "0", "X2": "90", "Width": "40"}) == 90

    def test_escape_in_condition_raises(self):
        xml = func_xml(f'<ifcond Value="1"><![CDATA[{ESCAPE}]]></ifcond><else Value="0" />')
        with pytest.raises(AcmExpressionError):
            evaluate_conditional_function(xml, {})

    def test_escape_in_value_raises(self):
        xml = func_xml(f'<ifcond Value="{ESCAPE}"><![CDATA[True]]></ifcond>')
        with pytest.raises(AcmExpressionError):
            evaluate_conditional_function(xml, {})

    def test_code_injection_through_value_is_not_executed(self):
        xml = func_xml('<ifcond Value="1"><![CDATA[True]]></ifcond>'
                       '<else Value="0&#10;    import os&#10;    os.system(\'id\')" />')
        assert evaluate_conditional_function(xml, {}) == 1


class _FakeAcmDataHandler:
    def __init__(self, parameters):
        self._parameters = parameters

    def get_all_parameters_in_object(self, object_id):
        return pd.DataFrame({"Name": list(self._parameters), "Value": list(self._parameters.values())})


@pytest.fixture
def handler_module(monkeypatch):
    stubs = {
        "bin.logic_acm_data_handler": {"ACM_Data_Handler": object},
        "bin.logic_acm_libraries_retrieval": {"acm_libraries_retrieval": None, "get_library_file_path": None},
        "bin.logic_acm_library_parser": {"acm_library_parser": None},
    }
    for name, attrs in stubs.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "bin.logic_acm_function_handler", raising=False)
    module = importlib.import_module("bin.logic_acm_function_handler")
    yield module
    sys.modules.pop("bin.logic_acm_function_handler", None)


class TestFunctionHandler:
    def test_calculation(self, handler_module):
        xml = func_xml("<Exp><![CDATA[{IO_Map_Strategy}=5]]></Exp>", "Calculation")
        assert handler_module.acm_function_Handler(xml, 1, _FakeAcmDataHandler({"IO_Map_Strategy": "5"})) == "True"

    def test_conditional(self, handler_module):
        xml = func_xml("<ifcond Value=\"32767\"><![CDATA['{EventLogging_Style}' = 'EdgeGateway']]></ifcond>"
                       "<else Value=\"15\" />")
        handler = _FakeAcmDataHandler({"EventLogging_Style": "EdgeGateway"})
        assert handler_module.acm_function_Handler(xml, 1, handler) == "32767"

    def test_calculation_escape_raises(self, handler_module):
        xml = func_xml(f"<Exp><![CDATA[{ESCAPE}]]></Exp>", "Calculation")
        with pytest.raises(AcmExpressionError):
            handler_module.acm_function_Handler(xml, 1, _FakeAcmDataHandler({}))

    def test_conditional_escape_in_value_raises(self, handler_module):
        xml = func_xml(f'<ifcond Value="{ESCAPE}"><![CDATA[True]]></ifcond>')
        with pytest.raises(AcmExpressionError):
            handler_module.acm_function_Handler(xml, 1, _FakeAcmDataHandler({}))

    def test_parameter_handler_max(self, handler_module, monkeypatch):
        monkeypatch.setattr(handler_module, "process_acm_variable", lambda name, *a, **k: {"Count": "4"}[name])
        assert handler_module.acm_parameter_handler("{Count} * 2", 1, None, "p") == "8"
        assert handler_module.acm_parameter_handler("99999999999", 1, None, "p") == "99999999999"

    def test_parameter_handler_escape_in_max_raises(self, handler_module, monkeypatch):
        monkeypatch.setattr(handler_module, "process_acm_variable", lambda name, *a, **k: "1")
        with pytest.raises(AcmExpressionError):
            handler_module.acm_parameter_handler("{Count} + " + ESCAPE, 1, None, "p")
