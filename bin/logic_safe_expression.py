"""Restricted evaluators for expressions that come from ACM libraries and ACM
parameter values.

Library XML files and ACM parameters can originate from shared project
archives or third-party libraries, so neither must ever reach ``eval()``.
"""

import ast
import math
import re

__all__ = ['UnsafeExpressionError', 'condition_variable_names', 'evaluate_arithmetic', 'evaluate_include_condition']

_MAX_EXPRESSION_LENGTH = 1000
_MAX_EXPONENT = 64
_MAX_NESTING = 32
_MAX_MAGNITUDE = 1e18


class UnsafeExpressionError(ValueError):
    """Raised when an expression is malformed or uses unsupported syntax."""


# ---------------------------------------------------------------------------
# ACM symbol IncludeCondition
#
# Grammar (case-insensitive keywords):
#   expr       := or_expr
#   or_expr    := and_expr ('OR' and_expr)*
#   and_expr   := not_expr ('AND' not_expr)*
#   not_expr   := 'NOT' not_expr | comparison
#   comparison := operand (cmp_op operand)?
#   operand    := NUMBER | STRING | '{' NAME '}' | 'Always' | 'True' | 'False' | '(' expr ')'
#   cmp_op     := '=' | '==' | '<>' | '!=' | '<' | '<=' | '>' | '>='
#
# Placeholders are resolved to values, never re-parsed as syntax.
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<var>\{[^{}]+\})
  | (?P<number>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)
  | (?P<string>"[^"]*"|'[^']*')
  | (?P<op><>|!=|==|<=|>=|=|<|>)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
""", re.VERBOSE)

_KEYWORDS = {'AND', 'OR', 'NOT'}
_BOOLEAN_WORDS = {'ALWAYS': True, 'TRUE': True, 'FALSE': False, 'NEVER': False}


def _tokenize(condition):
    tokens = []
    position = 0
    while position < len(condition):
        match = _TOKEN_RE.match(condition, position)
        if not match:
            raise UnsafeExpressionError(f'Unexpected character {condition[position]!r} at position {position}')
        kind = match.lastgroup
        text = match.group(kind)
        position = match.end()
        if kind == 'ws':
            continue
        if kind == 'word':
            upper = text.upper()
            if upper in _KEYWORDS:
                tokens.append((upper, text))
            elif upper in _BOOLEAN_WORDS:
                tokens.append(('value', _BOOLEAN_WORDS[upper]))
            else:
                raise UnsafeExpressionError(f'Unsupported identifier {text!r}')
        elif kind == 'number':
            tokens.append(('value', _to_number(text)))
        elif kind == 'string':
            tokens.append(('value', text[1:-1]))
        elif kind == 'var':
            tokens.append(('var', text[1:-1].strip()))
        else:
            tokens.append((kind, text))
    return tokens


def _to_number(text):
    try:
        return int(text)
    except ValueError:
        value = float(text)
        if not math.isfinite(value):
            raise UnsafeExpressionError(f'Non-finite number {text!r}')
        return value


def _coerce_parameter(value):
    """Turn a raw ACM parameter value into a plain number, bool, string or None."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    text = str(value).strip()
    if text == '':
        return text
    if re.fullmatch(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?', text):
        return _to_number(text)
    return text


def _compare(left, op, right):
    if left is None or right is None:
        if op in ('=', '=='):
            return left is right
        if op in ('<>', '!='):
            return left is not right
        return False
    if isinstance(left, str) != isinstance(right, str):
        # A quoted string never equals (or orders against) a number.
        return op in ('<>', '!=')
    if op in ('=', '=='):
        return left == right
    if op in ('<>', '!='):
        return left != right
    try:
        if op == '<':
            return left < right
        if op == '<=':
            return left <= right
        if op == '>':
            return left > right
        if op == '>=':
            return left >= right
    except TypeError:
        return False
    raise UnsafeExpressionError(f'Unsupported operator {op!r}')


class _ConditionParser:

    def __init__(self, tokens, variables):
        self.tokens = tokens
        self.index = 0
        self.depth = 0
        self.variables = variables

    def parse(self):
        if not self.tokens:
            raise UnsafeExpressionError('Empty condition')
        result = self._or()
        if self.index != len(self.tokens):
            raise UnsafeExpressionError(f'Unexpected token {self.tokens[self.index][1]!r}')
        return bool(result)

    def _peek(self):
        return self.tokens[self.index][0] if self.index < len(self.tokens) else None

    def _take(self, kind=None):
        if self.index >= len(self.tokens):
            raise UnsafeExpressionError('Unexpected end of condition')
        token = self.tokens[self.index]
        if kind is not None and token[0] != kind:
            raise UnsafeExpressionError(f'Expected {kind}, got {token[1]!r}')
        self.index += 1
        return token

    def _or(self):
        result = self._and()
        while self._peek() == 'OR':
            self._take()
            right = self._and()
            result = bool(result) or bool(right)
        return result

    def _and(self):
        result = self._not()
        while self._peek() == 'AND':
            self._take()
            right = self._not()
            result = bool(result) and bool(right)
        return result

    def _not(self):
        if self._peek() == 'NOT':
            self._take()
            self.depth += 1
            if self.depth > _MAX_NESTING:
                raise UnsafeExpressionError('Condition nested too deeply')
            result = not bool(self._not())
            self.depth -= 1
            return result
        return self._comparison()

    def _comparison(self):
        left = self._operand()
        if self._peek() == 'op':
            op = self._take()[1]
            right = self._operand()
            return _compare(left, op, right)
        return left

    def _operand(self):
        kind, value = self._take()
        if kind == 'value':
            return value
        if kind == 'var':
            return _coerce_parameter(self.variables(value) if callable(self.variables) else self.variables.get(value))
        if kind == 'lparen':
            self.depth += 1
            if self.depth > _MAX_NESTING:
                raise UnsafeExpressionError('Condition nested too deeply')
            result = self._or()
            self._take('rparen')
            self.depth -= 1
            return result
        raise UnsafeExpressionError(f'Unexpected token {value!r}')


def evaluate_include_condition(condition, variables):
    """Evaluate an ACM HMI symbol ``IncludeCondition``.

    Args:
        condition: Condition text, e.g. ``"{SymbolStyle} = 0 AND ({SymbolType} = 0 OR {SymbolType} = 1)"``.
        variables: Mapping of placeholder name to value, or a callable taking the name.

    Returns:
        bool

    Raises:
        UnsafeExpressionError: if the condition is malformed or uses unsupported syntax.
    """
    if condition is None:
        raise UnsafeExpressionError('Empty condition')
    condition = str(condition)
    if len(condition) > _MAX_EXPRESSION_LENGTH:
        raise UnsafeExpressionError('Condition too long')
    try:
        return _ConditionParser(_tokenize(condition), variables).parse()
    except RecursionError:
        raise UnsafeExpressionError('Condition nested too deeply')


def condition_variable_names(condition):
    """Return the ``{Name}`` placeholders used in a condition, in order of first use."""
    names = []
    for match in re.finditer(r'\{([^{}]+)\}', condition or ''):
        name = match.group(1).strip()
        if name not in names:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Handlebar arithmetic, e.g. "41 + 12 * 2" or "max(3, 4) - 1"
# ---------------------------------------------------------------------------

_ARITHMETIC_FUNCTIONS = {
    'abs': abs, 'round': round, 'max': max, 'min': min, 'int': int, 'float': float,
}

_BINARY_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
}

_UNARY_OPERATORS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}


def _check_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeExpressionError('Non-numeric value')
    if isinstance(value, float) and not math.isfinite(value):
        raise UnsafeExpressionError('Non-finite value')
    if abs(value) > _MAX_MAGNITUDE:
        raise UnsafeExpressionError('Value out of range')
    return value


def _eval_arithmetic_node(node):
    if isinstance(node, ast.Expression):
        return _eval_arithmetic_node(node.body)
    if isinstance(node, ast.Constant):
        return _check_number(node.value)
    if isinstance(node, ast.BinOp):
        left = _eval_arithmetic_node(node.left)
        right = _eval_arithmetic_node(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT:
                raise UnsafeExpressionError('Exponent out of range')
            return _check_number(left ** right)
        operator = _BINARY_OPERATORS.get(type(node.op))
        if operator is None:
            raise UnsafeExpressionError(f'Unsupported operator {type(node.op).__name__}')
        return _check_number(operator(left, right))
    if isinstance(node, ast.UnaryOp):
        operator = _UNARY_OPERATORS.get(type(node.op))
        if operator is None:
            raise UnsafeExpressionError(f'Unsupported operator {type(node.op).__name__}')
        return _check_number(operator(_eval_arithmetic_node(node.operand)))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ARITHMETIC_FUNCTIONS or node.keywords:
            raise UnsafeExpressionError('Unsupported function call')
        args = [_eval_arithmetic_node(arg) for arg in node.args]
        return _check_number(_ARITHMETIC_FUNCTIONS[node.func.id](*args))
    raise UnsafeExpressionError(f'Unsupported syntax {type(node).__name__}')


def evaluate_arithmetic(expression):
    """Evaluate a numeric expression built only from numbers, + - * / // % **,
    parentheses and abs/round/max/min/int/float calls.

    Raises:
        UnsafeExpressionError: for anything else (names, attributes, strings, ...).
    """
    expression = str(expression).strip()
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise UnsafeExpressionError('Expression too long')
    try:
        tree = ast.parse(expression, mode='eval')
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        raise UnsafeExpressionError(f'Invalid expression: {e}')
    try:
        return _eval_arithmetic_node(tree)
    except (ArithmeticError, TypeError, ValueError, RecursionError) as e:
        if isinstance(e, UnsafeExpressionError):
            raise
        raise UnsafeExpressionError(f'Evaluation failed: {e}')
