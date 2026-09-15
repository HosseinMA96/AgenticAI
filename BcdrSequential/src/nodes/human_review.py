"""human_review node — pause point.

Decision (Phase 3, discussed before coding): implemented as a blocking
`input()` prompt in the executor's own handler, not the framework's
`request_info`/external-response mechanism. Reasons:
  1. It's the simplest thing that satisfies the brief ("surfaces flagged
     findings, waits for input, merges the decision back into state") without
     learning a second pause/resume mechanic on top of everything else this
     week.
  2. It's a *better* fit for Phase 4's `kill -9` test than an async handoff
     would be: killing the process while it's genuinely blocked on stdin,
     mid-superstep, is exactly the scenario checkpoint/resume needs to prove
     out.

`Finding` is frozen (Phase 1 decision), so a resolved finding is a new
`Finding` built via `model_copy(update=...)`, not a mutation.
"""

from agent_framework import Executor, WorkflowContext, handler

from src.models import Finding, FindingSet, FindingStatus, HumanReviewDecision

DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class HumanReviewExecutor(Executor):
    @handler
    async def review(self, finding_set: FindingSet, ctx: WorkflowContext[FindingSet]) -> None:
        threshold = ctx.get_state("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        decisions: list[HumanReviewDecision] = []
        resolved_findings: list[Finding] = []

        for finding in finding_set.findings:
            flagged = finding.status == FindingStatus.NEEDS_REVIEW or finding.confidence < threshold
            if not flagged:
                resolved_findings.append(finding)
                continue

            print(f"\n--- Human review required: {finding.control_id} ---")
            print(f"  status={finding.status.value} confidence={finding.confidence:.2f}")
            print(f"  evidence={finding.evidence_ref}")
            resolved_status_raw = input("  Resolve as PASS/FAIL/NEEDS_REVIEW: ").strip().upper()
            resolved_status = FindingStatus(resolved_status_raw)
            note = input("  Reviewer note: ").strip()

            decision = HumanReviewDecision(
                control_id=finding.control_id,
                resolved_status=resolved_status,
                reviewer_note=note,
            )
            decisions.append(decision)
            resolved_findings.append(
                finding.model_copy(update={"status": resolved_status, "confidence": 1.0})
            )

        ctx.set_state("human_review_decisions", decisions)

        resolved_set = FindingSet(
            findings=tuple(resolved_findings),
            coverage_ratio=finding_set.coverage_ratio,
            needs_review=False,
        )
        await ctx.send_message(resolved_set)
