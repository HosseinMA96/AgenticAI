# BcdrSequential — Compliance Evidence Workflow

Learning project (see `compliance-evidence-workflow-brief.md` and `TODO.md`). Not a
product — the deliverable is code that exercises six agentic-workflow concepts, not
report quality. Scope: ≤ 1 week.

## Golden rule

At every step (design, implementation, decisions), stop and discuss the options and
tradeoffs before committing to one. The user is new to agentic frameworks and BCDR
compliance workflows and is using this project to learn both — don't skip straight to
an implementation without first walking through the alternatives and the "why."

## What this is

A graph-based (deterministic orchestration) workflow that ingests synthetic BCDR
artifacts for a fake service and produces a markdown evidence packet with per-control
findings. All inputs are synthetic and live in `fixtures/` — never connect to a real
system, API, or tenant.

The six concepts that must appear in the final code:
1. Type-safe steps (Pydantic-typed node inputs/outputs, validated before execution)
2. Conditional edges (routing by step output + shared state)
3. Fan-out / fan-in (parallel branches converging on a barrier node)
4. Streaming observability (per-step events, consumable in real time)
5. Serialization (graph dumps to JSON and reconstructs)
6. Checkpoint and resume (a killed run resumes from persisted state)

## Stack

- Python, Microsoft Agent Framework (`agent-framework`)
- Azure OpenAI via Microsoft Foundry, using `agent_framework.openai.OpenAIChatClient`
  (its `azure_endpoint=`/`api_key=` params — not `agent_framework.foundry`, which is
  for a different Azure AI Foundry *Agent Service* project shape). **Corrected in
  Phase 6:** originally called for `az login`/`DefaultAzureCredential` here, but the
  actual shared `.env` already has a static `AZURE_OPENAI_API_KEY`, and every sibling
  `Dummy/Pre6/dummy*.py` script authenticates with it directly — matched that
  established convention instead of fighting it. See `src/llm.py`.
- Shared root `.env` per the parent `Stack of Agents/CLAUDE.md` conventions — this
  experiment loads `../.env` via relative path; do not duplicate credentials here. Keys
  actually used: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` (see `.env.example`).
- OpenTelemetry → Application Insights for observability; framework's DevUI for
  visualizing/debugging the graph

**API caution:** the Agent Framework is recent and its API has changed across
releases. Verify current method signatures against official docs/samples before
writing code — do not rely on recalled signatures.

## Repo layout

See `compliance-evidence-workflow-brief.md` §4 for the target layout
(`src/models.py`, `src/controls.py`, `src/nodes/`, `src/graph.py`, `src/run.py`,
`fixtures/`, `checkpoints/` [gitignored], `tests/`).

## Working conventions

- Never commit `.env` or `checkpoints/`.
- Follow `TODO.md` milestone order (M1 sequential spine → M2 parallel/conditional →
  M3 durability → M4 stretch, cut first if time runs short). Each milestone has an
  acceptance test — don't advance until it passes.
- Non-goals: report/prompt quality, auth, multi-tenancy, web UI, database, real data,
  retry sophistication beyond what the framework gives for free.
