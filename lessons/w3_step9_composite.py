"""Week 3, Step 9 (lesson): a composite termination: four exits, one clear outcome (book Ch 7, 2.3-2.5).

Exits: approved (keyword), max_rounds, budget (D39), cancel (step 8). Each ends the chat differently:
the first two end it politely, the budget raises BudgetExceeded, cancel raises CancelledError.
`run_chat` turns all four into one string. If approval and budget land together, approved wins:
the keyword is checked on a finished turn, the budget only refuses the NEXT call (user's call).

Run: uv run python lessons/w3_step9_composite.py
"""

import asyncio

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.middleware.budget import BudgetExceeded, RunBudget

MAKER = "You write one short sentence about the weather."
APPROVING = "Reply with exactly: APPROVED"
STUBBORN = "Reply with one short objection to the previous message. Never say APPROVED."


async def run_chat(checker_prompt: str, *, max_rounds: int, budget: RunBudget, cancel_after: float | None = None) -> str:
    agents = [Agent(client=get_client(CHEAP_MODEL), name=n, instructions=p, default_options=AGENT_DEFAULTS,
                    middleware=budget.middleware()) for n, p in (("maker", MAKER), ("checker", checker_prompt))]
    workflow = GroupChatBuilder(
        participants=agents, max_rounds=max_rounds,
        selection_func=lambda s: "maker" if s.current_round % 2 == 0 else "checker",
        termination_condition=lambda conv: "APPROVED" in conv[-1].text and conv[-1].author_name == "checker",
    ).build()
    task = asyncio.create_task(workflow.run("Start."))
    if cancel_after:
        asyncio.get_running_loop().call_later(cancel_after, task.cancel)
    try:
        result = await task
    except BudgetExceeded as e:
        return f"budget ({e})"
    except asyncio.CancelledError:
        return "cancelled"
    # The two polite exits differ only in the orchestrator's closing line (seen in step 4).
    notice = result.get_outputs()[-1].text
    return "max_rounds" if "maximum number of rounds" in notice else "approved"


async def main() -> None:
    cases = {
        "approved": dict(checker_prompt=APPROVING, max_rounds=6, budget=RunBudget(max_usd=0.5)),
        "max_rounds": dict(checker_prompt=STUBBORN, max_rounds=4, budget=RunBudget(max_usd=0.5)),
        "budget": dict(checker_prompt=STUBBORN, max_rounds=20, budget=RunBudget(max_usd=0.0003)),
        "cancelled": dict(checker_prompt=STUBBORN, max_rounds=40, budget=RunBudget(max_usd=0.5), cancel_after=4),
    }
    for expected, kw in cases.items():
        outcome = await run_chat(**kw)
        print(f"expected {expected:11s} → got {outcome}")


asyncio.run(main())
