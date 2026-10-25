"""Week 3, Step 5 (lesson): Magentic, a manager plans, delegates and re-plans (book Ch 7).

Task: compare two companies' FY2022 effective tax rate. No FinanceBench question does this, so there is no
gold answer: we read the run, we don't score it. Specialist = the analyst; the manager tells each which filing.

Run: uv run python lessons/w3_step5_magentic.py
"""

import asyncio
import time
from pathlib import Path

from agent_framework import Agent
from agent_framework.orchestrations import MagenticBuilder

from finsight.llm import AGENT_DEFAULTS, get_client
from finsight.tools.calculator import calculator
from finsight.tools.filings import render_page
from finsight.tools.search_filings import make_search_filings

PROMPT = (Path(__file__).parents[1] / "src/finsight/prompts/analyst.md").read_text()
TASK = ("Compare Boeing's and Corning's effective tax rate in FY2022: what is each, and which is higher? "
        "The filings are BOEING_2022_10K and CORNING_2022_10K. Cite page numbers.")


def specialist(name: str, description: str) -> Agent:
    # description is what the manager reads when it picks who goes next.
    return Agent(client=get_client(), name=name, description=description, instructions=PROMPT,
                 tools=[make_search_filings(), render_page, calculator], default_options=AGENT_DEFAULTS)


async def main() -> None:
    manager = Agent(client=get_client(), name="manager", instructions="You coordinate analysts on SEC filing questions.")
    workflow = MagenticBuilder(
        participants=[specialist("boeing_analyst", "Reads Boeing's 10-K (BOEING_2022_10K) and reports figures with page numbers."),
                      specialist("corning_analyst", "Reads Corning's 10-K (CORNING_2022_10K) and reports figures with page numbers.")],
        manager_agent=manager,
        max_round_count=8, max_stall_count=2,  # cost guard for a lesson; the Terminations step does this properly
        output_from="all",
    ).build()
    start = time.monotonic()
    result = await workflow.run(TASK)
    for e in result:
        if e.type == "output":
            print(f"\n[{e.executor_id}] {str(getattr(e.data, 'text', e.data))[:500]}")
    print(f"\n{time.monotonic() - start:.0f} s")


asyncio.run(main())
