"""Offline wiring tests for the workflow graph (D34). Stub agents, no model calls.

They prove the edges, not the agents: oos skips research, a failed check retries once,
a second failure pauses for a human, and the pause is saved in a checkpoint.
"""

import asyncio
from types import SimpleNamespace

import pytest

from finsight.models import Answer, Route, Verdict
from finsight.orchestration import workflow as wf
from finsight.orchestration.messages import Question, ReviewDecision, ReviewRequest


def answer() -> Answer:
    return Answer(reasoning="r", found=True, answer="0.83", value=0.83, unit="ratio", citations=[57], confidence="medium")


def fake(value) -> SimpleNamespace:
    """Just enough of an AgentResponse: the typed value, no messages, no usage."""
    return SimpleNamespace(value=value, messages=[], usage_details={})


@pytest.fixture
def stubs(monkeypatch):
    """Replace the three agents. Returns a dict to set the route label and the verdicts, and to count calls."""
    s = {"label": "analysis", "supported": [True], "asks": [], "verifies": 0}
    for name in ("build_router", "build_analyst", "build_verifier"):
        monkeypatch.setattr(wf, name, lambda *a, **k: None)

    async def route(agent, doc, q):
        return fake(Route(label=s["label"], reason="stub"))

    async def ask(agent, doc, prompt, reasoning=None):
        s["asks"].append((prompt, reasoning))
        return fake(answer())

    async def verify(agent, doc, q, a):
        ok = s["supported"][min(s["verifies"], len(s["supported"]) - 1)]
        s["verifies"] += 1
        return fake(Verdict(check="c", supported=ok, problem=None if ok else "wrong year"))

    monkeypatch.setattr(wf, "route", route)
    monkeypatch.setattr(wf, "ask", ask)
    monkeypatch.setattr(wf, "verify", verify)
    return s


def run(workflow, **kw):
    return asyncio.run(workflow.run(**kw))


Q = Question(doc_name="ADOBE_2017_10K", question="ratio?")


def test_oos_skips_research(stubs):
    stubs["label"] = "oos"
    report = run(wf.build_workflow(), message=Q).get_outputs()[-1]
    assert report.status == "oos" and stubs["asks"] == []


def test_verified_first_try_and_analysis_gets_reasoning(stubs):
    report = run(wf.build_workflow(), message=Q).get_outputs()[-1]
    assert (report.status, report.attempts) == ("verified", 1)
    assert stubs["asks"][0][1] == wf.ANALYSIS_REASONING


def test_lookup_gets_no_reasoning(stubs):
    stubs["label"] = "lookup"
    run(wf.build_workflow(), message=Q)
    assert stubs["asks"][0][1] is None


def test_one_failure_retries_with_the_problem(stubs):
    stubs["supported"] = [False, True]
    report = run(wf.build_workflow(), message=Q).get_outputs()[-1]
    assert (report.status, report.attempts) == ("verified", 2)
    assert [st.agent for st in report.steps] == ["router", "research", "verifier", "research", "verifier"]
    assert "wrong year" in stubs["asks"][1][0]  # the retry prompt carries the Verifier's problem


def test_two_failures_pause_for_a_human_then_resume(stubs, tmp_path):
    stubs["supported"] = [False]
    storage = wf.FileCheckpointStorage(tmp_path, allowed_checkpoint_types=wf.CHECKPOINT_TYPES)
    workflow = wf.build_workflow(checkpoint_storage=storage)
    result = run(workflow, message=Q)
    assert result.get_outputs() == [] and len(stubs["asks"]) == 2  # paused after one retry, no third try
    req = result.get_request_info_events()[0]

    # The pause is in the checkpoint as a real ReviewRequest, not a dict: the allow-list covers it.
    saved = asyncio.run(storage.get_latest(workflow_name="finsight"))
    pending = list(saved.pending_request_info_events.values())[0]
    assert isinstance(pending.data, ReviewRequest)

    result = run(workflow, responses={req.request_id: ReviewDecision(approved=False, note="bad page")})
    report = result.get_outputs()[-1]
    assert (report.status, report.reviewer_note) == ("human_rejected", "bad page")
