# Notes — Compliance Evidence Workflow

Answers to the 3 questions in `compliance-evidence-workflow-brief.md` §6, written
against what was actually built and verified in this repo (not general theory).

## Required experiment: the lopsided fan-out

`src/experiments/lopsided_fanout.py` is a standalone demo graph (separate from the
real evidence workflow — decided during Phase 5 discussion, so an artificial
`asyncio.sleep()` never has to live in production node code):

```
start --+--> fast_a --> fast_b --> fast_c --+
        |                                    +--> finish (fan-in)
        +--> slow ---------------------------+
```

`fast_a/b/c` is a 3-node chain that does no real work; `slow` sleeps for 3 seconds.
Run with `python -m src.experiments.lopsided_fanout`. Observed output:

```
[  0.00s] start: fanning out 'seed' to fast_a and slow
[  0.05s] fast_a: relaying 'seed'
[  0.05s] slow: starting 3.0s of (simulated) work
[  3.06s] slow: finished
[  3.11s] fast_b: relaying 'seed->fast_a'
[  3.16s] fast_c: relaying 'seed->fast_a->fast_b'
[  3.21s] finish: barrier satisfied, both branches delivered: [...]
```

**This is a stronger result than "the fan-in waits for the slow branch."** `fast_a`
finishes at `0.05s`, but `fast_b` doesn't even *start* until `3.11s` — right after
`slow` completes. The fast chain doesn't run ahead of the slow branch and only get
blocked at the final aggregation; it's frozen after its very first hop. That's because
the framework executes in **supersteps** (bulk-synchronous, BSP-style): every executor
triggered in a given superstep must finish before *any* executor in the next superstep
starts, for the whole workflow, not just for one fan-in edge. `fast_a` and `slow` are
both triggered in superstep 1 (by `start`'s fan-out); `fast_b` can't run until superstep
2 begins, and superstep 2 can't begin until every executor in superstep 1 — `slow`
included — has completed. Concurrency exists *within* a superstep, not *across* it.

The direct, practical corollary for this project's real graph (Phase 3): if any one
of the 4 `evaluate_control` executors is slow (e.g. an LLM call with high latency once
Phase 6 swaps in real agents), it does not just delay `aggregate` — it holds up nothing
else in the sense that there's nothing else running concurrently to hold up in this
particular graph, but it does mean "4 evaluators run concurrently" (the M2 acceptance
test) is a claim about the current superstep only. A future evaluator with a much
higher latency variance would make the whole run's wall-clock time equal to its worst
evaluator's latency, not the average.

## Q1: Why does a fan-in node need different readiness logic than a conditionally-routed node?

They're answering two different questions, evaluated at two different points relative
to the data.

**Fan-in readiness** (`aggregate` in `src/graph.py`, wired via `add_fan_in_edges`) is a
**structural/cardinality** question, asked *before* any message content is even looked
at: "have all N declared sources delivered a message for this superstep?" The runtime
tracks this per edge group — it's bookkeeping about *how many* senders exist, not about
what any of them said. It literally cannot fire early: `aggregate` has no valid way to
run with 3 of 4 findings, because its handler signature is `list[Finding]` representing
the complete set, and the framework enforces at `.build()` time that a fan-in group
needs at least 2 sources in the first place (discovered empirically in Phase 2 — the
framework rejects `add_fan_in_edges([single_source], target)` outright with
`ValueError: FanInEdgeGroup must contain at least two sources`).

**Conditional-edge readiness** (`aggregate → human_review` / `aggregate → write_report`
in `src/graph.py`) is a **content** question, asked *the instant one message arrives*:
"does this specific message satisfy the predicate?" `lambda fs: fs.needs_review` runs
against the one `FindingSet` `aggregate` just produced — there is no "waiting for more
senders" concept here at all, because a conditional edge doesn't have multiple sources
to wait on; it has one source and a decision to make about what it sent.

Put differently: fan-in readiness is about **quantity of inputs** (do we have everyone
we're supposed to have?); conditional-edge readiness is about **quality of one input**
(does what we have route left or right?). A fan-in group that never receives all its
declared sources will hang forever waiting — that's a real deadlock risk if an
evaluator ever silently drops a message. A conditional edge can never hang this way;
every message it examines gets exactly one immediate yes/no per outgoing edge.

## Q2: What breaks if you resume a checkpoint against a changed graph, and how should the system detect that?

**What breaks:** a checkpoint's `state` and pending `messages` are keyed by executor id
and shaped by the edges that existed when it was written. If the graph has since
changed — a node renamed, an edge rewired, a handler's input/output type changed — the
checkpoint's data can reference an executor id that no longer exists, expect a message
type a handler no longer produces, or resume into a topology where the old routing
decision (e.g. a conditional edge's threshold logic) no longer makes sense. Silently
"resuming" onto a different graph could deliver a `Finding` to a node that now expects
something else, or skip a node that used to sit between two others — corrupting the run
without necessarily crashing it.

**How the system detects it — verified, not designed by us:** every `WorkflowCheckpoint`
stores a `graph_signature_hash`, computed from the workflow's topology when it was
built (`Workflow._hash_graph_signature(self.graph_signature)` in the framework's own
`_workflow.py`). On `--resume`, the runner compares the *current* graph's hash against
the hash stored in the checkpoint, before restoring any state. Confirmed by building a
deliberately different graph (same workflow name, only `ingest → one evaluator`, no
`aggregate`/`human_review`/`write_report`) and attempting to resume a checkpoint taken
from the real graph:

```
WorkflowCheckpointException: Workflow graph has changed since the checkpoint was
created. Please rebuild the original workflow before resuming.
```

So we didn't have to build this ourselves — the framework refuses to resume across a
structural change and fails loudly with a specific exception, rather than silently
proceeding with mismatched state. What we did have to build ourselves, and got wrong on
the first pass (see `TODO.md` Phase 4), is a related but distinct failure mode:
checkpoints are pickled, and a type not on `FileCheckpointStorage`'s allow-list fails to
*decode* — but that failure was not loud enough by default. Missing `FindingStatus`
(an enum) from `ALLOWED_CHECKPOINT_TYPES` caused `get_latest()` to silently skip the
unreadable checkpoint and fall back to an older, readable one, logging only a warning
to stderr — which in practice caused already-finished evaluator nodes to incorrectly
re-run on resume. The graph-hash check protects against *structural* drift; it does
nothing to protect against a *storage-layer* problem quietly returning stale-but-valid
data. Both are "the checkpoint doesn't match what you think it does," but only one of
them fails loudly out of the box.

## Q3: When would you *not* use a deterministic workflow, and reach for an autonomous orchestrator instead?

Based on what this project actually required a graph/executor framework for, versus
what it didn't:

**A deterministic workflow (what this project builds) fits when the *shape* of the
process is known in advance** — you can draw the boxes and arrows before you've seen a
single real input. `ingest → evaluate × 4 → aggregate → [conditional] → write_report`
was true on day one and never needed to change based on what a fixture actually
contained; only the *content* flowing through each fixed node varied (which is exactly
why type-safe steps and conditional-edges-on-state work well here — the branching logic
is a small, enumerable set of conditions on structured data, not an open-ended
decision). This also happens to be the only mode compatible with the durability story
we actually built and tested: checkpoint/resume relies on the graph having a fixed
`graph_signature_hash` to resume against, and reproducible per-node type contracts to
validate at `.build()` time. Neither of those concepts is meaningful if the set of
nodes-that-might-run is decided by the LLM at runtime.

**An autonomous orchestrator (an agent loop deciding its own next action/tool call)
fits better when the *shape* of the process can't be known ahead of time** — when the
number of steps, their order, or even which "controls" apply depends on what's
discovered along the way. Concretely, for something adjacent to this project: an
open-ended "investigate whether this service is BCDR-compliant" task where the agent
might need to decide *which* documents to pull, *how many* follow-up questions to ask
a service owner, or *whether* a discovered gap warrants pulling in an additional,
not-predetermined check — that's a search/reasoning problem over an unbounded action
space, not a fixed pipeline. Similarly, this project's own Phase 6 (swapping in real
Azure OpenAI calls for `evaluate_control`) is being done as a **contained substitution
inside a fixed node**, precisely to keep the deterministic-workflow property — if
instead each control's evaluation genuinely needed a variable number of tool calls to
gather evidence (e.g. "check three different systems until you find the failover log,
however many attempts that takes"), that logic would want to live inside an agent's own
loop, not be flattened into one `evaluate_control` handler's single LLM call.

The practical tell, based on what got easy vs. hard while building this: if you can
write the edges before writing the node bodies, and the acceptance tests are about
*structure* (as every milestone's acceptance test in this project was), you have a
deterministic workflow. If you can't describe the steps without already having run the
task once, you're describing an autonomous orchestrator instead.
