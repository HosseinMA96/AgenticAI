"""Pydantic contracts for the compliance evidence workflow.

Every node input/output is defined here so the graph builder can validate
edges at build time (see brief §1, concept 1: type-safe steps).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RunRequest(StrictModel):
    """Initial input to the workflow — carries the confidence threshold as
    typed data rather than a hidden CLI side-channel, so `ingest` can push it
    into shared state for the conditional edge to read later."""

    service_id: str
    confidence_threshold: float = Field(ge=0.0, le=1.0)


class EvidenceFormat(StrEnum):
    """How this evidence item must be presented to the model. TEXT is
    inlined into the prompt; IMAGE/PDF are attached as multimodal message
    content (see evaluate.py) — the model looks at the actual file rather
    than a paraphrase of it."""

    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"


class EvidenceItem(StrictModel):
    """One piece of evidence for a service, discovered by role (a fixed
    stem like "runbook") rather than a fixed filename+extension — the
    extension only decides `format` (see ingest.py)."""

    role: str
    path: str
    format: EvidenceFormat
    text: str | None = None
    """Populated for TEXT evidence only; IMAGE/PDF evidence is read from
    `path` at prompt-build time instead of being inlined here."""
    media_type: str


class ArtifactSet(StrictModel):
    """Parsed output of `ingest` — the raw synthetic bundle, structured.

    Format-agnostic (TODO Phase 8): evidence is keyed by role
    ("runbook", "failover_log", "config") rather than fixed
    str/str/dict fields, so a role's evidence can be markdown, a PDF, or a
    screenshot without changing this contract or ControlSpec.relevant_artifacts."""

    service_id: str
    evidence: dict[str, EvidenceItem]


class ControlSpec(StrictModel):
    """Definition of a single control to evaluate against the ArtifactSet."""

    control_id: str
    description: str
    evaluation_prompt: str
    relevant_artifacts: tuple[str, ...]
    """Which ArtifactSet field(s) this control's evaluation actually needs —
    e.g. ("runbook_markdown",). Scopes each evaluate_control call's prompt
    to only relevant evidence instead of the full bundle every time."""


class NotesSource(StrEnum):
    AGENT = "AGENT"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    """SYSTEM covers evaluate_control's own fallback path (agent/tool call
    failed), so a NEEDS_REVIEW finding's notes clearly aren't a real
    judgment from either the model or a person."""


class Finding(StrictModel):
    """Output of one `evaluate_control` node."""

    control_id: str
    status: FindingStatus
    evidence_ref: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
    notes_source: NotesSource
    """Why this decision was made. AGENT = the model's own rationale;
    HUMAN = overwritten by a human_review reviewer note, replacing whatever
    rationale was there before; SYSTEM = evaluate_control's error fallback."""


class FindingSet(StrictModel):
    """Output of `aggregate` — fan-in result plus coverage stats."""

    findings: tuple[Finding, ...]
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    needs_review: bool


class HumanReviewDecision(StrictModel):
    """Merged back into state after `human_review` pauses for input."""

    control_id: str
    resolved_status: FindingStatus
    reviewer_note: str


class EvidencePacket(StrictModel):
    """Final output of `write_report` — the markdown evidence packet."""

    service_id: str
    markdown: str
    findings: tuple[Finding, ...]
    coverage_ratio: float
