"""The budget's counting and stopping, offline (D39). The middleware wiring is exercised by lesson w3_step7."""

import pytest

from finsight.middleware.budget import BudgetExceeded, RunBudget


def test_under_budget_passes():
    b = RunBudget(max_usd=1.0, max_tool_calls=3)
    b.add_usage({"input_token_count": 1000, "output_token_count": 100}, "gpt-5.4")
    b.check()


def test_money_cap():
    b = RunBudget(max_usd=0.01)
    b.add_usage({"input_token_count": 10_000, "output_token_count": 1000}, "gpt-5.4")  # ≈ $0.04
    with pytest.raises(BudgetExceeded):
        b.check()


def test_tool_call_cap_sums_across_agents():
    b = RunBudget(max_tool_calls=2)
    b.tool_calls = 2  # two agents shared one budget
    with pytest.raises(BudgetExceeded):
        b.check()


def test_time_cap():
    b = RunBudget(max_seconds=0)
    with pytest.raises(BudgetExceeded):
        b.check()


def test_unknown_model_is_priced_as_main_not_free():
    b = RunBudget()
    b.add_usage({"input_token_count": 1_000_000}, "some-new-model")
    assert b.spent_usd > 0
