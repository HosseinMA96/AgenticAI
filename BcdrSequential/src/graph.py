"""Builds and validates the compliance evidence workflow.

M1 (this file, Phase 2): a sequential spine —
    ingest -> evaluate_control(rto_documented) -> aggregate -> write_report
wired one control at a time with plain edges. Phase 3 rewires the middle of
this graph: four `EvaluateControlExecutor` instances fan out from `ingest`
and fan in at `aggregate` (which then takes `list[Finding]`), plus a
conditional edge out of `aggregate` toward `human_review` or `write_report`.
Each node's contract is a Pydantic model from models.py, so every rewiring
is checked for type compatibility at `.build()` time rather than discovered
at runtime.
"""

from agent_framework import WorkflowBuilder

from src.controls import CONTROLS
from src.nodes.aggregate import AggregateExecutor
from src.nodes.evaluate import EvaluateControlExecutor
from src.nodes.ingest import IngestExecutor
from src.nodes.report import WriteReportExecutor


def build_graph():
    ingest = IngestExecutor(id="ingest")
    evaluate_rto = EvaluateControlExecutor(control=CONTROLS[0], id="evaluate_rto_documented")
    aggregate = AggregateExecutor(id="aggregate")
    write_report = WriteReportExecutor(id="write_report")

    return (
        WorkflowBuilder(start_executor=ingest)
        .add_edge(ingest, evaluate_rto)
        .add_edge(evaluate_rto, aggregate)
        .add_edge(aggregate, write_report)
        .build()
    )
