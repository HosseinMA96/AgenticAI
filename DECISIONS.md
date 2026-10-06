# Decisions log

One entry per real choice: the options, what we chose, and **why**.

---

## D1 — Python environment: separate `uv` project env (2026-10-05)

**Options:**
1. Reuse the existing `agents` conda env (Python 3.13, contains `picoagents`).
2. A separate `uv` env for FinSight (Python 3.12, lock file).

**Choice:** 2, a separate `uv` env.

**Why:**
- Agent Framework needs `openai>=2.25`, but the `agents` env has `openai 1.107`. Installing it there would upgrade `openai` and could break `picoagents` and the book experiments.
- Disk cost is nearly the same. `uv` keeps each package version once in `~/.cache/uv` and *hard-links* it into each project's `.venv`. The same version used in two projects is stored once on disk (verified: a BcdrSequential `.venv` file and the cache file share an inode).
- `uv.lock` pins exact versions, so the setup is reproducible. That matters for the Azure deployment later.
- It fits the root rule "keep experiments isolated".

**Takeaway for Bcdr work:** one env per project and a lock file. Share disk through the package manager's cache, not by sharing an env.

---

## D2 — Agent Framework packages: core + OpenAI connector only (2026-10-05)

**Options:**
1. The `agent-framework` umbrella package, which pulls in all ~30 integrations.
2. Only `agent-framework-core` + `agent-framework-openai`, adding more as each week needs them.

**Choice:** 2.

**Why:**
- `pyproject.toml` lists exactly what we depend on, and each new dependency comes with a lesson (orchestrations in week 3, azure-ai-search in week 2, devui in week 4).
- No unused integrations.

**Installed:** core 1.20.0 and openai connector 1.15.0. These are newer than BcdrSequential's 1.18, so APIs were re-checked against the installed code.

**Related setup facts learned in Step 1:**
- `OpenAIChatClient` uses the **Responses API**. On Azure it calls the versionless `/openai/v1/` endpoint, so we **don't pass `api_version`**. The shared `.env`'s `2024-10-21` caused `400 API version not supported`.
- The shared `.env`'s `AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini` doesn't exist on `atlas-foundry-hma96`. FinSight names its deployment explicitly (`gpt-5.4`). The shared `.env` is left untouched because other experiments use it.

---

## D3 — Lessons vs product: learn small, then add it to the product right away (2026-10-05)

**Options:**
- **A.** All lessons first, then build the product.
- **B.** Each concept: 📘 a lesson script in `lessons/`, then 🏗️ move it into `src/finsight/` straight away.
- **C.** Product only, no lessons.

**Choice:** B.

**Why:**
- The lesson isolates one idea, so it's easy to understand.
- The product step shows how that idea fits a real system, which is the skill needed for the Bcdr work.
- Nothing learned is thrown away, and the product never arrives as a big unexplained drop.
- Experiment-only steps (inspect, break it) stay as lessons.
- The user has read the book, so lessons are hands-on and point to the book section instead of re-teaching theory.
