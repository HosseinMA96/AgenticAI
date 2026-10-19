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
from typing_extensions import Never

from finsight.agents.analyst import ask, build_analyst
from finsight.agents.router import build_router, route
from finsight.agents.verifier import build_verifier, verify
from finsight.config import ANALYSIS_REASONING
from finsight.models import Verdict
from finsight.orchestration.messages import (
    Checked, Draft, Question, Report, ReviewDecision, ReviewRequest, Routed,
)

CHECKPOINTS = Path(__file__).parents[3] / "checkpoints"  # gitignored

# Checkpoints are pickled, and MAF only unpickles listed types. A missing type fails
# silently (found in BcdrSequential), so every message type and everything inside it is listed.
CHECKPOINT_TYPES = [f"finsight.orchestration.messages:{n}" for n in (
    "Question", "Routed", "Draft", "Checked", "ReviewRequest", "ReviewDecision", "Report")
] + [f"finsight.models:{n}" for n in ("Answer", "Route", "Verdict")]


class RouterNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="router")
        self.agent = build_router()

    @handler
    async def run(self, q: Question, ctx: WorkflowContext[Routed]) -> None:
        response = await route(self.agent, q.doc_name, q.question)
        await ctx.send_message(Routed(question=q, route=response.value))


@executor(id="out_of_scope")
async def out_of_scope(m: Routed, ctx: WorkflowContext[Never, Report]) -> None:
    await ctx.yield_output(Report(question=m.question, status="oos", route=m.route))  # no research, no cost


class ResearchNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="research")
        self.agent = build_analyst()  # no edgar MCP here: the analyst almost never used it (D16)

    @handler
    async def first(self, m: Routed, ctx: WorkflowContext[Draft]) -> None:
        await self._attempt(m, m.question.question, 1, ctx)

    @handler  # MAF picks the handler by message type: a Checked arriving here is a retry
    async def retry(self, c: Checked, ctx: WorkflowContext[Draft]) -> None:
        m = c.draft.routed
        prompt = (f"{m.question.question}\n\nA checker rejected your previous answer: {c.verdict.problem}\n"
                  "Look at the evidence again and answer.")
        await self._attempt(m, prompt, 2, ctx)

    async def _attempt(self, m: Routed, prompt: str, attempt: int, ctx: WorkflowContext[Draft]) -> None:
        # The one place the label changes the path: analysis gets reasoning, lookup doesn't (D31).
        effort = ANALYSIS_REASONING if m.route.label == "analysis" else None
        response = await ask(self.agent, m.question.doc_name, prompt, reasoning=effort)
        await ctx.send_message(Draft(routed=m, answer=response.value, attempt=attempt))


class VerifierNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="verifier")
        self.agent = build_verifier()

    @handler
    async def check(self, d: Draft, ctx: WorkflowContext[Checked]) -> None:
        q = d.routed.question
        if not d.answer.citations:  # nothing to check, so no model call; it fails like any unsupported answer
            verdict = Verdict(check="No cited pages.", supported=False,
                              problem="The answer cites no pages. Find the pages that state it.")
        else:
            verdict = (await verify(self.agent, q.doc_name, q.question, d.answer)).value
        await ctx.send_message(Checked(draft=d, verdict=verdict))


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
            reviewer_note=d.note,
        ))


class ReportNode(Executor):
    """The single exit for answered questions, so later steps (saving, formatting) have one place to go."""

    def __init__(self) -> None:
        super().__init__(id="report")

    @handler
    async def verified(self, c: Checked, ctx: WorkflowContext[Never, Report]) -> None:
        d = c.draft
        await ctx.yield_output(Report(question=d.routed.question, status="verified", route=d.routed.route,
                                      answer=d.answer, verdict=c.verdict, attempts=d.attempt))

    @handler
    async def reviewed(self, r: Report, ctx: WorkflowContext[Never, Report]) -> None:
        await ctx.yield_output(r)


def build_workflow(checkpoint_storage: FileCheckpointStorage | None = None):
    router, research, verifier = RouterNode(), ResearchNode(), VerifierNode()
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
    workflow = build_workflow(checkpoint_storage())
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
    print(result.get_outputs()[-1].model_dump_json(indent=2, exclude={"question"}))


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) != 3:
        sys.exit('usage: python -m finsight.orchestration.workflow <FILING_ID> "<question>"')
    asyncio.run(_main(sys.argv[1], sys.argv[2]))
