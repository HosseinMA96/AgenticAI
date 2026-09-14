# Project Brief: Compliance Evidence Workflow

A 2–3 day learning project to internalize graph-based agentic workflows (deterministic
orchestration, as opposed to autonomous agent loops).

---

## 1. Purpose

This is a **learning project**, not a product. The deliverable is working code that
exercises six specific concepts. Optimize for exercising the concepts, not for output
quality of the generated report.

The six concepts, all of which must appear in the final code:

1. **Type-safe steps** — every node has a declared input and output type (Pydantic), validated before execution.
2. **Conditional edges** — routing decided by step output and by shared workflow state.
3. **Fan-out / fan-in** — parallel branches that converge on a node which waits for all of them.
4. **Streaming observability** — a run emits events per step, consumable in real time.
5. **Serialization** — the graph can be dumped to JSON and reconstructed.
6. **Checkpoint and resume** — a run can be killed mid-execution and resumed from persisted state, ideally by a *different* process.

---

## 2. What it does

Input: a service identifier plus a bundle of raw artifacts (a failover test log, a runbook
in markdown, a JSON config export).

Output: an evidence packet in markdown containing a per-control findings table and a
coverage summary.

**All input data is synthetic and lives in the repo.** Do not connect to any real system,
API, or tenant. Generating a realistic `fixtures/` directory is part of task 1.

### Graph

```
              ┌─→ evaluate_control("rto_documented")      ─┐
              │                                            │
ingest ──────►├─→ evaluate_control("rollback_path")       ─┤──► aggregate ──► [conditional]
(deterministic)│                                           │                     │
              ├─→ evaluate_control("failover_test_recent")─┤        needs_review │  clean
              │                                            │             ▼       ▼
              └─→ evaluate_control("contacts_current")    ─┘      human_review ──► write_report
                                                                                    │
                                                                                    ▼
                                                                                 packet.md
```

| Node | Kind | Notes |
|---|---|---|
| `ingest` | deterministic | Parses the artifact bundle into a typed `ArtifactSet`. No LLM. |
| `evaluate_control` × 4 | agent | One instance per control. Returns a typed `Finding`. Deliberately vary their latency (one should be noticeably slower) — see §6. |
| `aggregate` | deterministic | Fan-in. Waits for **all** evaluators. Computes coverage stats. |
| conditional edge | — | Routes to `human_review` if any finding is `NEEDS_REVIEW` or `confidence < threshold`; otherwise straight to `write_report`. Threshold read from shared state, not hardcoded. |
| `human_review` | pause point | Surfaces flagged findings, waits for input, merges the decision back into state. |
| `write_report` | agent | Produces the markdown packet. |

### Types

Define these as Pydantic models before writing any node logic:

- `ArtifactSet` — parsed inputs
- `ControlSpec` — id, description, evaluation prompt
- `Finding` — `control_id`, `status` (`PASS` / `FAIL` / `NEEDS_REVIEW`), `evidence_ref`, `confidence: float`
- `FindingSet` — aggregated findings plus coverage stats
- `EvidencePacket` — final output

---

## 3. Stack

- **Language:** Python
- **Framework:** Microsoft Agent Framework (`pip install agent-framework`)
- **Model:** Azure OpenAI via Microsoft Foundry (Azure credits available; use `az login` / DefaultAzureCredential rather than committing keys)
- **Observability:** the framework's built-in OpenTelemetry integration → Application Insights
- **Dev UI:** the framework ships a DevUI for visualizing and debugging the graph — use it

Framework concepts map roughly as: executors are the nodes, edges carry typed messages
between them, and a builder assembles the graph and validates it before it runs.

**Important:** verify the current API against the official documentation before writing
code. Do not rely on recalled method signatures — this framework is recent and the API
has changed across releases. Check the docs and the repo's own samples first.

---

## 4. Repo layout

```
compliance-evidence-workflow/
├── pyproject.toml
├── .env.example              # azure endpoint + deployment name; no secrets committed
├── fixtures/
│   └── svc-alpha/            # synthetic artifacts
├── src/
│   ├── models.py             # Pydantic contracts
│   ├── controls.py           # ControlSpec definitions
│   ├── nodes/
│   │   ├── ingest.py
│   │   ├── evaluate.py
│   │   ├── aggregate.py
│   │   └── report.py
│   ├── graph.py              # builds and validates the workflow
│   └── run.py                # CLI: run / resume / export-graph
├── checkpoints/              # gitignored
└── tests/
```

CLI surface to aim for:

```
python -m src.run --service svc-alpha              # fresh run, streaming output
python -m src.run --service svc-alpha --resume <checkpoint-id>
python -m src.run --export-graph graph.json
```

---

## 5. Milestones

Each milestone has an acceptance test. Don't advance without it passing.

**M1 — Sequential spine (day 1)**
Ingest → one evaluator → aggregate → report, running end to end with streaming events
printed per step.
*Accept when:* a deliberately mismatched type between two nodes causes a failure **at
graph build time**, before any model call is made.

**M2 — Parallel and conditional (day 2)**
Fan out to all four evaluators, fan in at aggregate, add the conditional edge and the
review branch. Confidence threshold lives in shared state.
*Accept when:* lowering the threshold in state (not in code) changes which branch runs,
and all four evaluators are observably concurrent in the event stream.

**M3 — Durability (day 3)**
Checkpointing to disk, then to Blob Storage. Graph serialization to JSON.
*Accept when:* `kill -9` during the fan-out, followed by `--resume`, completes the run
without re-executing already-finished nodes.

**M4 — Stretch, only if M1–M3 are done**
Containerize, deploy to Azure Container Apps, checkpoint store in Blob Storage.
*Accept when:* a run started by one replica is resumed to completion by a *different*
replica. This is the whole point of externalized checkpoint state — it makes the workers
stateless.

Cut M4 before cutting anything else.

---

## 6. Required experiment

The framework executes in **supersteps**: all nodes triggered in a given step run
concurrently, and the workflow does not advance until every one of them finishes
(a synchronization barrier).

Build a deliberately lopsided fan-out — one branch that is a chain of two or three fast
nodes, and one branch that is a single slow node — and observe from the event stream that
the fast chain cannot advance past the slow branch.

Then write a short `NOTES.md` answering:

1. Why does a fan-in node need different readiness logic than a conditionally-routed node?
2. What breaks if you resume a checkpoint against a graph whose structure has since changed, and how should the system detect that?
3. When would you *not* use a deterministic workflow, and reach for an autonomous orchestrator instead?

---

## 7. Non-goals

- Report quality, prompt tuning, or model selection benchmarking
- Auth, multi-tenancy, a web UI, or a database
- Real data of any kind, from any source
- Retry/backoff sophistication beyond whatever the framework gives for free

---

## 8. First actions for the assistant

1. Confirm the current Agent Framework Python API from official docs and samples; state any deviation from this brief before coding.
2. Scaffold the repo per §4 with `pyproject.toml` and a working `.env.example`.
3. Generate the synthetic `fixtures/svc-alpha/` bundle — make the artifacts plausibly messy, with one control that should clearly fail and one that should land in `NEEDS_REVIEW`.
4. Write `models.py` and `controls.py` in full before any node logic.
5. Stop and show me the graph construction code before wiring up model calls.
