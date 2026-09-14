"""write_report node — deterministic for now (see evaluate.py's docstring for
the same reasoning: graph structure is the thing under test in M1/M2, not
prose quality, which is an explicit non-goal). This is the workflow's
terminal node, so it yields a workflow output instead of sending a message.
"""

from typing_extensions import Never

from agent_framework import Executor, WorkflowContext, handler

from src.models import EvidencePacket, FindingSet


class WriteReportExecutor(Executor):
    @handler
    async def write_report(
        self, finding_set: FindingSet, ctx: WorkflowContext[Never, EvidencePacket]
    ) -> None:
        service_id = ctx.get_state("service_id", "unknown-service")

        rows = "\n".join(
            f"| {f.control_id} | {f.status.value} | {f.confidence:.2f} | {f.evidence_ref} |"
            for f in finding_set.findings
        )
        markdown = (
            f"# Evidence Packet — {service_id}\n\n"
            f"Coverage: {finding_set.coverage_ratio:.0%} of controls evaluated. "
            f"Needs review: {'yes' if finding_set.needs_review else 'no'}.\n\n"
            "| Control | Status | Confidence | Evidence |\n"
            "|---|---|---|---|\n"
            f"{rows}\n"
        )
        packet = EvidencePacket(
            service_id=service_id,
            markdown=markdown,
            findings=finding_set.findings,
            coverage_ratio=finding_set.coverage_ratio,
        )
        await ctx.yield_output(packet)
