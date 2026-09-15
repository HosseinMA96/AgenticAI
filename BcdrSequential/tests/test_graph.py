"""Acceptance tests for graph structure (M1/M3 from TODO.md).

Not covered here: the M3 kill -9 / --resume acceptance test. It requires a
genuinely blocked process (human_review's input()) and a real SIGKILL, which
doesn't fit a fast pytest run — verified manually instead (see NOTES.md /
README for the reproduction steps and results).
"""

import json

from agent_framework import WorkflowBuilder

from src.controls import CONTROLS
from src.graph import build_graph
from src.nodes.evaluate import EvaluateControlExecutor
from src.nodes.ingest import IngestExecutor
from src.nodes.report import WriteReportExecutor


def test_type_mismatch_fails_at_build_time():
    """M1 acceptance test: skip aggregate, wire evaluate_control directly
    into write_report (Finding -> FindingSet is a type mismatch). Must fail
    at .build(), before any node executes."""
    ingest = IngestExecutor(id="ingest")
    evaluate_rto = EvaluateControlExecutor(control=CONTROLS[0], id="evaluate_rto_documented")
    write_report = WriteReportExecutor(id="write_report")

    try:
        (
            WorkflowBuilder(start_executor=ingest)
            .add_edge(ingest, evaluate_rto)
            .add_edge(evaluate_rto, write_report)
            .build()
        )
    except Exception as e:
        assert type(e).__name__ == "TypeCompatibilityError"
    else:
        raise AssertionError("build() should have rejected a Finding -> FindingSet edge")


def test_fan_in_requires_at_least_two_sources():
    """Documents a real framework constraint discovered while building
    Phase 2: a fan-in group of one source is rejected, not silently allowed."""
    ingest = IngestExecutor(id="ingest")
    evaluate_rto = EvaluateControlExecutor(control=CONTROLS[0], id="evaluate_rto_documented")

    try:
        WorkflowBuilder(start_executor=ingest).add_fan_in_edges([evaluate_rto], ingest)
    except ValueError as e:
        assert "at least two sources" in str(e)
    else:
        raise AssertionError("add_fan_in_edges should reject a single-source group")


def test_graph_json_dump_matches_live_structure():
    """M3 serialization: Workflow.to_json()/from_json() has no working path
    back to a runnable Workflow (see graph.py docstring / TODO Phase 4
    decision), so 'reconstruct' here means: parse the dump back into a dict
    and confirm it structurally matches the live graph -- executor ids,
    types, the custom control_id field, and the start executor."""
    live = build_graph()
    dumped = json.loads(live.to_json())

    live_executors = live.get_executors_list()
    live_ids = {e.id for e in live_executors}
    assert live_ids == set(dumped["executors"].keys())

    live_types = {e.id: type(e).__name__ for e in live_executors}
    dumped_types = {eid: data["type"] for eid, data in dumped["executors"].items()}
    assert live_types == dumped_types

    assert dumped["executors"]["evaluate_rto_documented"]["control_id"] == "rto_documented"
    assert dumped["start_executor_id"] == "ingest"


def test_evaluate_control_executor_round_trips_via_dict():
    """The custom to_dict/from_dict override (Phase 4 decision) actually
    reconstructs a working executor with the right ControlSpec attached."""
    original = EvaluateControlExecutor(control=CONTROLS[0], id="evaluate_rto_documented")
    rebuilt = EvaluateControlExecutor.from_dict(original.to_dict())
    assert rebuilt.id == original.id
    assert rebuilt._control == original._control
