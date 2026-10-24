"""The FinSight workflow (D31, D32, D34):

    Router ──oos──► out_of_scope ───────────────────────────────► (Report)
       └─lookup/analysis─► Research ─► Verifier ─supported──► report ──► (Report)
                              ▲           ├─failed, 1st try─┘ (back to Research, with the problem)
                              └───────────┘
                                          └─failed, 2nd try─► human_review ─► report

    uv run python -m finsight.orchestration.workflow <FILING_ID> "<question>"

Each node calls an existing function and sends a typed message (messages.py), so every
agent sees only what it is handed. Checkpoints are written after each superstep.
"""

from pathlib import Path

from agent_framework import (
    Case, Default, Executor, FileCheckpointStorage, WorkflowBuilder, WorkflowContext, executor, handler,
    response_handler,
)
from agent_framework.exceptions import ChatClientException
from pydantic import ValidationError
from typing_extensions import Never

from finsight.agents.analyst import ask, build_analyst, edgar_stdio
from finsight.agents.router import build_router, route
from finsight.agents.verifier import build_verifier, verify
from finsight.config import ANALYSIS_REASONING, CHEAP_MODEL, MAIN_MODEL
from finsight.evidence import unread_citations
from finsight.limits import limit_hit
from finsight.models import Verdict
from finsight.orchestration.concurrent import ask_concurrent, build_concurrent
from finsight.orchestration.handoff import ask_handoff, build_handoff
from finsight.orchestration.maker_checker import ask_maker_checker, build_maker_checker
from finsight.orchestration.messages import (
    Checked, Draft, Question, Report, ReviewDecision, ReviewRequest, Routed, Step,
)

CHECKPOINTS = Path(__file__).parents[3] / "checkpoints"  # gitignored

# Checkpoints are pickled, and MAF only unpickles listed types. A missing type fails
# silently (found in BcdrSequential), so every message type and everything inside it is listed.
CHECKPOINT_TYPES = [f"finsight.orchestration.messages:{n}" for n in (
    "Step", "Question", "Routed", "Draft", "Checked", "ReviewRequest", "ReviewDecision", "Report")
] + [f"finsight.models:{n}" for n in ("Answer", "Route", "Verdict")]


def _step(agent: str, model: str, response) -> Step:
    tools = [c.name for m in response.messages for c in m.contents if c.type == "function_call"]
    return Step(agent=agent, model=model, usage=dict(response.usage_details or {}), tools_used=tools)


class RouterNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="router")
        self.agent = build_router()

    @handler
    async def run(self, q: Question, ctx: WorkflowContext[Routed]) -> None:
        response = await route(self.agent, q.doc_name, q.question)
        await ctx.send_message(Routed(question=q, route=response.value, steps=[_step("router", CHEAP_MODEL, response)]))


@executor(id="out_of_scope")
async def out_of_scope(m: Routed, ctx: WorkflowContext[Never, Report]) -> None:
    await ctx.yield_output(Report(question=m.question, status="oos", route=m.route, steps=m.steps))  # no research, no cost


class ResearchNode(Executor):
    def __init__(self, *tools, mode: str = "router") -> None:
        """tools: extra tools such as the edgar MCP. The single-agent baseline had edgar, so the
        fair comparison passes it too; leaving it out is a separate variant (TODO, Measure).
        mode: "router" = one analyst, the Router's label sets reasoning (D31);
              "handoff" = quick hands off to deep, the model decides (D36);
              "makerchecker" = analyst and a critic loop in a group chat;
              "concurrent" = 3 analysts, plain-code vote (D37)."""
        super().__init__(id="research")
        self.tools, self.mode = tools, mode
        self.agent = build_analyst(*tools) if mode == "router" else None

    @handler
    async def first(self, m: Routed, ctx: WorkflowContext[Draft]) -> None:
        await self._attempt(m, m.question.question, 1, m.steps, ctx)

    @handler  # MAF picks the handler by message type: a Checked arriving here is a retry
    async def retry(self, c: Checked, ctx: WorkflowContext[Draft]) -> None:
        m = c.draft.routed
        prompt = (f"{m.question.question}\n\nA checker rejected your previous answer: {c.verdict.problem}\n"
                  "Look at the evidence again and answer.")
        try:
            await self._attempt(m, prompt, 2, c.steps, ctx)
        except ChatClientException as e:
            # Criticism can rattle the model into an answer that breaks Answer's rules (e.g. "not found"
            # plus a value; dev run workflow-edgar-r1, financebench_id_00591). A broken retry shouldn't
            # crash the question: keep the first answer. Anything else (e.g. a 429) still raises.
            if not isinstance(e.__cause__, ValidationError):
                raise
            await ctx.send_message(Draft(routed=m, answer=c.draft.answer, attempt=2, steps=c.steps))

    async def _attempt(self, m: Routed, prompt: str, attempt: int, steps: list[Step], ctx: WorkflowContext[Draft]) -> None:
        if self.mode == "handoff":
            # A fresh handoff workflow per attempt: its conversation is per-run state.
            answer, response, who = await ask_handoff(build_handoff(*self.tools), m.question.doc_name, prompt)
        elif self.mode == "makerchecker":
            answer, response, who = await ask_maker_checker(build_maker_checker(*self.tools), m.question.doc_name, prompt)
        elif self.mode == "concurrent":
            answer, response, who = await ask_concurrent(build_concurrent(*self.tools), m.question.doc_name, prompt)
        else:
            # The one place the label changes the path: analysis gets reasoning, lookup doesn't (D31).
            effort = ANALYSIS_REASONING if m.route.label == "analysis" else None
            response = await ask(self.agent, m.question.doc_name, prompt, reasoning=effort)
            answer, who = response.value, ""
        step = _step("research", MAIN_MODEL, response).model_copy(update={
            "detail": who, "limit_hit": limit_hit(response), "unread_citations": unread_citations(answer.citations, response)})
        await ctx.send_message(Draft(routed=m, answer=answer, attempt=attempt, steps=[*steps, step]))


class VerifierNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="verifier")
        self.agent = build_verifier()

    @handler
    async def check(self, d: Draft, ctx: WorkflowContext[Checked]) -> None:
        q, steps = d.routed.question, d.steps
        if not d.answer.citations:  # nothing to check, so no model call; it fails like any unsupported answer
            verdict = Verdict(check="No cited pages.", supported=False,
                              problem="The answer cites no pages. Find the pages that state it.")
        else:
            response = await verify(self.agent, q.doc_name, q.question, d.answer)
            verdict, steps = response.value, [*steps, _step("verifier", MAIN_MODEL, response)]
        await ctx.send_message(Checked(draft=d, verdict=verdict, steps=steps))


class HumanReviewNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="human_review")

    @handler
    async def ask_human(self, c: Checked, ctx: WorkflowContext) -> None:
        # Pauses the run. The caller answers with workflow.run(responses={request_id: ReviewDecision}).
        await ctx.request_info(ReviewRequest(checked=c), ReviewDecision)

    @response_handler
    async def resolve(self, req: ReviewRequest, d: ReviewDecision, ctx: WorkflowContext[Report]) -> None:
        c = req.checked
        await ctx.send_message(Report(
            question=c.draft.routed.question, status="human_approved" if d.approved else "human_rejected",
            route=c.draft.routed.route, answer=c.draft.answer, verdict=c.verdict, attempts=c.draft.attempt,
            reviewer_note=d.note, steps=c.steps,
        ))


class ReportNode(Executor):
    """The single exit for answered questions, so later steps (saving, formatting) have one place to go."""

    def __init__(self) -> None:
        super().__init__(id="report")

    @handler
    async def verified(self, c: Checked, ctx: WorkflowContext[Never, Report]) -> None:
        d = c.draft
        await ctx.yield_output(Report(question=d.routed.question, status="verified", route=d.routed.route,
                                      answer=d.answer, verdict=c.verdict, attempts=d.attempt, steps=c.steps))

    @handler
    async def reviewed(self, r: Report, ctx: WorkflowContext[Never, Report]) -> None:
        await ctx.yield_output(r)


def build_workflow(*research_tools, research: str = "router", checkpoint_storage: FileCheckpointStorage | None = None):
    """research: "router" or "handoff" (see ResearchNode). With handoff, the Router still blocks oos."""
    router, research, verifier = RouterNode(), ResearchNode(*research_tools, mode=research), VerifierNode()
    human, report = HumanReviewNode(), ReportNode()
    return (
        WorkflowBuilder(start_executor=router, name="finsight", checkpoint_storage=checkpoint_storage,
                        output_from=[out_of_scope, report])
        .add_switch_case_edge_group(router, [
            Case(condition=lambda m: m.route.label == "oos", target=out_of_scope),
            Default(target=research),
        ])
        .add_edge(research, verifier)
        .add_switch_case_edge_group(verifier, [
            Case(condition=lambda c: c.verdict.supported, target=report),
            Case(condition=lambda c: c.draft.attempt == 1, target=research),  # one retry before a human (D31)
            Default(target=human),
        ])
        .add_edge(human, report)
        .build()
    )


def checkpoint_storage() -> FileCheckpointStorage:
    CHECKPOINTS.mkdir(exist_ok=True)
    return FileCheckpointStorage(CHECKPOINTS, allowed_checkpoint_types=CHECKPOINT_TYPES)


async def _main(doc_name: str, question: str) -> None:
    async with edgar_stdio() as edgar:
        workflow = build_workflow(edgar, checkpoint_storage=checkpoint_storage())
        result = await workflow.run(Question(doc_name=doc_name, question=question))
        # A paused run returns with a pending request; answer it in the terminal and resume.
        while requests := result.get_request_info_events():
            req = requests[0]
            c = req.data.checked
            print(f"\n⚠️  Failed verification twice.\n  answer: {c.draft.answer.answer}\n  problem: {c.verdict.problem}")
            approved = input("  Approve anyway? [y/N] ").strip().lower() == "y"
            note = input("  Note: ").strip()
            result = await workflow.run(responses={req.request_id: ReviewDecision(approved=approved, note=note)})
    for e in result:
        if e.type == "executor_completed":
            print(f"  ✓ {e.executor_id}")
    print(result.get_outputs()[-1].model_dump_json(indent=2, exclude={"question", "steps"}))


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 3:
        sys.exit('usage: python -m finsight.orchestration.workflow <FILING_ID> "<question>"')
    asyncio.run(_main(sys.argv[1], sys.argv[2]))
