"""Week 3, Step 13 (lesson): the decision log (D42) stops a second answer to the same review request (book 4.13).

Lesson 12's break, replayed against the real product `--resume`. Each command is a separate process:
    uv run python lessons/w3_step13_double_answer.py start              # pause a run for a human, then EXIT
    uv run python lessons/w3_step13_double_answer.py list               # paused checkpoints + the decision log
    uv run python lessons/w3_step13_double_answer.py resume             # answer the latest pause (y or n)
    uv run python lessons/w3_step13_double_answer.py resume <CKPT_ID>   # break it: answer again from the OLD pause

No model calls: the three agents are stubs (as in tests/test_workflow.py) and the Verifier always
fails, so every run pauses after the retry. Everything else is the product code in workflow.py.
"""

import asyncio
import contextlib
import shutil
import sys
from pathlib import Path

from finsight.models import Answer, Route, Verdict
from finsight.orchestration import workflow as wf
from finsight.orchestration.messages import Question

OUT = Path(__file__).parent / "_out" / "checkpoints_step13"
wf.CHECKPOINTS, wf.DECISIONS = OUT, OUT / "decisions"  # keep the lesson out of the real checkpoints/


def _fake(value):
    return type("Response", (), {"value": value, "messages": [], "usage_details": {}})()


async def _route(agent, doc, q):
    return _fake(Route(label="analysis", reason="stub"))


async def _ask(agent, doc, prompt, reasoning=None):
    return _fake(Answer(reasoning="stub", found=True, answer="0.83", value=0.83, unit="ratio",
                        citations=[57], confidence="medium"))


async def _verify(agent, doc, q, a):
    return _fake(Verdict(check="stub", supported=False, problem="wrong year"))


for name in ("build_router", "build_analyst", "build_verifier"):
    setattr(wf, name, lambda *a, **k: None)
wf.route, wf.ask, wf.verify = _route, _ask, _verify
wf.edgar_stdio = contextlib.nullcontext  # no MCP server: the stubs never call tools


async def start() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    result = await wf.build_workflow(checkpoint_storage=wf.checkpoint_storage()).run(
        Question(doc_name="ADOBE_2017_10K", question="Quick ratio?"))
    req = result.get_request_info_events()[0]
    print(f"paused for a human: request {req.request_id} ({req.data.reason}). Process exits now.")


async def show() -> None:
    cps = await wf.checkpoint_storage().list_checkpoints(workflow_name="finsight")
    for c in sorted(cps, key=lambda c: c.timestamp):
        if c.pending_request_info_events:
            print(f"paused checkpoint {c.checkpoint_id}  waiting on request {list(c.pending_request_info_events)[0]}")
    decided = sorted(wf.DECISIONS.glob("*.json")) if wf.DECISIONS.exists() else []
    print(f"decision log: {len(decided)} file(s)")
    for f in decided:
        print(f"  {f.name}: {f.read_text()}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["start"]:
            asyncio.run(start())
        case ["list"]:
            asyncio.run(show())
        case ["resume", *ckpt] if len(ckpt) <= 1:
            asyncio.run(wf._resume(*ckpt))  # the product code path, guard included
        case _:
            sys.exit(__doc__)
