"""aggregate node. Deterministic.

M1 (this file, Phase 2): wired via a plain edge from the single evaluator,
so the handler takes one `Finding`. Phase 3 changes this signature to
`list[Finding]` and rewires it via `add_fan_in_edges` across all four
evaluators — the framework requires >=2 sources for a fan-in group, so a
single-source "fan-in of one" isn't a legal stand-in; the signature change
at M2 is a real, expected revision, not a workaround.

The confidence threshold is hardcoded here for M1; Phase 3 moves it into
shared workflow state so the conditional edge can read a value that changed
at runtime, not at code-authoring time (see brief M2 acceptance test).
"""

from agent_framework import Executor, WorkflowContext, handler

from src.controls import CONTROLS
from src.models import Finding, FindingSet, FindingStatus

CONFIDENCE_THRESHOLD = 0.6


class AggregateExecutor(Executor):
    @handler
    async def aggregate(self, finding: Finding, ctx: WorkflowContext[FindingSet]) -> None:
        findings = [finding]
        coverage_ratio = len(findings) / len(CONTROLS)
        needs_review = any(
            f.status == FindingStatus.NEEDS_REVIEW or f.confidence < CONFIDENCE_THRESHOLD
            for f in findings
        )
        finding_set = FindingSet(
            findings=tuple(findings),
            coverage_ratio=coverage_ratio,
            needs_review=needs_review,
        )
        await ctx.send_message(finding_set)
