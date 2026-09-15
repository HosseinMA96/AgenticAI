"""Brief §6 required experiment: a deliberately lopsided fan-out.

A standalone demo graph, separate from the real evidence workflow (decided
in Phase 5 discussion — keeps an artificial sleep() out of production node
code, even gated). It has nothing to do with BCDR controls; it exists only
to make one fact from the framework's superstep/BSP execution model visible
in the event stream:

    start --+--> fast_a --> fast_b --> fast_c --+
            |                                    +--> finish (fan-in)
            +--> slow ---------------------------+

`fast_a/b/c` is a 3-node chain that finishes in milliseconds. `slow` sleeps
for a few seconds. Both branches are triggered by the same fan-out
superstep. Because `finish` is a fan-in barrier, it cannot run until BOTH
branches have delivered a message — so despite the fast chain finishing
almost immediately, `finish` is observably delayed until `slow` completes.
Run it and watch the timestamps:

    python -m src.experiments.lopsided_fanout
"""

import asyncio
import time

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

START_TIME = time.monotonic()


def _elapsed() -> str:
    return f"{time.monotonic() - START_TIME:6.2f}s"


class StartExecutor(Executor):
    @handler
    async def start(self, seed: str, ctx: WorkflowContext[str]) -> None:
        print(f"[{_elapsed()}] start: fanning out '{seed}' to fast_a and slow")
        await ctx.send_message(seed)


class FastStepExecutor(Executor):
    """One link in the 3-node fast chain — does no real work, just relays."""

    @handler
    async def step(self, value: str, ctx: WorkflowContext[str]) -> None:
        print(f"[{_elapsed()}] {self.id}: relaying '{value}'")
        await ctx.send_message(f"{value}->{self.id}")


class SlowStepExecutor(Executor):
    """The lopsided branch: a single node that takes several seconds."""

    def __init__(self, id: str, delay_seconds: float):
        super().__init__(id=id)
        self._delay_seconds = delay_seconds

    @handler
    async def step(self, value: str, ctx: WorkflowContext[str]) -> None:
        print(f"[{_elapsed()}] {self.id}: starting {self._delay_seconds}s of (simulated) work")
        await asyncio.sleep(self._delay_seconds)
        print(f"[{_elapsed()}] {self.id}: finished")
        await ctx.send_message(f"{value}->{self.id}")


class FinishExecutor(Executor):
    """Fan-in barrier: cannot run until both fast_c and slow have delivered."""

    @handler
    async def finish(self, results: list[str], ctx: WorkflowContext[None, str]) -> None:
        print(f"[{_elapsed()}] finish: barrier satisfied, both branches delivered: {results}")
        await ctx.yield_output(f"done at {_elapsed()}")


def build_lopsided_graph(slow_delay_seconds: float = 3.0):
    start = StartExecutor(id="start")
    fast_a = FastStepExecutor(id="fast_a")
    fast_b = FastStepExecutor(id="fast_b")
    fast_c = FastStepExecutor(id="fast_c")
    slow = SlowStepExecutor(id="slow", delay_seconds=slow_delay_seconds)
    finish = FinishExecutor(id="finish")

    return (
        WorkflowBuilder(start_executor=start)
        .add_fan_out_edges(start, [fast_a, slow])
        .add_edge(fast_a, fast_b)
        .add_edge(fast_b, fast_c)
        .add_fan_in_edges([fast_c, slow], finish)
        .build()
    )


async def main() -> None:
    workflow = build_lopsided_graph()
    stream = workflow.run("seed", stream=True)
    async for event in stream:
        if event.type in ("executor_invoked", "executor_completed"):
            print(f"[{_elapsed()}] event: {event.type} executor={event.executor_id}")
    result = await stream.get_final_response()
    print(f"[{_elapsed()}] workflow output: {result.get_outputs()}")


if __name__ == "__main__":
    asyncio.run(main())
