# TODO — FinSight (learning project)

Every item goes through the loop in `CLAUDE.md`:
**walkthrough → decision (logged in DECISIONS.md) → small build → break it on purpose → measure → reflect in NOTES.md.**
Don't advance past a ✅ acceptance check until it has really been run.

## Week 1: one strong agent, tools, MCP, eval baseline
Book: Ch 1, 4.1–4.6, 4.11, 10.2, 12.2, 15.3
**Working mode (from Week 2 Memory onwards):** Claude writes the code and explains the important lines. The user reviews it and asks questions. Understanding is checked through occasional review questions along the way and the "Defend it" interview questions at the end of each week (`INTERVIEW.md`).

**How steps work (D3):** 📘 **Lesson** = a tiny sandbox script in `lessons/` to understand one idea. 🏗️ **Product** = right after, move what we learned into the real app in `src/finsight/`. Experiment-only steps have no product part. The user knows the book, so lessons are hands-on and point to the book section rather than re-teach the theory.

- [x] The agent loop and tools:
  - [x] Plain-language intro: an agent is a chatbot that can ask your code to run tools.
  - [x] **Step 1 — hello agent**
    - [x] 📘 Scaffold FinSight (D1), add MAF core + OpenAI connector (D2), run `lessons/w1_step1_hello_agent.py`.
    - [x] 🏗️ Move the client setup into `src/finsight/llm.py` (one place that builds the client for gpt-5.4 / gpt-5.4-nano) and add `.env.example`. The lesson script then uses it.
  - [x] **Step 2 — first tool**
    - [x] 📘 Add a `calculator` function tool in a lesson script. Ask a math question and watch the tool call happen.
    - [x] 🏗️ Move it to `src/finsight/tools/calculator.py` with a safe evaluator, plus the first offline test in `tests/` (set up `pytest`).
  - [x] **Step 3 — look inside** (📘 only): print the full message list after a run (user → function_call → function_result → answer), and see what is re-sent on each model call.
  - [x] **Step 4 — break it**
    - [x] 📘 Cap the tool calls (`max_function_calls`) and see the agent answer anyway without finishing its work.
    - [x] 🏗️ Set explicit loop limits in `llm.py` (no silent defaults) and decide how a hit limit gets flagged (D5: `finsight/limits.py`).
    - [x] 🏗️ Move models and loop limits into one settings file, `src/finsight/config.py` (D6).
- [x] Typed LLM responses with Pydantic:
  - [x] **Step 5 — Pydantic basics** (📘): a model class, validation, and what a `ValidationError` looks like. No LLM yet.
  - [x] **Step 6 — free text vs typed** (📘): ask the same question both ways. Free text needs fragile parsing, while `response_format=Model` gives you `response.value` as a typed object.
  - [x] **Step 7 — what the model actually sees** (📘): look at the JSON schema Pydantic produces, and see how `Field(description=...)` changes the answers.
  - [x] **Step 8 — when typing goes wrong**
    - [x] 📘 A wrong type, a missing field, or the model "filling in" a field it doesn't know (e.g. making up a citation), and how to defend against each (optional fields, `None`, validators).
    - [x] 🏗️ Write the product's `Answer` model in `src/finsight/models.py` using everything from Steps 5–8, with tests.
- [x] Scaffold check: `.gitignore` (`data/`), package layout. Verify the installed MAF version's API surface.
- [x] Data:
  - [x] Pick the companies (D8): 12 companies, 10-K questions only, numeric + written answers.
  - [x] Download those questions plus their 28 PDFs (`python -m finsight.dataset`).
  - [x] Build `dev`/`test` splits by company (D9): dev 42, test 24.
  - [x] Add a text answer field to `Answer` (D8), so written answers fit. Update the tests.
- [x] Single agent with structured output: `Answer{value, unit, citations[page], confidence, reasoning}`. This uses everything from Steps 5–8.
  - It reads filings through `search_filing_text` (D10), so that tool is built here, ahead of the tools item below.
  - [x] Command line: `uv run python -m finsight.agents.analyst <FILING_ID> "<question>"`.
- [x] Function tools: `calculator`, `render_page` (returns a page image), `search_filing_text` (keyword search).
- [x] Our own MCP server `edgar-mcp` (FastMCP):
  - [x] Tools `get_company_facts` and `list_filings`, a `filing://` resource, and a prompt.
  - [x] Consume it over stdio, then over streamable HTTP (`analyst --http`).
- [x] Connect one third-party MCP server and watch how tool discovery works (D13, `lessons/w1_step9_third_party_mcp.py`).
- [x] Eval harness v0 (D14, `python -m evals.run`): numeric match with tolerance, LLM judge, citations, tokens, $ and latency. **Baseline recorded: 86% on dev, $1.44.**
- [x] Decisions to discuss (D15):
  - Why one agent first.
  - Structured output vs free text.
  - Function tool vs MCP vs agent-as-tool.
  - MCP over stdio vs HTTP.
  - How to write tool descriptions.
  - Choice of eval metric.
- [x] ✅ The agent answers ≥10 dev questions end to end using MCP plus a local tool. The baseline is recorded in `evals/leaderboard.md`.
  - [x] 10-question check: 10/10 correct, but MCP was never called (the agent chose not to).
  - [x] Cross-check prompt variant (`analyst_crosscheck.md`): MCP used on 32/42, accuracy 88% vs 86% (noise), cost +46%. Not adopted (D16).
- [x] Reflect (NOTES.md): tool vs MCP tool vs agent-as-tool. Why build the eval before tuning the prompt?
- [x] Defend it (no notes): answer the Week 1 questions in `INTERVIEW.md` out loud or in `NOTES.md`; Claude points out gaps.

## Week 2: RAG, multimodal evidence, memory types
Book: 4.7–4.8, 4.12, 5.3, Ch 14
- [x] Ingestion: PDF → page text and images → two chunkers (fixed-size vs page/section-aware) → embeddings (1024-d) → Azure AI Search (hybrid + semantic ranker). *Confirm before creating the Search resource.*
  - [x] Walkthrough: chunkers, embeddings, hybrid search + reranker, the pipeline.
  - [x] Decisions: Search Free tier (D17), one chunker at a time (D18), fixed-size = 1024 tokens / 128 overlap (D19). Search resource `finsight-search-hma96` created.
  - [x] **Step 1 — embeddings** (📘 `lessons/w2_step1_embeddings.py`): embed a question and a few chunks, print similarity. Break it: an exact number (`598,194`) ranks the wrong page first, which is why we use hybrid search.
  - [x] 🏗️ Chunkers + ingestion into `src/finsight/rag/`, with offline tests. Upload one index; check its real size in Azure.
- [x] Retrieval eval: recall@k against the gold evidence page, for each chunker (`python -m evals.retrieval`, `evals/retrieval.md`). Page wins: recall@5 63% vs 43% (D21–D23).
  - [x] Decide how to score fixed-size chunks fairly: 91% of them span 2+ pages, so "any page hits" gives them a big head start.
- [x] Give the analyst a `search_filings` tool backed by the winning index (search mode settled in D25: vector). Decide whether it replaces or sits beside keyword search. Run a dev eval and compare to the 86% baseline. Result: 93% (vector, 2 runs) vs 86%, about a third cheaper (D24, D25).
- [x] Multimodal: send the page image (instead of extracted text) for table/chart pages. Compare accuracy on table questions both ways.
  - Lesson `w2_step2_page_image.py`, switch `PAGE_FORMAT`. Images 88% vs text 93% (numeric 92% vs 100%). Text stays the default (D26).
- [x] Memory:
  - [x] Thread/session (short-term). Lesson `w2_step3_session.py`: default history is stored service-side in Azure; switched all agents to `store=False` (D27).
  - [x] RAG (long-term). Already built: the filings index in Azure AI Search, pulled in on demand via `search_filings` (D17–D25).
  - [x] Memory-as-tool notes (D28). Lesson `w2_step4_notes.py`: with no outside signal the agent saves nothing. Told it was wrong (by a bad gold label), it invented a false excuse and saved it as a note.
  - [x] Episodic `ContextProvider` (D29). `memory/episodes.py`, lesson `w2_step5_episodes.py`; evals use `--memory` with a fresh empty store.
- [x] Break it: poison a memory note and watch a wrong answer come out. Then add a defense. Lesson `w2_step6_poison.py`: poison that discredits the filing won 3/3. Defence A + B (D30): 0/7.
- [x] Decisions to discuss (confirmed 2026-10-14; chunking D23, search D25, dimensions D18 (1024, not measured vs 512), image vs text D26, memory D28–D30):
  - Chunking strategy.
  - Vector vs keyword vs hybrid search, and what the reranker does.
  - Embedding dimensions.
  - Image vs text for tables.
  - Automatic vs on-demand memory.
  - Where memory is stored.
- [x] ✅ Dev accuracy beats the week-1 baseline. Recall@5 is reported for both chunkers. (93% vs 86% on dev, D25; recall@5 page 63% vs fixed 43%, `evals/retrieval.md`.)
- [x] Reflect: when does memory hurt?
- [x] Defend it (no notes): Claude asks 3–4 interview-style questions about this week's decisions and failures (added to `INTERVIEW.md`). Cover memory too: notes vs episodes, the bad-gold-label note (D28 result), and episodic injection (D29 result). Answer out loud or in `NOTES.md`; Claude points out gaps.

## Week 3: orchestrations, workflow, terminations, approvals
Book: Ch 2, 6, 7, 4.13, 11.3.5–11.3.6, 11.3.10
- [x] Workflow graph: Router (nano, conditional edges) → Research → Verifier → HITL → Report, with checkpointing.
  - [x] Walkthrough and sketch. Decisions: router labels `lookup` / `analysis` / `oos`, with stronger reasoning on `analysis` and a retry before human review (D31); Verifier design (D32).
  - [x] **Step 1 — agents in a workflow** (📘 `lessons/w3_step1_agents_in_workflow.py`): router → switch → agent or plain-code `oos`. Found: by default (`context_mode="full"`) the next agent receives the whole conversation, including the router's JSON.
  - [x] 🏗️ Router agent (nano, typed `Route`), plus an `oos` check set: real questions paired with the wrong filing.
    - `agents/router.py`, `prompts/router.md`, `python -m evals.router` (D33). Caught 40/42 wrong filings, blocked 0/42 good ones, $0.01. Both misses: Boeing/Corning named in the question, yet labelled `analysis`.
    - Fix (user's idea): prompt checks the company first. 42/42 caught in 2 runs, still 0 blocked, cost about +10%.
    - Stabilise lookup vs analysis (user's idea): a "copy it straight from one place?" test. Label flips between 2 runs: 4 → 2 (totals matched, 9/33, but two questions swapped). Still 42/42 and 0 blocked, cost about +7% more.
  - [x] 🏗️ Verifier agent (D32), with offline tests.
    - `agents/verifier.py`, `prompts/verifier.md`, `Verdict` in `models.py`, `tests/test_verifier.py` (5 offline tests; 82 pass). Live spot check on one Adobe question: right answer ✓, wrong math ✗, a missing cited page ✗. About $0.003–0.009 per check.
  - [x] 🏗️ Wire the graph: Router → Research → Verifier → retry once → human review → Report, with checkpointing.
    - `orchestration/workflow.py` + `messages.py` (D34: our own executors, typed messages). CLI: `python -m finsight.orchestration.workflow <FILING_ID> "<question>"`. Live: Adobe ratio verified on the first try (15 s); the same question vs Boeing → oos. 5 offline wiring tests (87 pass); removing the retry edge makes 2 of them fail. Surviving a real restart is the Approvals item below.
  - [x] Measure: workflow vs single agent on dev (accuracy, $, latency, per Router label). Both with the edgar MCP tool, because the 93% baseline had it.
    - [x] Run 1 (D35: a human hand-off is scored as-is): workflow + edgar 90% / 93% vs single agent 93% / 93%; $2.01 / $2.24 vs $0.94 / $0.97; p50 17–18 s vs 6 s. The Verifier approved all 3 wrong answers in each run: definition or judgement disagreements with gold, not unsupported claims. It also sent 1 correct answer to a human over rounding (5.2576% vs 5.3%). The one gain was `00678`: wrong in both single-agent runs, right in both workflow runs.
    - [x] Fix: a retry that breaks `Answer`'s rules crashed the question (`00591`). Now it keeps the first answer (test added).
    - [x] Fix: the Verifier accepts rounding differences (3/3 spot checks; still rejects bad math 3/3), then re-run. v2: 90% / 90%, $2.45 / $1.94, p50 14 s. 0 crashes. The one human hand-off was a truly wrong answer (`01290`). Still not better than the single agent.
    - [x] Variant: the workflow without edgar, vs with it (user's request), to measure the tool on its own. No edgar: 93% / 95%, $2.23 / $2.36, p50 14–16 s. With edgar: 90% / 90%. Edgar was called on only 1–2 questions per run, so the gap (1–2 questions) is noise: the tool makes no measurable difference. In no-edgar r2, both human hand-offs were *correct* answers.
- [x] Research-step variants:
  - [x] Handoff (D36: quick → deep).
    - [x] 📘 `lessons/w3_step2_handoff.py`: on 4 questions quick handed off exactly where the Router says `analysis`. `--break` (contradictory jobs, mesh): quick → deep → quick, then quick *wrote* "I'm handing off" without calling the tool. The run ended with no answer and no error (3/3).
    - [x] 🏗️ `orchestration/handoff.py`, `build_workflow(research="handoff")`, `evals.run --research handoff`. A run that ends without a valid Answer becomes found=false (test). Dev: 93% / 90%, $2.03 / $2.07, p50 16–17 s, vs the Router workflow at 90% / 90%, $2.45 / $1.94, 14 s: a tie. Quick kept every Router-`lookup` (17/17) but also kept 5–8 `analysis` questions per run; one of those (`00494`) was wrong both runs.
  - [x] Concurrent + aggregator. Lesson only (D37, user's call): 3 agents vote on the judgement questions. No product step or dev eval, because voting can't fix disagreements with gold.
    - Later (D38, user's call) it got a product step too: `orchestration/concurrent.py`, `--research concurrent`. Dev: 90% / 87% text, citation supported 90%, $3.62, p50 18 s / p95 82 s. First run 86% had 2 Azure 429 errors; those 2 rows were rerun one at a time (both correct) and the result patched. Ties Router/Handoff on accuracy, costliest.
    - `lessons/w3_step3_concurrent.py`: 3 questions × 3 agents, every vote unanimous (3–0), so the vote never changed anything. 2 of 3 unanimous answers disagreed with gold. ~$0.30; the wait = the slowest agent (6–12 s), the cost = 3×.
  - [x] Group chat maker-checker.
    - [x] 📘 `lessons/w3_step4_maker_checker.py`: structured `{approved, issues}` checker works in a group chat (needs `output_from="all"` to see turns). Control `00678`: approved first look (3 turns). Wrong-answer `01290`: checker rejected 3 drafts in a row, never converged, `max_rounds=6` ended it. `--break` (checker may never approve): the same 7 turns, ended only by `max_rounds`.
    - [x] 🏗️ `orchestration/maker_checker.py`, `evals.run --research makerchecker` (D38). Dev: 88% / 83% text, $3.14, p50 19 s / p95 45 s, 0 errors. No better than the single agent (93%, $0.95) or Handoff (~$2.05).
  - [x] Magentic (multi-company compare). Lesson only: dev has no multi-company question to score (8 companies, 0 comparisons), so no product step or eval.
    - `lessons/w3_step5_magentic.py`: Boeing vs Corning FY2022 tax rate, hand-written task, no gold. Manager sent boeing_analyst, then corning_analyst, then asked boeing_analyst to write the comparison (−0.6% vs 22.9%, both cited to p. 77). 39 s, 3 specialist turns, under $0.50.
- [x] Terminations: max turns, token/$ budget, keyword, tool-call cap, timeout, composite, and mid-run cancellation.
  - [x] 📘 `lessons/w3_step6_limit_scope.py`: the client's tool-call cap (3) is per agent turn, not per chat: 8 pings over 4 turns. Only `max_rounds` covers the whole conversation today.
  - [x] 🏗️ Whole-run budget (D39, option A): `middleware/budget.py` (`RunBudget`: $, tool calls, wall-clock; one object shared by all agents via `middleware=budget.middleware()`), 5 offline tests.
    - `lessons/w3_step7_budget.py`: same ping chat as step 6 with a shared budget of 5 calls: exactly 5 pings, then `BudgetExceeded` reached our `try/except` cleanly through the group chat. $0.0002.
    - Not yet wired into the workflow graph or `evals.run` (a later step: it needs a per-question budget).
  - [x] 📘 Mid-run cancellation: `lessons/w3_step8_cancel.py`: `task.cancel()` after ping 2 (inside a 1 s tool) ended the group chat at once with `CancelledError`; 15 s later still 2 pings, so no leaked tasks. Our tools are read-only; a tool with side effects needs a compensating action or idempotency (user's point, saga pattern).
  - [x] 📘 Composite: `lessons/w3_step9_composite.py`: one wrapper reports which of 4 exits fired (approved / max_rounds / budget / cancelled); all 4 correct on the nano model. Approval wins a tie with the budget (user's call). The approved-vs-max_rounds split reads the orchestrator's closing text, so it is fragile.
- [x] Break it: remove a termination condition and watch the loop run away.
  - 📘 `lessons/w3_step10_runaway.py`: step 9's maker + stubborn checker with no `max_rounds` and no `termination_condition` (both default to `None` in MAF, so no error or warning). It ran until our outside fail-safe (`asyncio.wait_for`, 20 s, option A) stopped it: 13 turns, $0.0007 on nano. The maker said the same sentence again and again and the checker repeated its objection, so the loop never made progress. Straight-line extrapolation: ~2,300 turns, ~$0.13/hour on nano. The real cost is higher because the prompt grows every turn.
- [ ] Approvals:
  - [x] A tool with `approval_mode` set.
    - 📘 `lessons/w3_step11_tool_approval.py` (D40: `save_report` writes a file, a side effect). `run()` returned early with the request instead of running the tool; the answer went back with a second `run()` on the same session. Yes → the file was written. No → no file, but the agent never said a human refused: in one run it claimed "I can't access the filesystem", in the user's run its final words were the same as when approved.
    - [x] Fix (option B): code records each approval decision next to the answer, so a refusal shows whatever the model writes. Rerun: the model again said "I can't run the save operation here", and the code record said `save_report: DECLINED by reviewer`.
  - [ ] ⏩ **NEXT** — Workflow `request_info` for low-confidence claims, surviving a restart.
- [ ] Decisions to discuss:
  - Workflow vs autonomous orchestration.
  - Pattern selection criteria.
  - What deserves approval.
  - Fail-safe termination.
  - Shared state vs messages.
- [ ] ✅ Comparison table of patterns × {accuracy, tokens, $, latency, turns}. A demo of an approval surviving a restart.
- [ ] Reflect: which pattern won and why? When is one agent enough?
- [ ] Defend it (no notes): Claude asks 3–4 interview-style questions about this week's decisions and failures (added to `INTERVIEW.md`). Answer out loud or in `NOTES.md`; Claude points out gaps.

## Week 4: observability, hooks, cost, compaction, debugging
Book: 3.4, 4.9–4.10, 4.12, 9.2.3, 11.3
- [ ] OTel: local dashboard (Aspire/Jaeger), then Application Insights. *Confirm before creating App Insights.* Make a deliberate choice about content capture.
- [ ] Middleware:
  - [ ] Logging.
  - [ ] Cost meter (including cached tokens).
  - [ ] Tool allowlist / argument validation.
  - [ ] PII redaction.
  - [ ] Loop guard.
- [ ] Cost analysis: $/question per architecture; nano vs gpt-5.4 per role; prompt-cache hit rate.
- [ ] Compaction: truncation, observation masking, rolling summary, sub-agent summary. Measure accuracy vs tokens for each.
- [ ] Debugging: diagnose 5 failed dev questions using DevUI and traces, and label each with the 11.3 failure taxonomy.
- [ ] Decisions to discuss:
  - What to trace and what never to log.
  - Middleware vs logic inside the agent.
  - Which model for which role.
  - What each compaction strategy saves vs what it loses.
  - Root cause vs symptom.
- [ ] ✅ One full trace with per-agent cost, a compaction table, and a failure-analysis table.
- [ ] Defend it (no notes): Claude asks 3–4 interview-style questions about this week's decisions and failures (added to `INTERVIEW.md`). Answer out loud or in `NOTES.md`; Claude points out gaps.

## Week 5: evaluation in depth, optimization, testing, Responsible AI
Book: Ch 10, 11, 13, 12.3
- [ ] LLM-as-judge, calibrated against 20 user-labelled items (report agreement).
- [ ] Citation correctness, trajectory metrics, `azure-ai-evaluation` evaluators.
- [ ] Ablation leaderboard: change one thing at a time (prompts, tool descriptions, k/reranker, model per role, pattern).
- [ ] Tests:
  - [ ] Unit tests and MCP contract tests.
  - [ ] Stub-LLM wiring tests.
  - [ ] Replay tests.
  - [ ] `make eval` regression gate.
- [ ] Responsible AI:
  - [ ] Plant a prompt injection in a filing chunk and show the agent obeying it.
  - [ ] Defend with middleware or Prompt Shields, and show the defense working.
  - [ ] Groundedness gating.
  - [ ] A "not investment advice" output policy.
  - [ ] Walk through the 13.5 checklist.
- [ ] Optional: expose the Verifier via A2A.
- [ ] Optional (MLE / Applied Science bridge): fine-tune the embedding model or a reranker and measure recall@k against the off-the-shelf model.
  - Train only on real (question, evidence page) pairs from FinanceBench questions outside our 12 companies. No synthetic data, and never `test`.
  - Report the gain across several runs, with the noise.
- [ ] Decisions to discuss:
  - Trusting the judge.
  - Overfitting to `dev`.
  - Deterministic tests vs evals.
  - Defense-in-depth.
  - When to stop optimizing.
- [ ] ✅ Run the held-out **test** set once (the user OKs it). Final report: accuracy, $/question, p50/p95 latency, best configuration.
- [ ] Defend it (no notes): Claude asks 3–4 interview-style questions about this week's decisions and failures (added to `INTERVIEW.md`). Answer out loud or in `NOTES.md`; Claude points out gaps.

## Project review (end of week 5)
- [ ] Explain the whole system on a whiteboard from memory: data → index → search → agents → verifier → eval. No notes.
- [ ] Mock interview: answer the questions in `INTERVIEW.md` without notes. Claude grades the answers against `DECISIONS.md`.
  - Claude adds new questions to `INTERVIEW.md` at the end of each week.
- [ ] Write a one-page summary in your own words: what you built, 3 decisions you'd defend, 2 you'd change, and the numbers that back them.

## Final step (optional): polished public showcase on Azure
Book: Ch 3, Ch 8, 9.2.8, 12.4
- [ ] Web app built around the Ch 3 UX principles:
  - [ ] Capability discovery.
  - [ ] Live agent/tool timeline.
  - [ ] Cited page images.
  - [ ] Cancel/redirect.
  - [ ] $ per question.
  - [ ] Approval dialogs.
  - [ ] "How it works" page.
  - [ ] Eval dashboard.
- [ ] FastAPI with SSE, and a React (Vite) frontend.
- [ ] Two Container Apps in `atlas-env`: the app (public) and `edgar-mcp` (internal only).
- [ ] Managed identity + RBAC (no keys in the cloud), Key Vault, App Insights workbook.
- [ ] Checkpoints in Cosmos DB, so a pending approval survives a restart or scale-out.
- [ ] Public-demo guardrails: auth or demo key, rate limits, per-request $ budget, scale to zero.
- [ ] Bicep/azd for repeatable deploy and teardown. *Confirm before deploying.*
- [ ] Decisions to discuss:
  - Streamlit vs React.
  - SSE vs WebSockets.
  - Container Apps vs App Service vs Foundry Agent Service.
  - Public access model.
  - Abuse and cost protection.
  - Stateless replicas.
- [ ] ✅ A public URL where a viewer asks a question, watches the agents work, approves, and gets a cited answer. The request's trace is in App Insights. Teardown works.
