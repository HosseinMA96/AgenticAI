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

---

## D4 — Calculator: our own small `ast` evaluator (2026-10-06)

**Options:**
1. Python built-ins. `eval` is unsafe (runs any code). `ast.literal_eval` is safe but rejects arithmetic, even `2+3` (tested).
2. A ready-made evaluator: the `simpleeval` library, or the model's hosted code interpreter.
3. Our own ~25-line `ast` evaluator with an explicit allow-list.

**Choice:** 3.

**Why:**
- Tool arguments come from the model, which can be steered (for example by an injection in a filing). Trust the tool's code, never its inputs.
- An allow-list (numbers, `+ - * / **`, brackets, unary minus) permits exactly what we need and nothing more.
- No new dependency, and it's easy to test offline.
- The lesson's two-number tool isn't enough: FinanceBench needs CAGR (`**`) and multi-term sums, which would take many model round trips.

**Cost:** we own the edge cases (huge exponents, division by zero).

**Takeaway for Bcdr work:** give tools allow-lists, not deny-lists.

---

## D5 — Tool-loop limits: explicit caps, and a hit cap is flagged on the result (2026-10-08)

**Context:** when MAF hits `max_function_calls`, it sets `tool_choice="none"`, forcing a text answer, and writes only a `logger.info` line (`agent_framework/_tools.py`). Nothing on the response says so, and the defaults are `max_iterations=40` with no call or time cap.

**Options:**
- **A.** Count and flag: after `run()`, count the `function_call`s in `response.messages`. Reaching the cap returns `limit_hit=True` alongside the answer.
- **B.** Fail loud: a function middleware raises at the cap, so no answer comes back.
- **C.** Log only: raise MAF's log line to a warning.

**Choice:** A.

**Why:**
- A silent early stop is more dangerous than a runaway loop. A runaway is visible in time and cost. A truncated answer looks just like a good one.
- It's free and small, and it reuses the message inspection from Step 3.
- The flag is a field, so evals can count it and Week 3 (Verifier, HITL) can route on it.
- B throws away the whole answer and needs middleware, which is a Week 4 topic. C still leaves the code unable to tell.

**Cost:** "reached the cap" ≠ "needed more calls", so expect some false alarms.

**Takeaway for Bcdr work:** a comment built from incomplete evidence goes to human review instead of being thrown away.

---

## D6 — Settings: one plain-Python `config.py` (2026-10-08)

**Options:**
- **A.** `src/finsight/config.py` with plain constants (models, loop limits).
- **B.** A `pydantic-settings` class, with defaults that env vars can override.
- **C.** A `config.toml` file plus a loader.

**Choice:** A.

**Why:**
- It's the simplest option: no new dependency, and every change is a reviewable diff tied to an eval run.
- B adds a dependency and uses Pydantic before Step 5 covers it. C needs parsing and has no type checks.
- Code only imports names from `finsight.config`, so switching to B later (for the Week 5 ablation `--config` runs or Container Apps env vars) won't touch the callers.

**Rule:** secrets never go in `config.py`. They stay in the root `.env`.

## D7 — `Answer.confidence`: three named levels (2026-10-09)

**Options:**
- **A.** A `float` from 0 to 1.
- **B.** `Literal["high", "medium", "low"]`, with each level defined in the field description.
- **C.** No self-reported confidence. The Week 3 Verifier decides instead.

**Choice:** B, and the Week 3 Verifier still checks every claim.

**Why:**
- LLM self-confidence is poorly calibrated. A float looks precise (0.87 vs 0.91), but the difference means little, and values bunch up near 0.9.
- Three defined levels are easy to act on and to test. In Week 3, `low` will route a claim to human approval (`request_info`).
- It matches the rating scales used in BCDR assessments.
- Self-reported confidence is only a hint. The Verifier agent (Week 3, already in `TODO.md`) is what actually checks claims against the evidence, and it can override this field.
