"""Deterministic ingest node — no LLM. Discovers a service's evidence files
by role and parses them into a typed ArtifactSet.

Format-agnostic (TODO Phase 8): each role is looked up by a fixed filename
*stem* (e.g. "runbook"), with any extension — the extension alone decides
EvidenceFormat (text vs image vs pdf), so a control's evidence can be
swapped from a markdown file to a screenshot or PDF without touching
models.py, controls.py, or the graph.
"""

from pathlib import Path

from agent_framework import Executor, WorkflowContext, handler

from src.models import ArtifactSet, EvidenceFormat, EvidenceItem, RunRequest

FIXTURES_ROOT = Path(__file__).resolve().parent.parent.parent / "fixtures"

# role -> filename stem to look for (any extension) in fixtures/<service_id>/
ROLE_STEMS = {
    "runbook": "runbook",
    "failover_log": "failover-test",
    "config": "config",
}

_TEXT_EXTENSIONS = {".md", ".txt", ".log", ".json"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_PDF_EXTENSIONS = {".pdf"}

_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}


def _classify(suffix: str) -> EvidenceFormat:
    if suffix in _TEXT_EXTENSIONS:
        return EvidenceFormat.TEXT
    if suffix in _IMAGE_EXTENSIONS:
        return EvidenceFormat.IMAGE
    if suffix in _PDF_EXTENSIONS:
        return EvidenceFormat.PDF
    raise ValueError(f"Unsupported evidence file extension: {suffix!r}")


def _find_evidence_file(service_dir: Path, stem: str) -> Path:
    matches = [p for p in service_dir.iterdir() if p.stem == stem and p.is_file()]
    if not matches:
        raise FileNotFoundError(f"No evidence file with stem {stem!r} found in {service_dir}")
    if len(matches) > 1:
        raise ValueError(f"Multiple evidence files with stem {stem!r} found in {service_dir}: {matches}")
    return matches[0]


class IngestExecutor(Executor):
    """Reads fixtures/<service_id>/{runbook,failover-test,config}.<any ext>."""

    @handler
    async def ingest(self, request: RunRequest, ctx: WorkflowContext[ArtifactSet]) -> None:
        service_dir = FIXTURES_ROOT / request.service_id
        if not service_dir.is_dir():
            raise FileNotFoundError(
                f"No fixture bundle for service_id={request.service_id!r} at {service_dir}"
            )

        evidence: dict[str, EvidenceItem] = {}
        for role, stem in ROLE_STEMS.items():
            path = _find_evidence_file(service_dir, stem)
            fmt = _classify(path.suffix.lower())
            evidence[role] = EvidenceItem(
                role=role,
                path=str(path),
                format=fmt,
                text=path.read_text() if fmt == EvidenceFormat.TEXT else None,
                media_type=_MEDIA_TYPES[path.suffix.lower()],
            )

        ctx.set_state("service_id", request.service_id)
        ctx.set_state("confidence_threshold", request.confidence_threshold)

        artifacts = ArtifactSet(service_id=request.service_id, evidence=evidence)
        await ctx.send_message(artifacts)
