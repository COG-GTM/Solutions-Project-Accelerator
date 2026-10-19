"""Unit tests for bin/logic_extracted_logic_to_rockwell_code.py.

These lock in the converter's current output so the parser can be refactored
safely. Where the docstring and the implementation disagree, the mismatch is
recorded as a strict xfail rather than papered over.
"""

import pytest

from bin.logic_extracted_logic_to_rockwell_code import LogicToRockwellConverter

NIB_INFO = {
    "TIC-401": {"nib_name": "Val", "nib_data_type": "Real"},
    "FIT-205": {"nib_name": "Val", "nib_data_type": "Real"},
    "PMP-1": {"nib_name": "Run", "nib_data_type": "Bool"},
}


@pytest.fixture
def converter():
    return LogicToRockwellConverter()


class TestTokenizer:
    def test_splits_a_simple_comparison(self, converter):
        tokens = converter._tokenize_logic_expression("TIC-401.value < 200")
        assert tokens == [{
            "type": "condition", "tagname": "TIC-401", "property": "value",
            "operator": "<", "value": "200",
        }]

    def test_recognises_and_or_operators(self, converter):
        tokens = converter._tokenize_logic_expression("(A.v < 1) AND (B.v > 2) OR (C.v = 3)")
        operators = [t["value"] for t in tokens if t["type"] == "operator"]
        assert operators == ["AND", "OR"]

    def test_emits_paren_tokens(self, converter):
        tokens = converter._tokenize_logic_expression("(A.v < 1)")
        assert [t["value"] for t in tokens if t["type"] == "paren"] == ["(", ")"]

    @pytest.mark.parametrize("operator", ["<=", ">=", "!=", "<", ">", "="])
    def test_all_comparison_operators_are_recognised(self, converter, operator):
        tokens = converter._tokenize_logic_expression(f"A.v {operator} 1")
        assert tokens[0]["operator"] == operator

    def test_longer_operators_win_over_their_prefixes(self, converter):
        assert converter._tokenize_logic_expression("A.v <= 1")[0]["operator"] == "<="
        assert converter._tokenize_logic_expression("A.v >= 1")[0]["operator"] == ">="

    def test_a_bare_tagname_becomes_a_boolean_condition(self, converter):
        token = converter._tokenize_logic_expression("PMP-1.run")[0]
        assert token["operator"] is None
        assert token["value"] is None
        assert token["tagname"] == "PMP-1"
        assert token["property"] == "run"

    def test_tagname_without_a_property(self, converter):
        token = converter._tokenize_logic_expression("PMP1")[0]
        assert token["tagname"] == "PMP1"
        assert token["property"] is None

    def test_only_the_last_dot_separates_the_property(self, converter):
        token = converter._tokenize_logic_expression("Area.Line.Motor.run")[0]
        assert token["tagname"] == "Area.Line.Motor"
        assert token["property"] == "run"

    def test_empty_expression_yields_no_tokens(self, converter):
        assert converter._tokenize_logic_expression("") == []


class TestTopLevelOrDetection:
    def test_detects_or_outside_parentheses(self, converter):
        tokens = converter._tokenize_logic_expression("(A.v < 1) OR (B.v > 2)")
        assert converter._has_top_level_or(tokens) is True

    def test_ignores_or_nested_inside_parentheses(self, converter):
        tokens = converter._tokenize_logic_expression("((A.v < 1) OR (B.v > 2))")
        assert converter._has_top_level_or(tokens) is False

    def test_and_only_expression(self, converter):
        tokens = converter._tokenize_logic_expression("(A.v < 1) AND (B.v > 2)")
        assert converter._has_top_level_or(tokens) is False


class TestConvertLogicExpression:
    @pytest.mark.parametrize("expression,expected", [
        ("(TIC-401.value < 200)", "LES(TIC-401.Val,200)"),
        ("TIC-401.value > 200", "GRT(TIC-401.Val,200)"),
        ("TIC-401.value <= 200", "LEQ(TIC-401.Val,200)"),
        ("TIC-401.value >= 200", "GEQ(TIC-401.Val,200)"),
        ("TIC-401.value = 200", "EQU(TIC-401.Val,200)"),
        ("TIC-401.value != 200", "NEQ(TIC-401.Val,200)"),
    ])
    def test_each_comparison_maps_to_its_rockwell_instruction(self, converter, expression, expected):
        assert converter.convert_logic_expression_to_rockwell_code(expression, NIB_INFO) == expected

    def test_boolean_nibs_always_become_xic(self, converter):
        # Documented rule: a Bool NIB emits XIC regardless of the operator used.
        assert converter.convert_logic_expression_to_rockwell_code("(PMP-1.run)", NIB_INFO) == "XIC(PMP-1.Run)"

    def test_and_produces_sequential_instructions(self, converter):
        result = converter.convert_logic_expression_to_rockwell_code(
            "(TIC-401.value < 200) AND (FIT-205.value > 10)", NIB_INFO)
        assert result == "LES(TIC-401.Val,200)GRT(FIT-205.Val,10)"

    def test_or_wraps_instructions_in_brackets(self, converter):
        result = converter.convert_logic_expression_to_rockwell_code(
            "(TIC-401.value < 200) OR (FIT-205.value > 10)", NIB_INFO)
        assert result == "[LES(TIC-401.Val,200)GRT(FIT-205.Val,10)]"

    def test_nested_and_inside_a_top_level_or(self, converter):
        result = converter.convert_logic_expression_to_rockwell_code(
            "((TIC-401.value < 200) AND (FIT-205.value > 10)) OR (FIT-205.value < 50)", NIB_INFO)
        assert result == "[LES(TIC-401.Val,200)GRT(FIT-205.Val,10)LES(FIT-205.Val,50)]"

    def test_brackets_are_balanced(self, converter):
        result = converter.convert_logic_expression_to_rockwell_code(
            "((TIC-401.value < 200) AND (FIT-205.value > 10)) OR (FIT-205.value < 50)", NIB_INFO)
        assert result.count("[") == result.count("]")


class TestMalformedInput:
    """The public method swallows exceptions and returns '' — it must never raise."""

    @pytest.mark.parametrize("expression", [
        "",
        "   ",
        "(((unbalanced",
        "A.v <",
        "AND OR AND",
        ") backwards (",
    ])
    def test_never_raises(self, converter, expression):
        result = converter.convert_logic_expression_to_rockwell_code(expression, NIB_INFO)
        assert isinstance(result, str)

    def test_empty_expression_returns_empty_string(self, converter):
        assert converter.convert_logic_expression_to_rockwell_code("", NIB_INFO) == ""

    def test_unknown_tagname_does_not_raise(self, converter):
        result = converter.convert_logic_expression_to_rockwell_code("NOT-IN-NIB.value < 5", {})
        assert isinstance(result, str)


@pytest.mark.xfail(
    reason="The class docstring advertises '[LES(...)GRT(...)]XIC(FIT-205.sts_HiHi)' but the "
           "implementation flattens the OR branch into a single bracket and never emits "
           "the sts_ status-bit form. Docstring and code need to be reconciled.",
    strict=True,
)
def test_documented_class_docstring_example(converter):
    result = converter.convert_logic_expression_to_rockwell_code(
        "((TIC-401.value < 200) AND (FIT-205.value > 10)) OR (FIT-205 < HiHi)", NIB_INFO)
    assert result == "[LES(TIC-401.Val,200)GRT(FIT-205.Val,10)]XIC(FIT-205.sts_HiHi)"
