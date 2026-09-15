"""write_report node.

Phase 6 (required swap, decided 2026-09-14): the table of findings/scores
stays deterministic — those are facts (coverage ratio, per-control status
and confidence) computed upstream, and an agent restating them in prose has
nothing to add but risk of hallucinating a different number. What the agent
*does* draft is a short narrative summary above the table, which is a
legitimate, low-risk use of a model here: prose quality is explicitly a
non-goal per the brief, so a bad summary is a cosmetic problem, but a wrong
number in the table would be a real correctness problem for something
that's meant to double as audit evidence. Falls back to a fixed one-line
summary if the agent call fails, same reasoning as evaluate.py: don't take
the whole run down over a model hiccup.
"""

from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowContext, handler

from src.llm import get_chat_client
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
        table = (
            f"Coverage: {finding_set.coverage_ratio:.0%} of controls evaluated. "
            f"Needs review: {'yes' if finding_set.needs_review else 'no'}.\n\n"
            "| Control | Status | Confidence | Evidence |\n"
            "|---|---|---|---|\n"
            f"{rows}\n"
        )
        summary = await self._draft_summary(service_id, finding_set)

        markdown = f"# Evidence Packet — {service_id}\n\n{summary}\n\n{table}"
        packet = EvidencePacket(
            service_id=service_id,
            markdown=markdown,
            findings=finding_set.findings,
            coverage_ratio=finding_set.coverage_ratio,
        )
        await ctx.yield_output(packet)

    async def _draft_summary(self, service_id: str, finding_set: FindingSet) -> str:
        try:
            agent = Agent(
                client=get_chat_client(),
                name="write_report",
                instructions=(
                    "You write a 2-3 sentence executive summary for a BCDR compliance "
                    "evidence packet. State only what the findings support — do not "
                    "invent numbers or controls not listed. Plain prose, no markdown "
                    "headers, no restating the table that follows."
                ),
            )
            findings_text = "\n".join(
                f"- {f.control_id}: {f.status.value} (confidence {f.confidence:.2f})"
                for f in finding_set.findings
            )
            prompt = (
                f"Service: {service_id}\n"
                f"Coverage: {finding_set.coverage_ratio:.0%}\n"
                f"Needs review: {finding_set.needs_review}\n"
                f"Findings:\n{findings_text}\n"
            )
            response = await agent.run(prompt)
            return response.text.strip()
        except Exception as exc:  # noqa: BLE001 - deliberate: don't fail the run over a model hiccup
            return f"(Automated summary unavailable: {type(exc).__name__}: {exc})"
