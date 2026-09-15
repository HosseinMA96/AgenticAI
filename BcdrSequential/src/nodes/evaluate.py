"""evaluate_control node.

Phase 6 (required swap, decided 2026-09-14): the Phase 2 rule-based
heuristics are replaced with a real Azure OpenAI call per control, using
`agent_framework.Agent` + structured output (`response_format`) so the
model's judgment is constrained to a valid `ControlJudgment` — no free-text
parsing. The old heuristics are gone from this file (recoverable from git
history if ever needed); nothing in graph.py, models.py, or any other node
changed to make this swap, which is the actual proof of the type-safety
claim made back in Phase 2: the contract was `ArtifactSet -> Finding`
either way.

One executor instance is constructed per ControlSpec (see graph.py) so the
same class fans out across all four controls in Phase 3.

Failure handling (discussed, Phase 6): a malformed structured response or a
client-side error (timeout, content filter, etc.) does not crash the node —
it degrades to a NEEDS_REVIEW Finding with confidence 0.0, so one control's
model hiccup routes to human_review instead of failing the whole run. No
retry logic beyond whatever the framework/client already does by default
(explicit non-goal per the brief).

Correction (caught in review, same day): the first cut of `_judge` stuffed
*all three* raw artifact files into every control's prompt regardless of
relevance — not a fan-out bug (each control still gets its own independent
`agent.run()` call, confirmed via the event stream showing 4 separate
`executor_invoked`/`executor_completed` pairs), but unnecessary noise in
what each individual call actually sees. `ControlSpec.relevant_artifacts`
now scopes each prompt to only the artifact(s) that control needs.
"""

from datetime import UTC, datetime
from typing import Any

from agent_framework import Agent, Executor, WorkflowContext, handler
from pydantic import Field

from src.controls import CONTROLS
from src.llm import get_chat_client
from src.models import ArtifactSet, ControlSpec, Finding, FindingStatus, StrictModel

_CONTROLS_BY_ID = {control.control_id: control for control in CONTROLS}
_ARTIFACT_LABELS = {
    "runbook_markdown": "runbook.md",
    "failover_log": "failover-test.log",
    "config": "config.json",
}


class ControlJudgment(StrictModel):
    """The LLM's structured output shape — narrower than Finding, since
    control_id is already known and doesn't need to come from the model."""

    status: FindingStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ref: str
    rationale: str


class EvaluateControlExecutor(Executor):
    """Evaluates one ControlSpec against an ArtifactSet via an Azure OpenAI call."""

    def __init__(self, control: ControlSpec, id: str):
        super().__init__(id=id)
        self._control = control

    def to_dict(self) -> dict[str, Any]:
        """Adds control_id so a serialized graph can fully reconstruct this
        executor — the base Executor.to_dict() only captures {id, type},
        which is enough for the other four nodes (plain id-only
        constructors) but not this one, since `control` isn't otherwise
        recoverable from graph topology alone."""
        data = super().to_dict()
        data["control_id"] = self._control.control_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluateControlExecutor":
        control = _CONTROLS_BY_ID[data["control_id"]]
        return cls(control=control, id=data["id"])

    @handler
    async def evaluate(self, artifacts: ArtifactSet, ctx: WorkflowContext[Finding]) -> None:
        try:
            judgment = await self._judge(artifacts)
        except Exception as exc:  # noqa: BLE001 - deliberate: any model/client failure degrades gracefully
            finding = Finding(
                control_id=self._control.control_id,
                status=FindingStatus.NEEDS_REVIEW,
                evidence_ref=f"evaluate_control agent call failed: {type(exc).__name__}: {exc}",
                confidence=0.0,
            )
        else:
            finding = Finding(
                control_id=self._control.control_id,
                status=judgment.status,
                evidence_ref=judgment.evidence_ref,
                confidence=judgment.confidence,
            )
        await ctx.send_message(finding)

    async def _judge(self, artifacts: ArtifactSet) -> ControlJudgment:
        agent = Agent(
            client=get_chat_client(),
            name=f"evaluate_{self._control.control_id}",
            instructions=(
                "You are a BCDR compliance evidence reviewer. Evaluate exactly one "
                "control against the provided artifacts and return a structured "
                "judgment. Be conservative: prefer NEEDS_REVIEW over guessing when "
                "the evidence is ambiguous or incomplete."
            ),
        )
        evidence = "\n\n".join(
            f"--- {_ARTIFACT_LABELS[field]} ---\n{getattr(artifacts, field)}"
            for field in self._control.relevant_artifacts
        )
        prompt = (
            f"Today's date is {datetime.now(UTC).date().isoformat()}.\n\n"
            f"Control: {self._control.control_id}\n"
            f"Control description: {self._control.description}\n"
            f"Evaluation instructions: {self._control.evaluation_prompt}\n\n"
            f"{evidence}\n"
        )
        response = await agent.run(prompt, options={"response_format": ControlJudgment})
        return response.value
