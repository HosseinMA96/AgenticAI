"""A whole-run budget (D39). MAF's own limits reset on every agent turn (lesson w3_step6);
this one object is shared by every agent in a run, so it sees the sum.

Usage: budget = RunBudget(max_usd=1.0, max_tool_calls=40, max_seconds=120); then give each agent
`middleware=budget.middleware()`. Check `budget.spent_usd` etc. afterwards.
"""

import time

from agent_framework import ChatContext, FunctionInvocationContext, chat_middleware, function_middleware

from finsight.config import MAIN_MODEL
from finsight.pricing import PRICES, cost_usd


class BudgetExceeded(Exception):
    """Raised before the call that would go over, so the overrun is at most one model call."""


class RunBudget:
    def __init__(self, *, max_usd: float | None = None, max_tool_calls: int | None = None,
                 max_seconds: float | None = None) -> None:
        self.max_usd, self.max_tool_calls, self.max_seconds = max_usd, max_tool_calls, max_seconds
        self.spent_usd, self.tool_calls = 0.0, 0
        self.started = time.monotonic()  # the clock starts when the budget is made, so make it per run

    def check(self) -> None:
        if self.max_usd is not None and self.spent_usd >= self.max_usd:
            raise BudgetExceeded(f"spent ${self.spent_usd:.3f} of ${self.max_usd:.3f}")
        if self.max_tool_calls is not None and self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded(f"{self.tool_calls} tool calls of {self.max_tool_calls}")
        if self.max_seconds is not None and time.monotonic() - self.started >= self.max_seconds:
            raise BudgetExceeded(f"{time.monotonic() - self.started:.0f} s of {self.max_seconds:.0f} s")

    def add_usage(self, usage: dict | None, model: str | None) -> None:
        model = model if model in PRICES else MAIN_MODEL
        self.spent_usd += cost_usd(model, usage or {})

    def middleware(self) -> list:
        @chat_middleware
        async def count_model_calls(context: ChatContext, call_next) -> None:
            self.check()  # before: refuse to start a call once over budget
            await call_next()
            if context.result is not None and hasattr(context.result, "usage_details"):
                self.add_usage(context.result.usage_details, context.options.get("model"))

        @function_middleware
        async def count_tool_calls(context: FunctionInvocationContext, call_next) -> None:
            self.check()
            self.tool_calls += 1
            await call_next()

        return [count_model_calls, count_tool_calls]
