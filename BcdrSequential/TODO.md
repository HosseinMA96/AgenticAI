# TODO — Compliance Evidence Workflow (learning project)

Golden rule for every step below: before writing code, discuss the options/tradeoffs
and let the user (BCDR compliance background, new to agentic frameworks) choose. Land
on a decision + "why" before moving on. Scope ≤ 1 week; simplify ruthlessly, but keep
all 6 concepts from the brief (type-safe steps, conditional edges, fan-out/fan-in,
streaming, serialization, checkpoint/resume).

## Phase 0 — Orient (BCDR + framework) ✅
- [x] Discuss real-world BCDR compliance evidence review: what controls actually get
      checked (RTO/RPO docs, failover test recency, rollback path, contact trees),
      who reviews them, what "evidence" means to an auditor. Map this project's 4
      controls back to that reality — what's simplified away and why.
- [x] Confirm current Microsoft Agent Framework API from official docs/samples
      (executors, edges, builder, checkpointing, DevUI, OTel integration). Note any
      drift from the brief before coding. Discuss: why a graph/executor framework at
      all vs. hand-rolled orchestration vs. an autonomous agent loop — tradeoffs.
      **Confirmed API (verified against installed `agent-framework==1.18.0`, 2026-09-14):**
      `Executor` subclasses hold `@handler`-decorated async methods whose typed
      signature (`WorkflowContext[OutT]`) is what the builder validates — there's no
      separate "node function" concept. `WorkflowBuilder(start_executor=...,
      checkpoint_storage=...)`, `.add_edge(a, b, condition=fn)`, `.add_fan_out_edges`,
      `.add_fan_in_edges([...], target)`, `.build()` (validates at build time).
      `workflow.run(message, stream=True, checkpoint_id=..., checkpoint_storage=...)`
      returns a `ResponseStream[WorkflowEvent, WorkflowRunResult]` when streaming.
      Checkpointing is wired via constructor arg, not a separate `.with_checkpointing()`
      call as Phase-0 first assumed. Superstep/BSP execution model confirms the
      brief's §6 lopsided fan-out behavior directly.
      **Deviation from brief:** the brief's M3 names Blob Storage as the distributed
      checkpoint backend; the framework's actual distributed offering is
      `CosmosCheckpointStorage` (package `agent-framework-azure-cosmos`), not Blob.
      Adopting Cosmos for M4 instead — same learning goal (externalized state →
      stateless workers), just the real supported backend.

## Phase 1 — Scaffold + contracts (M1 groundwork) ✅
- [x] Repo layout per brief §4 (`pyproject.toml`, `.env.example`, `fixtures/`, `src/`,
      `checkpoints/` gitignored, `tests/`). Decided: uv, Python 3.12, `.env` +
      `DefaultAzureCredential` over static keys.
- [x] `models.py` — Pydantic types (`ArtifactSet`, `ControlSpec`, `Finding`,
      `FindingSet`, `HumanReviewDecision`, `EvidencePacket`). Decided: strict
      (`extra="forbid"`, frozen) — human_review builds new instances rather than
      mutating, keeping with the type-safety theme.
- [x] `controls.py` — 4 `ControlSpec`s (rto_documented, rollback_path,
      failover_test_recent, contacts_current). Prompt wording kept minimal —
      tuning is a non-goal.
- [x] Generated three synthetic fixture bundles (failover log, runbook.md,
      config.json each): `fixtures/svc-alpha/` (mixed — PASS/NEEDS_REVIEW/FAIL/PASS),
      `fixtures/svc-beta/` (clean — all PASS), `fixtures/svc-gamma/` (troubled —
      mostly FAIL with one NEEDS_REVIEW from an ambiguous/crashed test log).

## Phase 2 — Sequential spine (M1) ✅
- [x] Built `ingest` (deterministic) → `evaluate_control(rto_documented)` →
      `aggregate` → `write_report`, wired with `WorkflowBuilder`/`add_edge`/`.build()`.
      `evaluate_control` and `write_report` are deterministic/rule-based for now, not
      LLM calls — see decision note in `src/nodes/evaluate.py`'s docstring: the M1/M2
      acceptance tests are about graph structure, not model judgment, and swapping in
      a real Azure OpenAI-backed ChatAgent later is meant to be a localized change
      given the fixed Pydantic contracts.
- [x] Streaming: `src/run.py` iterates `workflow.run(service_id, stream=True)` and
      prints each `WorkflowEvent`; `executor_invoked`/`executor_completed` are emitted
      automatically by the framework per handler call, no manual instrumentation needed.
- [x] **Acceptance test passing:** wiring `evaluate_rto` directly into `write_report`
      (skipping `aggregate`) raises `TypeCompatibilityError` at `.build()`, before
      `workflow.run()` is ever called.
- [x] Discussed: type-safe steps catch a wiring mistake (missing aggregate node,
      wrong model passed downstream) at construction time — a plain function pipeline
      would only fail when that code path actually executes, possibly deep into a run
      with side effects already applied upstream.
- [x] Verified all three fixtures produce distinct, plausible finding sets end-to-end
      (svc-alpha: PASS/NEEDS_REVIEW/FAIL/PASS; svc-beta: all PASS; svc-gamma:
      FAIL/NEEDS_REVIEW/NEEDS_REVIEW/FAIL) — tuned `_evaluate_failover_test_recent` so
      an overdue test fails regardless of its last recorded outcome, matching the
      intended fixture story.

## Phase 3 — Parallel + conditional (M2) ✅
- [x] Fanned out `ingest` to all 4 `EvaluateControlExecutor` instances via
      `add_fan_out_edges` (broadcasts the same `ArtifactSet` concurrently); fan-in at
      `aggregate` via `add_fan_in_edges` (barrier — only runs once all 4 complete;
      framework requires >=2 sources for a fan-in group, confirming the Phase 2 note
      that a single-source "fan-in of one" isn't legal). `aggregate`'s handler
      signature changed from `Finding` to `list[Finding]` as flagged in Phase 2.
- [x] Conditional edge: `add_edge(aggregate, human_review, condition=...)` /
      `add_edge(aggregate, write_report, condition=...)` routing on
      `FindingSet.needs_review`. Threshold is no longer hardcoded — added a typed
      `RunRequest{service_id, confidence_threshold}` as the workflow's actual input
      type (replacing the bare `str`), which `ingest` pushes into shared state via
      `ctx.set_state`; `aggregate` and `human_review` both read it back via
      `ctx.get_state`. Decided against a hidden CLI side-channel specifically so the
      threshold stays inside the type-safety story.
- [x] `human_review`: decided (discussed before coding) on a blocking `input()` prompt
      in the executor's own handler over the framework's `request_info` mechanism —
      simpler, one fewer framework concept to learn this week, and a better fit for
      Phase 4's `kill -9` test (killing a process blocked on stdin mid-superstep is
      exactly what checkpoint/resume needs to prove out). Resolved findings are new
      `Finding` instances via `model_copy(update=...)` since `Finding` is frozen;
      decisions recorded as `HumanReviewDecision` in state for an audit trail.
- [x] **Acceptance test passing:** `--threshold 0.6` on `svc-beta` (all findings
      confidence >=0.9) skips `human_review` entirely (0 prompts); `--threshold 0.99`
      on the same fixture, same code, routes all 4 findings through `human_review` (4
      prompts) — threshold change alone flips the branch. Event stream confirms all 4
      evaluators' `executor_invoked` land in one superstep before `aggregate` starts.
- [x] Discussed: fan-in readiness is "have all N sources delivered for this
      superstep?" — a structural/cardinality question the runtime tracks per edge
      group. Conditional-edge readiness is "does this one message's *content* satisfy
      the predicate?" — evaluated per-message, no waiting on other sources. Fan-in
      can't fire early; a conditional edge doesn't wait at all. (Captured for
      `NOTES.md` Q1.)

## Phase 4 — Durability (M3) ✅
- [x] Checkpoint to disk after each superstep, via `FileCheckpointStorage("checkpoints")`
      passed into `WorkflowBuilder(checkpoint_storage=...)`. Confirmed against the
      framework's own code comment: `"The runner only checkpoints after each
      superstep"` — not per-node, which matters for what "already-finished" means
      below.
      **Real gotcha found and fixed:** checkpoints are pickled, and the framework
      refuses to deserialize any type not explicitly allow-listed (a real guard
      against arbitrary code execution from a tampered checkpoint file). Every
      Pydantic model that crosses an edge — including the `FindingStatus` enum,
      easy to miss — must be listed in `ALLOWED_CHECKPOINT_TYPES` (`src/run.py`).
      Missing one doesn't hard-fail: `get_latest()` silently falls back to an older
      *readable* checkpoint and logs a warning to stderr, which on first pass caused
      already-finished evaluator nodes to incorrectly re-run on resume. Caught by
      actually testing the resume, not by reasoning about it — the acceptance test
      below failed on the first attempt for exactly this reason.
- [x] Graph serialization: `Workflow.to_json()` produces a real topology dump, but
      **`Workflow.from_json()` has no working path back to a runnable `Workflow`** —
      verified directly (`Workflow.__init__() got an unexpected keyword argument
      'id'`), not assumed. Discussed and decided: "reconstruct" for concept 5 means
      parse the JSON back into a dict and assert it structurally matches the live
      graph (executor ids, types, edge count, start executor) — see
      `tests/test_graph.py::test_graph_json_dump_matches_live_structure`. Actually
      *running* after a restart is what checkpoint/resume (concept 6) covers, and
      that's real and tested below. Also added `EvaluateControlExecutor.to_dict`/
      `from_dict` overrides (the base `Executor.to_dict()` only captures `{id, type}`,
      not the `control_id` needed to rebuild it) — correct and tested on its own
      (`test_evaluate_control_executor_round_trips_via_dict`), even though it wasn't
      sufficient by itself to fix the bigger `Workflow`-level gap.
- [x] `--resume <checkpoint-id>` CLI path; `--export-graph <path>` for the topology dump.
- [x] **Acceptance test passing (verified manually, not automated — see
      `tests/test_graph.py` docstring for why):** launched `svc-alpha` with a FIFO as
      stdin so `human_review`'s `input()` call genuinely blocks (confirmed via `ps`
      showing sleep state `Sl`), `kill -9`'d it mid-prompt, confirmed 4 checkpoints on
      disk (through the end of `aggregate`'s superstep — `human_review`'s superstep
      never completed, so per the checkpoint-granularity fact above it wasn't
      captured). `--resume`'d from the latest checkpoint: event stream showed only
      `human_review` and `write_report` re-invoked — `ingest` and all 4 evaluators did
      not re-run. `human_review` re-running is correct, not a bug: it never finished.
- [x] Discussed: checkpoint granularity is per-superstep, not per-node — killing
      mid-superstep loses that whole step's progress, not just the one node that was
      running (a real cost, traded for simplicity: no partial-superstep bookkeeping).
      Resuming against a changed graph is dangerous because the persisted messages/
      state reference executor ids and edge shapes that may no longer exist or mean
      something different — **the framework already detects this itself** via a
      `graph_signature_hash` stored in every checkpoint; verified by building a
      deliberately different graph under the same workflow name and confirming
      `WorkflowCheckpointException: Workflow graph has changed since the checkpoint
      was created` fires on resume. (Both captured for `NOTES.md` Q2.)
- [ ] Stretch, optional: move checkpoint store to Azure Cosmos DB
      (`CosmosCheckpointStorage`, `agent-framework-azure-cosmos`) — the framework's
      actual distributed backend, not Blob Storage as the brief assumed.

## Phase 5 — Required experiment + NOTES.md ✅
- [x] Built the lopsided fan-out as a standalone demo graph, `src/experiments/
      lopsided_fanout.py` (discussed and decided: separate from the real evidence
      workflow, so an artificial `asyncio.sleep()` never has to live in production
      node code). `start` fans out to a 3-node fast chain (`fast_a → fast_b → fast_c`)
      and one `slow` node (3s sleep); both fan back in at `finish`.
      **Result was stronger than expected — verified by running it, not assumed:**
      `fast_a` completes at `0.05s`, but `fast_b` doesn't even *start* until `3.11s`,
      right after `slow` finishes. It's not just that the final fan-in waits — the
      *entire* workflow advances in lockstep supersteps (BSP-style), so the fast
      chain is frozen after its first hop, not just blocked at the finish barrier.
      Full run log and the implication for this project's real evaluator nodes
      captured in `NOTES.md`.
- [x] Wrote `NOTES.md` answering all 3 brief questions, grounded in what was actually
      verified while building Phases 3-4 rather than general theory: Q1 (fan-in
      readiness = structural/cardinality question asked before content is seen;
      conditional-edge readiness = content question asked the instant one message
      arrives), Q2 (the framework already detects a changed graph via
      `graph_signature_hash`, verified by triggering the actual
      `WorkflowCheckpointException`; contrasted against the *silent* checkpoint
      allow-list bug from Phase 4, which is a related but distinct failure mode that
      does NOT fail loudly by default), Q3 (deterministic workflow fits when the
      graph's shape is knowable before seeing any input — true of every milestone's
      acceptance test in this project; autonomous orchestrator fits when the number/
      order of steps depends on what's discovered at runtime).

## Phase 6 — Swap in real agents (required, not stretch) ✅
Decided 2026-09-14: the rule-based `evaluate_control`/`write_report` stand-ins (see
Phase 2) are a deliberate placeholder, not the deliverable — once the graph shape is
finalized and tested (Phases 3-5 passing), swap their internals for real Azure OpenAI
calls. This is a "must," not optional, precisely because the brief's stack section
(§3) names Azure OpenAI/Foundry as the model and the six concepts are meant to be
exercised by an agentic workflow, not a pipeline of regexes wearing an agentic
framework's clothes.

**Real-environment findings before coding (checked, not assumed):** `agent_framework`
has no `ChatAgent` in this installed version (1.18.0) — it's `Agent`. Structured
output is `agent.run(prompt, options={"response_format": SomeModel})`, read back via
`response.value`. The right client is `agent_framework.openai.OpenAIChatClient` (its
`azure_endpoint=`/`api_key=`/`credential=` params) — not `agent_framework.foundry`,
which targets a different Azure AI Foundry *Agent Service* project shape the shared
`.env` isn't configured for. **Auth convention corrected:** this file originally said
`az login`/`DefaultAzureCredential`, but the actual shared root `.env` has a static
`AZURE_OPENAI_API_KEY` that every sibling `Dummy/Pre6/dummy*.py` script already
authenticates with directly — matched that established convention instead (see
`src/llm.py`, `.env.example`, updated auth section above).
- [x] `evaluate_control` ×4 (`src/nodes/evaluate.py`): replaced the heuristics with an
      `Agent` call per control using `ControlSpec.evaluation_prompt`, structured
      output into a local `ControlJudgment` model (narrower than `Finding` — no
      `control_id`, since that's already known), then mapped into `Finding`. A failed
      or malformed call degrades to `NEEDS_REVIEW`/confidence `0.0` rather than
      crashing the node — one control's model hiccup routes to human review instead
      of failing the whole run.
- [x] **Correction (user-caught, same day):** the first cut of `_judge` passed *all
      three* raw artifact files into every control's prompt, regardless of
      relevance — not a fan-out bug (4 separate `EvaluateControlExecutor` instances
      already made 4 independent `agent.run()` calls, confirmed via the event stream
      showing separate `executor_invoked`/`executor_completed` pairs per control),
      but noise in what each individual call saw. Added `ControlSpec.relevant_artifacts`
      (`src/models.py`) — e.g. `rto_documented`/`rollback_path` -> `runbook_markdown`
      only, `failover_test_recent` -> `failover_log` only, `contacts_current` ->
      `config` only — and scoped each prompt accordingly. Re-verified with a real call
      (`contacts_current` against `svc-gamma`: correctly saw only `config.json`,
      correctly FAILed on the `"TBD"`/empty-field placeholders) and a full end-to-end
      `svc-gamma` run; all 4 structural tests still pass unchanged.
- [x] `write_report` (`src/nodes/report.py`): kept the findings table deterministic
      (facts computed upstream — an agent restating them risks hallucinating a
      different number, a real correctness problem for something meant to double as
      audit evidence); the agent's job is the overall verdict + reason.
- [x] **Extension (user-proposed, same day):** `write_report`'s agent now calls a real
      tool — `write_evidence_file(verdict, reason)` — to persist a structured
      `reports/{service_id}.md` (gitignored, like `checkpoints/`). This is the
      project's first exercise of actual tool/function-calling, distinct from
      `response_format` structured output used in `evaluate.py`. Confirmed via a toy
      weather-tool test first: `Agent(tools=[...])` auto-executes a plain Python
      function within `agent.run()` — no manual tool-call handling needed. The tool's
      signature deliberately excludes the per-control findings as arguments (only
      `verdict`/`reason`) — those are injected via closure from the already-computed
      `FindingSet`, so the model has no chance to restate (and possibly hallucinate) a
      fact it didn't need to touch, keeping the same deterministic-facts-vs-agent-
      judgment split as everywhere else in this project. Falls back to a
      deterministically-computed verdict (NON_COMPLIANT if any FAIL, else
      NEEDS_REVIEW if `needs_review`, else COMPLIANT) if the agent call fails or never
      calls the tool, so a report always exists.
      Verified against a real endpoint: `svc-gamma` (all FAIL) correctly produced
      `NON_COMPLIANT` with a grounded reason and a real file on disk matching the
      workflow's own output exactly; `svc-beta` (all PASS) correctly produced
      `COMPLIANT`.
- [x] **Extension (user-proposed, same day): Notes column with source attribution.**
      Added `Finding.notes` (why the decision was made) and `Finding.notes_source`
      (`AGENT`/`HUMAN`/`SYSTEM`) to `models.py`. `evaluate.py` now populates `notes`
      from `ControlJudgment.rationale` (previously computed and silently discarded!)
      with source `AGENT`, or the failure explanation with source `SYSTEM` on the
      error-fallback path. `human_review.py` now **replaces** `notes` with the
      reviewer's own note and flips `notes_source` to `HUMAN` when a finding is
      overridden — the report should reflect why the *recorded* decision was made,
      and once a human overrides a finding, that's the human's call, not the model's;
      the original agent rationale is still shown at the review prompt for context,
      just not retained afterward. `report.py`'s table gained a `Notes` column
      rendered as `(Agent|Human|System) <text>`, with pipe/newline sanitization so
      free-text notes can't corrupt the markdown table structure.
      Verified against a real endpoint end-to-end on `svc-alpha`: the table correctly
      showed `(Agent)` with the model's actual rationale for 3 untouched controls, and
      `(Human)` with the exact reviewer-typed note (not the original agent rationale)
      for the one control (`rollback_path`) that went through `human_review`.
- [x] Verified against a real Azure OpenAI endpoint, not mocked: ran a single
      `_judge()` call directly (sensible PASS + rationale for `rto_documented` on
      `svc-alpha`), then the full graph end-to-end for both `svc-alpha` (mixed
      findings, correctly routed to `human_review` on a real NEEDS_REVIEW from the
      model, resolved, reached `write_report`) and `svc-beta` (all real PASS, skipped
      review, coherent narrative summary).
- [x] Re-ran `tests/test_graph.py` (all 4 acceptance tests) after the swap — all still
      pass, unchanged. This is the actual proof of the type-safety claim made in
      Phase 2's discussion: swapping two nodes' internals for a live external API
      required zero changes to the graph, edges, or any acceptance test.
- [x] Discussed: checkpoint timing changes the *cost* of a kill, not just the *state*.
      Phase 4's kill test hit `human_review` blocked on local `input()` — free to
      re-run. A kill mid-`evaluate_control` now means killing a process that may be
      mid-flight on a real, billed Azure OpenAI call: since checkpoints only commit
      after a full superstep (confirmed in Phase 4), that call's result — and its
      cost — isn't persisted, so `--resume` re-runs the evaluator and pays for the
      call again. Not a correctness bug (the framework's checkpoint/resume behavior
      is unchanged), but a real operational cost that didn't exist with the
      rule-based stand-in and would matter at production scale. No mitigation
      implemented — flagging it is the point here, and building idempotency/dedup
      around a paid call is explicitly beyond this project's non-goals.
- [x] `ingest` stays deterministic/no-LLM per the brief — not in scope for this swap
      (see separate discussion on screenshot-based ingestion as a possible future
      extension, not part of this phase).

## Phase 7 — Wrap-up
- [x] `python -m src.run --export-graph graph.json` works standalone (verified after
      Phase 6's changes to `evaluate.py`/`report.py`) — no network call, all 8
      executors present, `control_id` round-trips correctly on the custom
      `EvaluateControlExecutor`, and `test_graph_json_dump_matches_live_structure`
      still passes.
- [ ] README pass: how to run, resume, export; what's simulated vs. real.
- [ ] Retro discussion: which of the 6 concepts felt most/least justified for this
      problem size, and where this toy version would need to grow up for a real BCDR
      pipeline.

## Explicitly cut unless time remains
- M4 (containerize + Azure Container Apps + cross-replica resume via Cosmos DB
  checkpoint store) — cut first.
- Prompt tuning / report quality, auth, multi-tenancy, web UI, DB, real data.
