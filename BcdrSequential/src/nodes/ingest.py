"""Deterministic ingest node — no LLM. Parses a service's fixture bundle
into a typed ArtifactSet.
"""

import json
from pathlib import Path

from agent_framework import Executor, WorkflowContext, handler

from src.models import ArtifactSet

FIXTURES_ROOT = Path(__file__).resolve().parent.parent.parent / "fixtures"


class IngestExecutor(Executor):
    """Reads fixtures/<service_id>/{failover-test.log, runbook.md, config.json}."""

    @handler
    async def ingest(self, service_id: str, ctx: WorkflowContext[ArtifactSet]) -> None:
        service_dir = FIXTURES_ROOT / service_id
        if not service_dir.is_dir():
            raise FileNotFoundError(
                f"No fixture bundle for service_id={service_id!r} at {service_dir}"
            )

        failover_log = (service_dir / "failover-test.log").read_text()
        runbook_markdown = (service_dir / "runbook.md").read_text()
        config = json.loads((service_dir / "config.json").read_text())

        ctx.set_state("service_id", service_id)

        artifacts = ArtifactSet(
            service_id=service_id,
            failover_log=failover_log,
            runbook_markdown=runbook_markdown,
            config=config,
        )
        await ctx.send_message(artifacts)
