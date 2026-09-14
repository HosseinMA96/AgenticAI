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
      **Confirmed API:** `WorkflowBuilder(start_executor=...)`, `.add_edge(a, b,
      condition=fn)`, `.add_fan_in_edges([...], target)`, `.build()` (validates at
      build time), `workflow.run(input, stream=True)`. Superstep/BSP execution model
      confirms the brief's §6 lopsided fan-out behavior directly.
      **Deviation from brief:** the brief's M3 names Blob Storage as the distributed
      checkpoint backend; the framework's actual distributed offering is
      `CosmosCheckpointStorage` (package `agent-framework-azure-cosmos`), not Blob.
      Adopting Cosmos for M4 instead — same learning goal (externalized state →
      stateless workers), just the real supported backend.

## Phase 1 — Scaffold + contracts (M1 groundwork)
- [ ] Repo layout per brief §4 (`pyproject.toml`, `.env.example`, `fixtures/`, `src/`,
      `checkpoints/` gitignored, `tests/`). Discuss: uv/poetry/pip choice, Python
      version, why `.env` + `DefaultAzureCredential` over static keys.
- [ ] `models.py` — Pydantic types (`ArtifactSet`, `ControlSpec`, `Finding`,
      `FindingSet`, `EvidencePacket`). Discuss: strictness of validation, why
      typed steps matter for catching errors at build time vs. runtime.
- [ ] `controls.py` — 4 `ControlSpec`s (rto_documented, rollback_path,
      failover_test_recent, contacts_current). Discuss prompt design tradeoffs later,
      not yet — keep specs minimal for now.
- [ ] Generate `fixtures/svc-alpha/` synthetic bundle (failover log, runbook.md,
      config.json) — messy enough that one control clearly FAILs and one lands in
      NEEDS_REVIEW. Discuss: how realism vs. simplicity tradeoff plays out here.

## Phase 2 — Sequential spine (M1)
- [ ] Build `ingest` (deterministic) → one `evaluate_control` → `aggregate` →
      `write_report`, wired with the framework's executor/edge/builder pattern.
- [ ] Streaming: print per-step events as they happen.
- [ ] **Acceptance test:** intentionally mismatch a type between two nodes → graph
      build fails before any model call.
- [ ] Discuss: what "type-safe step" actually buys you here vs. a plain Python
      function pipeline.

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

## Phase 6 — Wrap-up
- [ ] `python -m src.run --export-graph graph.json` works standalone.
- [ ] README pass: how to run, resume, export; what's simulated vs. real.
- [ ] Retro discussion: which of the 6 concepts felt most/least justified for this
      problem size, and where this toy version would need to grow up for a real BCDR
      pipeline.

## Explicitly cut unless time remains
- M4 (containerize + Azure Container Apps + cross-replica resume via Cosmos DB
  checkpoint store) — cut first.
- Prompt tuning / report quality, auth, multi-tenancy, web UI, DB, real data.
