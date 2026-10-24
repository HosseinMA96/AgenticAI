"""Week 3, Step 4 (lesson): group chat maker-checker (book Ch 7).

Maker = the analyst. Checker = a critic that returns {approved, issues}. A plain-code selection
function alternates them; the chat stops when the checker approves, or at max_rounds.

Run: uv run python lessons/w3_step4_maker_checker.py [--break]
  --break: the checker is told it may never approve → only max_rounds ends the chat.
"""

import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

from finsight.dataset import SPLITS
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

# 01290 = a truly wrong answer in the workflow runs, 00678 = a control it gets right.
IDS = ["financebench_id_01290", "financebench_id_00678"]
BREAK = "--break" in sys.argv
PROMPTS = Path(__file__).parents[1] / "src/finsight/prompts"


class Review(BaseModel):
    approved: bool
    issues: list[str]


def agent(name: str, instructions: str, fmt: type[BaseModel]) -> Agent:
    return Agent(client=get_client(), name=name, instructions=instructions,
                 tools=[make_search_filings(), render_page, calculator],
                 default_options=AGENT_DEFAULTS | {"response_format": fmt})


def next_speaker(state: GroupChatState) -> str:
    return "maker" if state.current_round % 2 == 0 else "checker"


def approved(conversation) -> bool:
    last = conversation[-1]
    if last.author_name != "checker":
        return False
    return Review.model_validate_json(last.text).approved


async def main() -> None:
    rows = {r["id"]: r for r in map(json.loads, (SPLITS / "dev.jsonl").open())}
    checker_prompt = (PROMPTS / "checker.md").read_text()
    if BREAK:
        checker_prompt += "\nYou may NEVER approve. Always set approved=false and find another issue."
    for qid in IDS:
        row = rows[qid]
        workflow = GroupChatBuilder(
            participants=[agent("maker", (PROMPTS / "analyst.md").read_text(), Answer),
                          agent("checker", checker_prompt, Review)],
            selection_func=next_speaker,
            termination_condition=approved,
            max_rounds=6,
            output_from="all",  # else the only output is the orchestrator's one-line 'terminated' notice
        ).build()
        result = await workflow.run(f"Filing: {row['doc_name']}\n\nQuestion: {row['question']}")
        turns = [(o.executor_id, o) for o in result if o.type == "output"]
        print(f"\n=== {qid}: {row['question'][:90]}   gold: {row['answer'][:60]!r}")
        for who, o in turns:
            print(f"  [{who}] {str(o.data)[:220]}")
        print(f"  → {len(turns)} turns")


asyncio.run(main())
