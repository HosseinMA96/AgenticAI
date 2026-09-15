"""evaluate_control node.

Decision (Phase 2, discussed before coding): implemented as a deterministic
rule-based evaluator for now, not an LLM call. Reasons:
  1. The M1/M2 acceptance tests are about graph *structure* (type-safety at
     build time, fan-out concurrency, conditional routing) — they don't
     require the evaluator's judgment to come from a model.
  2. It keeps the graph runnable end-to-end offline, without `az login` or
     Foundry deployment, while the wiring is still being shaken out.
  3. Swapping this executor's internals for an Azure OpenAI-backed ChatAgent
     later is a localized change — the graph, types, and edges don't change,
     which is itself a demonstration of why type-safe steps are useful.
The brief's non-goals explicitly exclude report/prompt quality, so a
heuristic standing in for the "agent" kind is an acceptable simplification
for this learning project.

One executor instance is constructed per ControlSpec (see graph.py) so the
same class fans out across all four controls in Phase 3.
"""

import re
from datetime import UTC, datetime
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from src.controls import CONTROLS
from src.models import ArtifactSet, ControlSpec, Finding, FindingStatus

_TIMESTAMP_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}Z\]")
_RESULT_RE = re.compile(r"result=(\w+)")
_CONTROLS_BY_ID = {control.control_id: control for control in CONTROLS}


class EvaluateControlExecutor(Executor):
    """Evaluates one ControlSpec against an ArtifactSet, deterministically."""

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
        method = getattr(self, f"_evaluate_{self._control.control_id}", None)
        if method is None:
            raise ValueError(f"No evaluator implemented for control {self._control.control_id!r}")
        finding = method(artifacts)
        await ctx.send_message(finding)

    def _evaluate_rto_documented(self, artifacts: ArtifactSet) -> Finding:
        runbook = artifacts.runbook_markdown
        match = re.search(r"\*\*RTO:\*\*\s*(.+)", runbook)
        if match and re.search(r"\d", match.group(1)):
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.PASS,
                evidence_ref="runbook.md#Recovery Objectives",
                confidence=0.95,
            )
        if "RTO" in runbook.upper():
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.NEEDS_REVIEW,
                evidence_ref="runbook.md",
                confidence=0.5,
            )
        return Finding(
            control_id=self._control.control_id,
            status=FindingStatus.FAIL,
            evidence_ref="runbook.md",
            confidence=0.9,
        )

    def _evaluate_rollback_path(self, artifacts: ArtifactSet) -> Finding:
        runbook = artifacts.runbook_markdown
        section_match = re.search(r"## Rollback\n(.+?)(\n##|\Z)", runbook, re.DOTALL)
        if not section_match:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.FAIL,
                evidence_ref="runbook.md",
                confidence=0.9,
            )
        body = section_match.group(1).strip()
        has_numbered_steps = bool(re.search(r"^\d+\.", body, re.MULTILINE))
        vague_markers = ("no rollback", "no scripted path", "not been written", "TBD")
        if any(marker.lower() in body.lower() for marker in vague_markers) or not has_numbered_steps:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.NEEDS_REVIEW,
                evidence_ref="runbook.md#Rollback",
                confidence=0.55,
            )
        return Finding(
            control_id=self._control.control_id,
            status=FindingStatus.PASS,
            evidence_ref="runbook.md#Rollback",
            confidence=0.9,
        )

    def _evaluate_failover_test_recent(self, artifacts: ArtifactSet) -> Finding:
        log = artifacts.failover_log
        entries = list(zip(_TIMESTAMP_RE.findall(log), _RESULT_RE.findall(log), strict=False))
        if not entries:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.NEEDS_REVIEW,
                evidence_ref="failover-test.log",
                confidence=0.4,
            )
        latest_date_str, latest_result = entries[0]
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - latest_date).days

        # Overdue is disqualifying regardless of outcome — an old partial
        # success still means there's no *recent* passing test on record.
        if age_days > 365:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.FAIL,
                evidence_ref="failover-test.log",
                confidence=0.85,
            )
        if latest_result == "SUCCESS":
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.PASS,
                evidence_ref="failover-test.log",
                confidence=0.95,
            )
        return Finding(
            control_id=self._control.control_id,
            status=FindingStatus.NEEDS_REVIEW,
            evidence_ref="failover-test.log",
            confidence=0.5,
        )

    def _evaluate_contacts_current(self, artifacts: ArtifactSet) -> Finding:
        contacts = artifacts.config.get("escalation_contacts", [])
        if not isinstance(contacts, list) or not contacts:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.FAIL,
                evidence_ref="config.json#escalation_contacts",
                confidence=0.9,
            )
        placeholder_markers = ("", "tbd")
        has_placeholder = any(
            str(entry.get("name", "")).strip().lower() in placeholder_markers
            or str(entry.get("channel", "")).strip().lower() in placeholder_markers
            for entry in contacts
            if isinstance(entry, dict)
        )
        if has_placeholder:
            return Finding(
                control_id=self._control.control_id,
                status=FindingStatus.FAIL,
                evidence_ref="config.json#escalation_contacts",
                confidence=0.85,
            )
        return Finding(
            control_id=self._control.control_id,
            status=FindingStatus.PASS,
            evidence_ref="config.json#escalation_contacts",
            confidence=0.9,
        )
