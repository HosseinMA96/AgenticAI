"""Week 3, Step 12 (lesson): a paused approval that survives a real restart (book 4.13, Ch 6).

Two commands, two separate processes:
    uv run python lessons/w3_step12_approval_restart.py start      # runs until the human pause, then EXITS
    uv run python lessons/w3_step12_approval_restart.py resume y   # a new process answers it (y or n)
    uv run python lessons/w3_step12_approval_restart.py resume-old n  # break it: answer again from the OLD paused checkpoint

No model calls: the claim is fixed text, so the lesson is only about pause → checkpoint → resume.
"""

import asyncio
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from agent_framework import (
    Executor, FileCheckpointStorage, WorkflowBuilder, WorkflowContext, handler, response_handler,
)
from typing_extensions import Never

CHECKPOINTS = Path(__file__).parent / "_out" / "checkpoints_step12"


@dataclass
class Claim:
    text: str
    confidence: str


@dataclass
class ReviewRequest:
    claim: Claim


@dataclass
class ReviewDecision:
    approved: bool


class Drafter(Executor):
    def __init__(self) -> None:
        super().__init__(id="drafter")

    @handler
    async def draft(self, question: str, ctx: WorkflowContext[Claim]) -> None:
        await ctx.send_message(Claim(text="Adobe's FY2022 operating margin was about 35%.", confidence="low"))


class Reviewer(Executor):
    def __init__(self) -> None:
        super().__init__(id="reviewer")

    @handler
    async def ask(self, claim: Claim, ctx: WorkflowContext) -> None:
        print(f"  ⏸  pausing for a human: {claim.text!r} (confidence={claim.confidence})")
        await ctx.request_info(ReviewRequest(claim=claim), ReviewDecision)

    @response_handler  # runs when the answer arrives: maybe in a different process, hours later
    async def decide(self, req: ReviewRequest, d: ReviewDecision, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"{'APPROVED' if d.approved else 'REJECTED'} by reviewer: {req.claim.text}")


def build(storage: FileCheckpointStorage):
    # The same graph must be rebuilt on resume: MAF compares a hash of it with the checkpoint's.
    drafter, reviewer = Drafter(), Reviewer()
    return (WorkflowBuilder(start_executor=drafter, name="step12", checkpoint_storage=storage)
            .add_edge(drafter, reviewer).build())


def storage() -> FileCheckpointStorage:
    # Our dataclasses are pickled, so they must be on the allow-list (a missing one fails silently).
    types = [f"{__name__}:{n}" for n in ("Claim", "ReviewRequest", "ReviewDecision")]
    return FileCheckpointStorage(CHECKPOINTS, allowed_checkpoint_types=types)


async def start() -> None:
    shutil.rmtree(CHECKPOINTS, ignore_errors=True)
    CHECKPOINTS.mkdir(parents=True)
    result = await build(storage()).run("What was Adobe's FY2022 operating margin?")
    pending = result.get_request_info_events()
    print(f"  run returned with {len(pending)} pending request(s); outputs so far: {result.get_outputs()}")
    print("  process exiting now. Nothing is in memory any more; only the checkpoint files on disk.")


async def resume(approved: bool, *, old: bool = False) -> None:
    store = storage()
    if old:  # every superstep left a checkpoint; pick the last one that was still waiting
        latest = [c for c in await store.list_checkpoints(workflow_name="step12") if c.pending_request_info_events][-1]
    else:
        latest = await store.get_latest(workflow_name="step12")
    if latest is None:
        sys.exit("no checkpoint found: run `start` first")
    request_ids = list(latest.pending_request_info_events)
    print(f"  new process. Latest checkpoint {latest.checkpoint_id[:8]}… holds pending request(s): {request_ids}")
    # One call restores the paused state AND delivers the human's answer.
    result = await build(store).run(checkpoint_id=latest.checkpoint_id,
                                    responses={rid: ReviewDecision(approved=approved) for rid in request_ids})
    print(f"  output: {result.get_outputs()}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["start"]:
            asyncio.run(start())
        case ["resume", answer]:
            asyncio.run(resume(answer.lower() == "y"))
        case ["resume-old", answer]:
            asyncio.run(resume(answer.lower() == "y", old=True))
        case _:
            sys.exit(__doc__)
