"""Safe evaluator for ACM library expressions.

ACM library files (``<Exp>``, ``<ifcond>`` text, ``Value`` and ``Max`` attributes)
use a small expression language: ``{Name}`` placeholders, ``=``/``<>`` comparisons,
``AND``/``OR``/``NOT``, ``&`` concatenation and a few functions such as ``Abs``.

Library files can come from imported project archives, so their text is untrusted.
Expressions are never handed to ``eval``/``exec``: they are translated to a Python
expression in which every placeholder is a bound name, parsed with
``ast.parse(mode="eval")`` and walked by an interpreter that only knows constants,
bound names, arithmetic, comparisons, boolean operators and an allowlist of calls.
Anything else (attributes, subscripts, lambdas, comprehensions, ...) is rejected.
"""

import ast
import operator
import re
import xml.etree.ElementTree as ET


class AcmExpressionError(ValueError):
    """Raised when an ACM expression is malformed or uses a disallowed construct."""


MAX_EXPRESSION_LENGTH = 4096
MAX_AST_NODES = 512
MAX_STRING_LENGTH = 65536
MAX_INT_DIGITS = 64

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
_INT_LITERAL = re.compile(r"^[+-]?\d+$")
_FLOAT_LITERAL = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_KEYWORDS = re.compile(r"\b(and|or|not)\b", re.IGNORECASE)
_BOOL_WORDS = re.compile(r"\b(true|false)\b", re.IGNORECASE)

_FUNCTIONS = {
    "abs": abs,
    "int": int,
    "round": round,
    "len": len,
    "length": len,
    "min": min,
    "max": max,
}

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_ALLOWED_NODES = (
    ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
    ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Call,
    *_BIN_OPS, *_UNARY_OPS, *_COMPARE_OPS,
)


def coerce_value(value):
    """Turn a parameter value (as stored in ACM) into a number, bool or string."""
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    text = str(value).strip()
    if _INT_LITERAL.match(text) and len(text.lstrip("+-")) <= MAX_INT_DIGITS:
        return int(text)
    if _FLOAT_LITERAL.match(text):
        return float(text)
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    return str(value)


def _translate_code(segment):
    """Map ACM operators/keywords in a non-string segment to Python syntax."""
    segment = _KEYWORDS.sub(lambda m: f" {m.group(1).lower()} ", segment)
    segment = _BOOL_WORDS.sub(lambda m: m.group(1).capitalize(), segment)
    out = []
    i = 0
    while i < len(segment):
        two = segment[i:i + 2]
        if two == "<>":
            out.append("!=")
            i += 2
        elif two in ("<=", ">=", "!=", "=="):
            out.append(two)
            i += 2
        elif segment[i] == "=":
            out.append("==")
            i += 1
        elif segment[i] == "&":
            out.append(" + ")
            i += 1
        else:
            out.append(segment[i])
            i += 1
    return "".join(out)


def _escape_for_literal(value, quote):
    text = str(value)
    text = text.replace("\\", "\\\\").replace(quote, "\\" + quote)
    return text.replace("\n", "\\n").replace("\r", "\\r")


def translate(expression, variables=None):
    """Translate ACM expression text into (python_source, bindings).

    Placeholders outside string literals become bound names; placeholders inside a
    string literal are inserted as escaped literal text. Other braces act as
    grouping parentheses (``{Abs({X1}-{X2})}``).
    """
    variables = variables or {}
    if expression is None:
        raise AcmExpressionError("empty expression")
    expression = str(expression)
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise AcmExpressionError("expression too long")

    bindings = {}
    names = {}
    out = []
    code = []
    quote = None
    i = 0

    def flush_code():
        if code:
            out.append(_translate_code("".join(code)))
            code.clear()

    while i < len(expression):
        ch = expression[i]
        placeholder = _PLACEHOLDER.match(expression, i) if ch == "{" else None
        if placeholder:
            name = placeholder.group(1).strip()
            if name not in variables:
                raise AcmExpressionError(f"unknown variable {name!r}")
            if quote:
                out.append(_escape_for_literal(variables[name], quote))
            else:
                if name not in names:
                    names[name] = f"_acm_v{len(names)}"
                    bindings[names[name]] = coerce_value(variables[name])
                code.append(f" {names[name]} ")
            i = placeholder.end()
            continue
        if quote:
            if ch == "\\":
                out.append("\\\\")
            elif ch == quote:
                out.append(ch)
                quote = None
            elif ch in "\r\n":
                raise AcmExpressionError("unterminated string literal")
            else:
                out.append(ch)
        elif ch in ("'", '"'):
            flush_code()
            out.append(ch)
            quote = ch
        elif ch == "{":
            code.append("(")
        elif ch == "}":
            code.append(")")
        else:
            code.append(ch)
        i += 1

    if quote:
        raise AcmExpressionError("unterminated string literal")
    flush_code()
    return "".join(out).strip(), bindings


def _check_tree(tree):
    for count, node in enumerate(ast.walk(tree), 1):
        if count > MAX_AST_NODES:
            raise AcmExpressionError("expression too complex")
        if not isinstance(node, _ALLOWED_NODES):
            raise AcmExpressionError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (str, int, float, bool, type(None))):
            raise AcmExpressionError("disallowed constant")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id.lower() not in _FUNCTIONS:
                raise AcmExpressionError("only allowlisted functions may be called")
            if node.keywords:
                raise AcmExpressionError("keyword arguments are not allowed")


def _check_result(value):
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        raise AcmExpressionError("string result too long")
    if isinstance(value, int) and not isinstance(value, bool) and abs(value).bit_length() > 4 * MAX_INT_DIGITS:
        raise AcmExpressionError("integer result too large")
    return value


def _guard_mult(left, right):
    for seq, count in ((left, right), (right, left)):
        if isinstance(seq, str) and isinstance(count, int) and len(seq) * max(count, 0) > MAX_STRING_LENGTH:
            raise AcmExpressionError("string result too long")


def _eval_node(node, bindings):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, bindings)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return bindings[node.id]
        raise AcmExpressionError(f"unknown name {node.id!r}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, bindings)
        right = _eval_node(node.right, bindings)
        if isinstance(node.op, ast.Mult):
            _guard_mult(left, right)
        return _check_result(_BIN_OPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, bindings))
    if isinstance(node, ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        result = None
        for value_node in node.values:
            result = _eval_node(value_node, bindings)
            if bool(result) != is_and:
                return result
        return result
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, bindings)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, bindings)
            if not _COMPARE_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        func = _FUNCTIONS[node.func.id.lower()]
        args = [_eval_node(arg, bindings) for arg in node.args]
        return _check_result(func(*args))
    raise AcmExpressionError(f"disallowed syntax: {type(node).__name__}")


def evaluate_acm_expression(expression, variables=None):
    """Evaluate ACM expression text with ``{Name}`` placeholders bound to ``variables``.

    Raises :class:`AcmExpressionError` for malformed or disallowed expressions.
    """
    source, bindings = translate(expression, variables)
    if not source:
        raise AcmExpressionError("empty expression")
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise AcmExpressionError(f"invalid expression: {error}") from None
    _check_tree(tree)
    try:
        return _eval_node(tree, bindings)
    except AcmExpressionError:
        raise
    except (ArithmeticError, TypeError, ValueError, RecursionError) as error:
        raise AcmExpressionError(f"evaluation failed: {error}") from None


def _condition_text(element):
    return (element.text or "").strip()


def build_conditional_branches(func_elem):
    """Turn a Conditional ``<Func>`` into nested data: a list of branch dicts.

    Each branch is ``{"kind": "if"|"else"|"value", "condition": str|None,
    "value": str|None, "children": [...]}``.
    """
    branches = []
    for child in func_elem:
        if child.tag == "ifcond":
            condition = _condition_text(child)
            if condition:
                branches.append({
                    "kind": "if",
                    "condition": condition,
                    "value": child.get("Value"),
                    "children": build_conditional_branches(child),
                })
            else:
                branches.extend(
                    branch for branch in build_conditional_branches(child) if branch["kind"] == "else"
                )
        elif child.tag == "else":
            branches.append({
                "kind": "else",
                "condition": None,
                "value": child.get("Value"),
                "children": build_conditional_branches(child),
            })
        else:
            branches.append({"kind": "value", "condition": None, "value": child.get("Value"), "children": []})
    return branches


_NO_RESULT = object()


def _evaluate_branches(branches, variables):
    previous_if_taken = None
    for branch in branches:
        kind = branch["kind"]
        if kind == "value":
            return _evaluate_value(branch["value"], variables)
        if kind == "if":
            taken = bool(evaluate_acm_expression(branch["condition"], variables))
            previous_if_taken = taken
        else:
            taken = previous_if_taken is not True
            previous_if_taken = None
        if not taken:
            continue
        result = _evaluate_branches(branch["children"], variables)
        if result is not _NO_RESULT:
            return result
        if branch["value"] is not None:
            return _evaluate_value(branch["value"], variables)
    return _NO_RESULT


def _evaluate_value(value, variables):
    if value is None:
        return None
    return evaluate_acm_expression(value, variables)


def evaluate_conditional_function(func_elem, variables=None):
    """Evaluate a ``FType="Conditional"`` ``<Func>`` element without generating code."""
    if isinstance(func_elem, str):
        func_elem = ET.fromstring(func_elem)
    result = _evaluate_branches(build_conditional_branches(func_elem), variables or {})
    return None if result is _NO_RESULT else result
