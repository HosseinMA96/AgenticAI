"""Week 3, Step 3 (lesson): concurrent agents + an aggregator (book Ch 7, D37).

Three copies of the analyst answer the same question in parallel. A plain-code aggregator
takes a majority vote on yes/no. The question: does voting fix the judgement misses?

Run: uv run python lessons/w3_step3_concurrent.py
"""

import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from agent_framework import Agent, AgentExecutorResponse
from agent_framework.orchestrations import ConcurrentBuilder

from finsight.dataset import SPLITS
from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.models import Answer
from finsight.pricing import cost_usd
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

# Two yes/no judgement questions every config got wrong (week 3 measure), plus one it gets right, as a control.
IDS = ["financebench_id_00790", "financebench_id_00005", "financebench_id_00678"]
N = 3
PROMPT = (Path(__file__).parents[1] / "src/finsight/prompts/analyst.md").read_text() + \
    "\nStart your `answer` with Yes or No."


def analyst(i: int) -> Agent:
    return Agent(client=get_client(), name=f"analyst_{i}", instructions=PROMPT,
                 tools=[make_search_filings(), render_page, calculator],
                 default_options=AGENT_DEFAULTS | {"response_format": Answer})


def vote(results: list[AgentExecutorResponse]) -> dict:
    """The aggregator: plain code, no LLM. Runs once, after the fan-in barrier has all N answers."""
    answers = [Answer.model_validate_json(r.agent_response.text) for r in results]
    votes = [a.answer.split()[0].strip(".,—-").lower() for a in answers]
    cost = sum(cost_usd("gpt-5.4", r.agent_response.usage_details or {}) for r in results)
    return {"votes": votes, "winner": Counter(votes).most_common(1)[0][0], "answers": answers, "cost": cost}


async def main() -> None:
    rows = {r["id"]: r for r in map(json.loads, (SPLITS / "dev.jsonl").open())}
    for qid in IDS:
        row = rows[qid]
        workflow = ConcurrentBuilder(participants=[analyst(i) for i in range(N)]).with_aggregator(vote).build()
        start = time.monotonic()
        result = (await workflow.run(f"Filing: {row['doc_name']}\n\nQuestion: {row['question']}")).get_outputs()[-1]
        print(f"\n=== {qid}: {row['question'][:90]}")
        for a in result["answers"]:
            print(f"  - {a.answer[:150]!r}")
        print(f"  votes={result['votes']} → {result['winner'].upper()}   gold: {row['answer'][:60]!r}")
        print(f"  ${result['cost']:.3f}, {time.monotonic() - start:.0f} s for all {N} in parallel")


asyncio.run(main())
