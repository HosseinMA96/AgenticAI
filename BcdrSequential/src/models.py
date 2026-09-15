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


class ArtifactSet(StrictModel):
    """Parsed output of `ingest` — the raw synthetic bundle, structured."""

    service_id: str
    failover_log: str
    runbook_markdown: str
    config: dict[str, object]


class ControlSpec(StrictModel):
    """Definition of a single control to evaluate against the ArtifactSet."""

    control_id: str
    description: str
    evaluation_prompt: str
    relevant_artifacts: tuple[str, ...]
    """Which ArtifactSet field(s) this control's evaluation actually needs —
    e.g. ("runbook_markdown",). Scopes each evaluate_control call's prompt
    to only relevant evidence instead of the full bundle every time."""


class Finding(StrictModel):
    """Output of one `evaluate_control` node."""

    control_id: str
    status: FindingStatus
    evidence_ref: str
    confidence: float = Field(ge=0.0, le=1.0)


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
