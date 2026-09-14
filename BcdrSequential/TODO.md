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

## Phase 3 — Parallel + conditional (M2)
- [ ] Fan out to all 4 `evaluate_control` executors; fan-in at `aggregate` (waits for
      all four); compute coverage stats.
- [ ] Conditional edge: route to `human_review` if any `Finding` is NEEDS_REVIEW or
      confidence < threshold (threshold in shared state, not hardcoded); else straight
      to `write_report`.
- [ ] `human_review`: surface flagged findings, pause for input, merge decision into
      state.
- [ ] **Acceptance test:** changing the threshold in state (not code) changes the
      routed branch; event stream shows all 4 evaluators running concurrently.
- [ ] Discuss: fan-in readiness vs. conditional-edge readiness — why they're different
      synchronization problems (this feeds directly into `NOTES.md` Q1).

## Phase 4 — Durability (M3)
- [ ] Checkpoint to disk after each step/superstep.
- [ ] Graph serialization: dump to JSON, reconstruct, confirm it still runs.
- [ ] `--resume <checkpoint-id>` CLI path.
- [ ] **Acceptance test:** `kill -9` mid-fan-out, then `--resume` completes without
      re-running already-finished nodes.
- [ ] Discuss: what checkpoint granularity costs you (superstep vs. per-node), and why
      resuming against a changed graph is dangerous (feeds `NOTES.md` Q2).
- [ ] Stretch, optional: move checkpoint store to Azure Cosmos DB
      (`CosmosCheckpointStorage`, `agent-framework-azure-cosmos`) — the framework's
      actual distributed backend, not Blob Storage as the brief assumed.

## Phase 5 — Required experiment + NOTES.md
- [ ] Build the deliberately lopsided fan-out (fast 2–3-node chain vs. one slow node);
      observe in the event stream that the fast chain stalls at the superstep barrier.
- [ ] Write `NOTES.md` answering the 3 brief questions (fan-in vs. conditional
      readiness; resuming a changed graph; when to prefer an autonomous orchestrator
      over a deterministic workflow).

## Phase 6 — Swap in real agents (required, not stretch)
Decided 2026-09-14: the rule-based `evaluate_control`/`write_report` stand-ins (see
Phase 2) are a deliberate placeholder, not the deliverable — once the graph shape is
finalized and tested (Phases 3-5 passing), swap their internals for real Azure OpenAI
calls. This is a "must," not optional, precisely because the brief's stack section
(§3) names Azure OpenAI/Foundry as the model and the six concepts are meant to be
exercised by an agentic workflow, not a pipeline of regexes wearing an agentic
framework's clothes.
- [ ] `evaluate_control` ×4: replace `_evaluate_<control_id>` heuristics with an
      Azure OpenAI `ChatAgent` call using each `ControlSpec.evaluation_prompt`,
      structured output parsed into `Finding`. Auth via `az login` +
      `DefaultAzureCredential`, endpoint/deployment from root `.env`.
- [ ] `write_report`: replace the hand-built markdown with an agent call that drafts
      the packet from `FindingSet` (still validated back into `EvidencePacket`).
- [ ] Re-run the M1-M3 acceptance tests against the swapped graph — confirm nothing
      about graph structure, streaming, checkpointing, or serialization had to change,
      only the two node internals. This is the actual proof of the type-safety claim
      made in Phase 2's discussion.
- [ ] Discuss: what changes about failure modes once these nodes are non-deterministic
      (model latency/timeouts, malformed structured output, cost) vs. the rule-based
      version — does checkpoint/resume behave any differently against a node that may
      have partially-billed a real API call before being killed?
- [ ] `ingest` stays deterministic/no-LLM per the brief — not in scope for this swap
      (see separate discussion on screenshot-based ingestion as a possible future
      extension, not part of this phase).

## Phase 7 — Wrap-up
- [ ] `python -m src.run --export-graph graph.json` works standalone.
- [ ] README pass: how to run, resume, export; what's simulated vs. real.
- [ ] Retro discussion: which of the 6 concepts felt most/least justified for this
      problem size, and where this toy version would need to grow up for a real BCDR
      pipeline.

## Explicitly cut unless time remains
- M4 (containerize + Azure Container Apps + cross-replica resume via Cosmos DB
  checkpoint store) — cut first.
- Prompt tuning / report quality, auth, multi-tenancy, web UI, DB, real data.
