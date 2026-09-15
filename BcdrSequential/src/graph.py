"""Builds and validates the compliance evidence workflow.

Phase 3 (M2): full graph —

              +-> evaluate(rto_documented)      -+
              |                                  |
    ingest ---+-> evaluate(rollback_path)       -+--> aggregate --[conditional]--+--> human_review --+
    (typed    |                                  |         |                    |                    |
    RunRequest+-> evaluate(failover_test_recent)-+         | needs_review=False |                    |
    in)       |                                  |         v                    +--------------------+
              +-> evaluate(contacts_current)    -+   write_report <-------------------------------------+

`add_fan_out_edges` broadcasts ingest's single ArtifactSet to all four
evaluators concurrently; `add_fan_in_edges` makes `aggregate` a barrier that
only runs once all four have completed for that superstep. The conditional
edges route on `FindingSet.needs_review`, which `aggregate` computes from a
threshold read out of shared state (set by `ingest` from the initial
`RunRequest`) rather than a hardcoded constant — so changing the threshold
at run time changes the routed branch without touching this file.
"""

from agent_framework import CheckpointStorage, WorkflowBuilder

from src.controls import CONTROLS
from src.nodes.aggregate import AggregateExecutor
from src.nodes.evaluate import EvaluateControlExecutor
from src.nodes.human_review import HumanReviewExecutor
from src.nodes.ingest import IngestExecutor
from src.nodes.report import WriteReportExecutor

WORKFLOW_NAME = "bcdr-evidence-workflow"


def build_graph(checkpoint_storage: CheckpointStorage | None = None):
    ingest = IngestExecutor(id="ingest")
    evaluators = [
        EvaluateControlExecutor(control=control, id=f"evaluate_{control.control_id}")
        for control in CONTROLS
    ]
    aggregate = AggregateExecutor(id="aggregate")
    human_review = HumanReviewExecutor(id="human_review")
    write_report = WriteReportExecutor(id="write_report")

    return (
        WorkflowBuilder(
            start_executor=ingest,
            name=WORKFLOW_NAME,
            checkpoint_storage=checkpoint_storage,
        )
        .add_fan_out_edges(ingest, evaluators)
        .add_fan_in_edges(evaluators, aggregate)
        .add_edge(aggregate, human_review, condition=lambda fs: fs.needs_review)
        .add_edge(aggregate, write_report, condition=lambda fs: not fs.needs_review)
        .add_edge(human_review, write_report)
        .build()
    )
