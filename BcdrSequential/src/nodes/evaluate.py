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

Phase 8 (format-agnostic evidence): TEXT evidence is still inlined into the
prompt text, same as before. IMAGE/PDF evidence is instead attached as a
multimodal `Content` item on the same `Message` — confirmed against the
installed `agent_framework_openai` connector source
(`_chat_client.py`): a `Content(type="uri", uri=<data: URI>,
media_type=...)` maps to an `input_image` block for image media types, and
the same shape with `additional_properties={"openai_content_type":
"input_file"}` maps to `input_file` for PDFs. So the model looks at the
actual screenshot/PDF page rather than a paraphrase of it, with no OCR or
PDF-text-extraction step needed.
"""

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_framework import Agent, Content, Executor, Message, WorkflowContext, handler
from pydantic import Field

from src.controls import CONTROLS
from src.llm import get_chat_client
from src.models import ArtifactSet, ControlSpec, EvidenceFormat, EvidenceItem, Finding, FindingStatus, NotesSource, StrictModel

_CONTROLS_BY_ID = {control.control_id: control for control in CONTROLS}


def _evidence_to_content(item: EvidenceItem) -> Content:
    """IMAGE/PDF evidence -> a multimodal Content item, read fresh from disk
    (not carried as bytes on ArtifactSet, to keep checkpoints small)."""
    data = base64.b64encode(Path(item.path).read_bytes()).decode("ascii")
    uri = f"data:{item.media_type};base64,{data}"
    if item.format == EvidenceFormat.PDF:
        return Content(
            type="uri",
            uri=uri,
            media_type=item.media_type,
            additional_properties={
                "openai_content_type": "input_file",
                "filename": Path(item.path).name,
            },
        )
    return Content(type="uri", uri=uri, media_type=item.media_type)


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
                evidence_ref="n/a (evaluation failed)",
                confidence=0.0,
                notes=f"evaluate_control agent call failed: {type(exc).__name__}: {exc}",
                notes_source=NotesSource.SYSTEM,
            )
        else:
            finding = Finding(
                control_id=self._control.control_id,
                status=judgment.status,
                evidence_ref=judgment.evidence_ref,
                confidence=judgment.confidence,
                notes=judgment.rationale,
                notes_source=NotesSource.AGENT,
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
        text_blocks = []
        media_contents = []
        for role in self._control.relevant_artifacts:
            item = artifacts.evidence[role]
            if item.format == EvidenceFormat.TEXT:
                text_blocks.append(f"--- {Path(item.path).name} ---\n{item.text}")
            else:
                text_blocks.append(f"--- {Path(item.path).name} (attached below) ---")
                media_contents.append(_evidence_to_content(item))

        prompt_text = (
            f"Today's date is {datetime.now(UTC).date().isoformat()}.\n\n"
            f"Control: {self._control.control_id}\n"
            f"Control description: {self._control.description}\n"
            f"Evaluation instructions: {self._control.evaluation_prompt}\n\n"
            f"{chr(10).join(text_blocks)}\n"
        )
        message = Message("user", contents=[Content(type="text", text=prompt_text), *media_contents])
        response = await agent.run([message], options={"response_format": ControlJudgment})
        return response.value
