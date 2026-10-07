"""Offline tests for the calculator tool. No model, no network."""

import pytest

from finsight.tools.calculator import calculator, evaluate


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2413.7 / 18902.1 * 100", 12.76948),  # net margin
        ("(150 / 100) ** (1 / 5) - 1", 0.08447),  # CAGR over 5 years
        ("(10 + 20 + 30) / 3", 20.0),  # average
        ("-5 + 2", -3.0),  # unary minus
    ],
)
def test_finance_math(expression, expected):
    assert evaluate(expression) == pytest.approx(expected, rel=1e-4)


@pytest.mark.parametrize(
    "attack",
    [
        "__import__('os').system('echo pwned')",  # code execution
        "open('/etc/passwd').read()",  # file access
        "x + 1",  # names
        "(1).__class__",  # attribute access
        "True + 1",  # bools are not numbers here
        "9 ** 9 ** 9",  # huge exponent would freeze the process
        "1" * 201,  # overly long input
    ],
)
def test_rejects_anything_not_arithmetic(attack):
    with pytest.raises((ValueError, SyntaxError)):
        evaluate(attack)


def test_tool_returns_errors_as_text():
    # The tool wrapper must never crash the agent loop; the model reads the error and retries.
    assert calculator.func("1 / 0").startswith("error:")
    assert calculator.func("__import__('os')").startswith("error:")
