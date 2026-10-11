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

## D8 — Dataset: 12 companies, number and sentence answers (2026-10-09)

**Finding:** of FinanceBench's 112 open-source 10-K questions, only 51 have a plain numeric answer. The other 61 are written answers ("Yes, one customer accounted for 16% of revenue"). Every question has a gold evidence page.

**Options:**
- **A.** Numbers only: all 51 numeric 10-K questions, spread over 24 companies (at most 4 each), about 40 PDFs.
- **B.** The 12 companies with the most 10-K questions, all question types: 66 questions (20 numeric, 46 written), 28 PDFs.

**Choice:** B. The companies are AMD, Boeing, American Express, PepsiCo, 3M, Adobe, Amcor, Best Buy, Verizon, Corning, CVS Health and General Mills.

**Why:**
- It's closer to the BCDR work, whose comments are written judgments backed by evidence, not numbers.
- Written questions are where agents actually struggle, so they make a better test.
- It matches the plan (8–12 companies, 60–80 questions) and needs fewer PDFs.

**Cost:**
- `Answer` needs a text answer field next to `value`.
- Week 1 accuracy (numeric match) covers only the numeric questions. Citation hit rate covers all 66.
- Written answers are scored by an LLM judge, which was planned for Week 5 and may need a simple version earlier.

## D9 — Dev/test split: by company (2026-10-09)

**Options:**
- **A.** By company: each company's questions go wholly into dev or wholly into test.
- **B.** Random by question: the same companies appear in both splits.

**Choice:** A. Test = 3M, AMD, Best Buy, PepsiCo (24 questions, 8 numeric). Dev = the other 8 companies (42 questions, 12 numeric).

**Why:**
- With B, anything we tune on a dev filing (chunking, memory notes in Week 2, prompts) also helps the test questions on that same filing, so the test score would look better than it really is.
- With A, the test filings are never seen while tuning, so the test score is an honest estimate on unseen filings.
- The test companies were picked for balance only (question count, numeric count, and each test sector also appearing in dev), not by looking at question difficulty.

**Also:** FinanceBench page numbers are 0-based. The splits store them 1-based (`evidence_pages`) so they match the PDF and our citations.

## D10 — How the first agent reads a 10-K: a search tool (2026-10-09)

**Options:**
- **A.** Put the whole filing text in the prompt (about 90k–200k tokens per question). No tools.
- **B.** Give the agent a keyword-search tool over the filing's pages, and let it decide what to look up.

**Choice:** B.

**Why:**
- It's real agent behaviour: the model plans what to look up and cites what it found.
- It's far cheaper and faster per question than resending a whole 10-K every time.
- It carries over to BCDR, where the evidence set is too large to paste in.
- It pulls the `search_filing_text` tool forward from the next TODO item, so the two items are built together.
- A could still serve later as a "no retrieval" comparison point in the eval.

## D11 — PDF library: PyMuPDF (2026-10-09)

**Options:**
- **A.** PyMuPDF: fast, good text extraction from tables, and it also renders pages as images.
- **B.** pypdf: pure Python with a permissive license, but weaker on tables and unable to render images.

**Choice:** A.

**Why:**
- One library covers both text search now and `render_page` / multimodal evidence in Week 2.
- Its license is AGPL. That's fine here because the repo is public. Revisit this if the BCDR work reuses the code in a closed product.

## D12 — MCP library: the official `mcp` SDK (2026-10-09)

**Options:**
- **A.** The official `mcp` SDK, which includes `FastMCP` for writing servers.
- **B.** The standalone `fastmcp` package: newer, with extras such as auth, proxies and server composition.

**Choice:** A.

**Why:**
- MAF's MCP client tools (`MCPStdioTool`, `MCPStreamableHTTPTool`) need `mcp` anyway, so one package covers both the server and the client side.
- B's extras aren't needed for a two-tool server. We can switch if the final step needs auth features.

## D13 — Third-party MCP server: the official fetch server (2026-10-10)

**Options:**
- **A.** `mcp-server-fetch`: the official reference server that reads web pages. Runs locally over stdio.
- **B.** Microsoft Learn docs MCP: hosted by Microsoft over HTTP, nothing to install.

**Choice:** A, pinned to `mcp-server-fetch==2026.8.18`.

**Why:**
- It's relevant to FinSight: the agent could read SEC pages or news.
- It sets up Week 5: fetched web pages are an obvious path for prompt injection.
- The version is pinned because we run someone else's code, so we decide when it changes.

**Seen in the lesson (`lessons/w1_step9_third_party_mcp.py`):**
- Its tool description contains instructions written by the server's author ("this tool now grants you internet access…"). A third-party server writes part of our agent's prompt.
- On the first run it executed `npm install` and printed to stdout, which corrupted the stdio channel; the client logged parse errors. A third-party server can also run more code than you expected.

## D14 — Eval v0 scoring: number match, LLM judge, two-step citation check (2026-10-10)

**Answer correctness:**
- **Options:** (A) a simple LLM judge for written answers now; (B) score only the 12 numeric dev questions until Week 5.
- **Choice:** A. Numeric questions are matched in code (within 1%, allowing for unit scale such as millions vs billions or ratio vs percent). Written answers go to a `gpt-5.4` judge that compares the agent's answer with the gold answer.
- **Why:** B would rest the baseline on 12 questions. The judge costs cents per run. Week 5 checks the judge against the user's own labels.

**Citations** (the user's idea):
- **Options:** (A) strict: a hit only if a cited page is a gold page; (B) lenient: a judge reads the cited pages every time.
- **Choice:** both, in order. First the free strict check. Only if it misses does a cheap `gpt-5.4-nano` judge read the cited pages and say whether they support the answer.
- **Why:** the strict check alone undercounts (Boeing: page 85 also states the number, but the gold page is 52). A judge on every question costs more for no gain when the strict check already passed.
- **Reported:** `citation_hit` (strict) and `citation_supported` (strict or judge), so both stay visible.
