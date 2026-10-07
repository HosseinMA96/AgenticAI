"""Calculator tool: safe arithmetic on an expression the model writes.

The expression comes from the model, and the model can be steered (e.g. by an
injection in a filing), so we never eval() it. We parse it into a syntax tree
and allow only numbers and arithmetic. Everything else is rejected (DECISIONS.md D4).
"""

import ast
import operator
from typing import Annotated

from agent_framework import tool
from pydantic import Field

# The allow-list. Anything not in here is rejected, so new syntax is denied by default.
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_MAX_LEN = 200  # a financial formula is short; a long input is a mistake or an attack
_MAX_EXPONENT = 100  # CAGR needs ** (1/years); 10**10**10 would freeze the process


def evaluate(expression: str) -> float:
    """Evaluate an arithmetic expression. Raises ValueError on anything not allowed."""
    if len(expression) > _MAX_LEN:
        raise ValueError(f"expression longer than {_MAX_LEN} characters")
    tree = ast.parse(expression, mode="eval")  # parses only; nothing runs
    return float(_eval_node(tree.body))


def _eval_node(node: ast.AST) -> float:
    # Walk the tree ourselves; each branch is one allowed kind of node.
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"exponent larger than {_MAX_EXPONENT}")
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"not allowed: {type(node).__name__}")


@tool
def calculator(
    expression: Annotated[
        str, Field(description="Arithmetic only, e.g. '(2413.7 / 18902.1) * 100' or '(150/100)**(1/5) - 1'")
    ],
) -> str:
    """Exact arithmetic. Supports + - * / ** and brackets. Use it for every calculation instead of doing math yourself."""
    try:
        return str(evaluate(expression))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        # Return the error as text so the model can see it and fix its expression.
        return f"error: {e}"
