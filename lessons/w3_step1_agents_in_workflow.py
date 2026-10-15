"""Week 3, Step 1 (lesson): agents as workflow executors, with a conditional edge (book Ch 6, D31).

Router (nano, typed Route) → switch → either an answering agent, or a plain-code
"oos" executor that skips the LLM entirely. Then we look at what the downstream
agent was actually sent: MAF passes the WHOLE conversation along by default.

Run: uv run python lessons/w3_step1_agents_in_workflow.py ["question"]
"""

import asyncio
import sys
from typing import Literal

from agent_framework import (
    Agent, AgentExecutor, AgentExecutorResponse, Case, Default, WorkflowBuilder, WorkflowContext, executor,
)
from pydantic import BaseModel, Field
from typing_extensions import Never

from finsight.config import CHEAP_MODEL
from finsight.llm import AGENT_DEFAULTS, get_client


class Route(BaseModel):
    label: Literal["lookup", "analysis", "oos"] = Field(
        description="lookup: one figure from a company's 10-K. analysis: compare, judge or compute "
        "across figures. oos: not about a company's financial filings."
    )


router = AgentExecutor(Agent(
    client=get_client(CHEAP_MODEL), name="router", instructions="Label the user's question.",
    default_options=AGENT_DEFAULTS | {"response_format": Route},  # structured output, as in week 1
))
answerer = AgentExecutor(Agent(
    client=get_client(), name="answerer", instructions="Answer in one sentence from general knowledge.",
    default_options=AGENT_DEFAULTS,
))


@executor(id="oos")
async def out_of_scope(r: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output("Out of scope: FinSight answers questions about 10-K filings.")  # no LLM call


def label(r: AgentExecutorResponse) -> str:
    return Route.model_validate_json(r.agent_response.text).label  # the edge condition reads the typed output


workflow = (
    WorkflowBuilder(start_executor=router, output_from=[answerer, out_of_scope])
    .add_switch_case_edge_group(router, [
        Case(condition=lambda r: label(r) == "oos", target=out_of_scope),
        Default(target=answerer),  # lookup and analysis: same path in this lesson
    ])
    .build()
)


async def main(question: str) -> None:
    result = await workflow.run(question)
    for e in result:
        if e.type == "executor_completed" or e.type == "output":
            print(f"  [{e.type}] {getattr(e, 'executor_id', '')}")
    print("→", result.get_outputs()[-1] if isinstance(result.get_outputs()[-1], str) else result.get_outputs()[-1].text)
    # What did the answerer actually receive? Not just the question.
    if not isinstance(result.get_outputs()[-1], str):
        print("\nanswerer's context (context_mode='full', the default):")
        for m in answerer._full_conversation:
            print(f"  {m.role:9s} {m.text[:90]!r}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "What was Boeing's revenue in 2022?"))
