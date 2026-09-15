"""aggregate node — the fan-in barrier. Deterministic.

Phase 3: now wired via `add_fan_in_edges` across all four evaluators (see
graph.py), so this handler receives the real `list[Finding]` the framework
assembles once every source has completed for this superstep — that's the
signature change flagged as coming in Phase 2's aggregate.py docstring.

The confidence threshold is no longer hardcoded: it's read from shared
workflow state (set by `ingest` from the initial `RunRequest`), so the M2
acceptance test — changing the threshold changes the routed branch — is
possible without touching this file.
"""

from agent_framework import Executor, WorkflowContext, handler

from src.controls import CONTROLS
from src.models import Finding, FindingSet, FindingStatus

DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class AggregateExecutor(Executor):
    @handler
    async def aggregate(self, findings: list[Finding], ctx: WorkflowContext[FindingSet]) -> None:
        threshold = ctx.get_state("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        coverage_ratio = len(findings) / len(CONTROLS)
        needs_review = any(
            f.status == FindingStatus.NEEDS_REVIEW or f.confidence < threshold for f in findings
        )
        finding_set = FindingSet(
            findings=tuple(findings),
            coverage_ratio=coverage_ratio,
            needs_review=needs_review,
        )
        await ctx.send_message(finding_set)
