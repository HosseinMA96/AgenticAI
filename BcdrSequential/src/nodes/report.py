"""write_report node.

Phase 6 (real agent call, see evaluate.py's docstring for the same
reasoning on why deterministic facts stay deterministic): the per-control
table and coverage stats are computed from `FindingSet`, not restated by a
model. What genuinely needs judgment — the overall compliance verdict and
the reasoning behind it — is the agent's job.

Extension (discussed, same day as Phase 6): the agent doesn't just return
that judgment as text — it calls a real tool, `write_evidence_file`, to
persist the structured report to `reports/{service_id}.md`. This is the
project's first exercise of actual tool/function-calling (distinct from
`response_format` structured output used in evaluate.py): the framework's
`Agent` auto-executes a plain Python function passed via `tools=[...]`
within `agent.run()` — confirmed by testing a toy weather-tool example
before wiring this up. The tool's signature deliberately takes only
`verdict` and `reason` as arguments, not the per-control findings — those
are injected via closure from the already-computed `FindingSet`, so the
model has no opportunity to restate (and possibly hallucinate) a fact it
didn't need to touch. If the agent call fails or never calls the tool, a
deterministic fallback verdict is computed and the file is still written,
so a model hiccup degrades gracefully rather than silently producing no
report.
"""

from enum import StrEnum
from pathlib import Path

from typing_extensions import Never

from agent_framework import Agent, WorkflowContext, Executor, handler

from src.llm import get_chat_client
from src.models import EvidencePacket, FindingSet, FindingStatus, NotesSource

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


class FindingVerdict(StrEnum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


def _deterministic_verdict(finding_set: FindingSet) -> FindingVerdict:
    if any(f.status == FindingStatus.FAIL for f in finding_set.findings):
        return FindingVerdict.NON_COMPLIANT
    if finding_set.needs_review:
        return FindingVerdict.NEEDS_REVIEW
    return FindingVerdict.COMPLIANT


def _markdown_table_cell(text: str) -> str:
    """Collapse newlines and escape pipes so free-text notes can't break the
    table's row structure."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


_NOTES_SOURCE_LABEL = {
    NotesSource.AGENT: "Agent",
    NotesSource.HUMAN: "Human",
    NotesSource.SYSTEM: "System",
}


def _render_markdown(service_id: str, finding_set: FindingSet, verdict: str, reason: str) -> str:
    rows = "\n".join(
        f"| {f.control_id} | {f.status.value} | {f.confidence:.2f} | {f.evidence_ref} "
        f"| ({_NOTES_SOURCE_LABEL[f.notes_source]}) {_markdown_table_cell(f.notes)} |"
        for f in finding_set.findings
    )
    return (
        f"# Compliance Evidence Report — {service_id}\n\n"
        f"## Overall Verdict: {verdict}\n\n"
        f"{reason}\n\n"
        f"Coverage: {finding_set.coverage_ratio:.0%} of controls evaluated.\n\n"
        "## Per-Control Findings\n\n"
        "| Control | Status | Confidence | Evidence | Notes |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n"
    )


def _make_write_evidence_file_tool(service_id: str, finding_set: FindingSet, captured: dict):
    def write_evidence_file(verdict: str, reason: str) -> str:
        """Write the final compliance evidence report for this service to disk.

        Call this exactly once, after you've decided the overall verdict.

        Args:
            verdict: Overall compliance verdict for this service. Must be
                one of: COMPLIANT, NON_COMPLIANT, NEEDS_REVIEW.
            reason: A 1-3 sentence justification for the verdict, grounded
                only in the findings you were given.
        """
        markdown = _render_markdown(service_id, finding_set, verdict, reason)
        REPORTS_DIR.mkdir(exist_ok=True)
        path = REPORTS_DIR / f"{service_id}.md"
        path.write_text(markdown)
        captured["markdown"] = markdown
        return f"Wrote evidence report to {path}"

    return write_evidence_file


class WriteReportExecutor(Executor):
    @handler
    async def write_report(
        self, finding_set: FindingSet, ctx: WorkflowContext[Never, EvidencePacket]
    ) -> None:
        service_id = ctx.get_state("service_id", "unknown-service")
        captured: dict = {}

        try:
            tool = _make_write_evidence_file_tool(service_id, finding_set, captured)
            agent = Agent(
                client=get_chat_client(),
                name="write_report",
                instructions=(
                    "You review per-control BCDR compliance findings for one service "
                    "and decide an overall verdict: COMPLIANT if all controls passed, "
                    "NON_COMPLIANT if any control failed, NEEDS_REVIEW if none failed "
                    "but some are unresolved or low-confidence. Ground your reasoning "
                    "only in the findings given to you. Call write_evidence_file "
                    "exactly once with your verdict and reason."
                ),
                tools=[tool],
            )
            findings_text = "\n".join(
                f"- {f.control_id}: {f.status.value} (confidence {f.confidence:.2f}) — {f.notes}"
                for f in finding_set.findings
            )
            prompt = (
                f"Service: {service_id}\n"
                f"Coverage: {finding_set.coverage_ratio:.0%}\n"
                f"Findings:\n{findings_text}\n"
            )
            await agent.run(prompt)
        except Exception:  # noqa: BLE001 - deliberate: don't fail the run over a model/tool hiccup
            pass

        if "markdown" not in captured:
            # Agent call failed, or the model never actually called the tool --
            # fall back to a deterministic verdict so a report still exists.
            verdict = _deterministic_verdict(finding_set)
            reason = "Automated fallback verdict (agent unavailable or declined to call the tool)."
            markdown = _render_markdown(service_id, finding_set, verdict.value, reason)
            REPORTS_DIR.mkdir(exist_ok=True)
            (REPORTS_DIR / f"{service_id}.md").write_text(markdown)
            captured["markdown"] = markdown

        packet = EvidencePacket(
            service_id=service_id,
            markdown=captured["markdown"],
            findings=finding_set.findings,
            coverage_ratio=finding_set.coverage_ratio,
        )
        await ctx.yield_output(packet)
