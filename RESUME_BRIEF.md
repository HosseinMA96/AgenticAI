# Resume Brief: Agentic AI Experience

**Who reads this:** an AI assistant writing or updating my resume.
**What it covers:** the agentic-AI skills and results from (a) my real BCDR agent work at Microsoft and (b) FinSight, a multi-agent project I built on the same stack to learn it in depth.
**Written as of:** 2026-10-28, describing the project as it will be when finished (end of week 5 plus the Azure deployment).

## Rules for the resume writer

1. **Keep the two sources apart.**
   - Under the **Microsoft** role, use only the BCDR work in section A and the skills from section C that I apply there.
   - **FinSight** (SEC filings, FinanceBench, all its numbers) goes in a **Projects** section. Never describe it as a Microsoft product, team project or deliverable.
   - Reason: the resume may be checked (background checks, immigration filings), and a false employer claim is worse than a project line.
2. **Numbers marked `[TBD]` are not measured yet.** Leave them out, or ask me for the final value. Never invent a number.
3. Prefer measured results over adjectives: accuracy, $/question, latency, number of questions.
4. Tone: hands-on engineer who builds, measures and explains tradeoffs. Not "leveraged synergies".

## A. Microsoft: BCDR Advisory Agent (real work)

**Context:** BCDR (business continuity / disaster recovery) assessments have several steps. Service owners submit evidence; approvers review it. Nobody got fast feedback before review.

What I did:
- Designed and wrote the requirements and preliminary design for an **advisory AI agent** that gives a first pass on each assessment step:
  - tells submitters what evidence is missing or weak and how to fix it,
  - tells approvers what already looks good and what to check by hand.
- Built on **C# / .NET with Microsoft Agent Framework (MAF)**. Tools wrap existing data connectors (SQL reads, blob downloads) with read-only access.
- Responsible-AI design: the agent is advisory only, a human always decides, and it cannot edit or delete evidence.
- Worked with the platform architect to define ownership boundaries:
  - the platform owns MAF, A2A, orchestration, observability and evaluation,
  - business developers own MCP servers and tools,
  - the business owns the prompts.
- Covered observability (Application Insights), an evaluation plan, and a step-pack contract in the design docs.
- Delivered V1 in the week of 2026-10-19. `[TBD: adoption, number of assessments or steps covered, time saved]`

## B. Project: FinSight, a multi-agent SEC 10-K analyst (personal project)

**One line:** Multi-agent system that answers questions about real company 10-K filings with page-cited, verified answers. Built in Python on Microsoft Agent Framework and Azure AI Foundry, and evaluated against the FinanceBench benchmark.

**Stack:** Python 3.12, uv, Microsoft Agent Framework, Azure AI Foundry (gpt-5.4, gpt-5.4-nano, text-embedding-3-large), Azure AI Search, MCP (FastMCP), Pydantic, pytest, OpenTelemetry, Application Insights, FastAPI + SSE, React (Vite), Azure Container Apps, Cosmos DB, Key Vault, Bicep/azd.

### Agents and tools
- Built a tool-using analyst agent with **typed structured output**. Each answer is a Pydantic model: value, unit, page citations, confidence and reasoning.
- Function tools: a safe calculator, page-image renderer, keyword search and semantic search.
- Wrote my own **MCP server** over the SEC EDGAR APIs, with tools, a resource and a prompt. It serves over stdio and streamable HTTP, and I added a third-party MCP server to study tool discovery.

### Retrieval (RAG) and multimodal
- Ingestion pipeline: PDF → page text and images → two chunkers → 1024-d embeddings → Azure AI Search.
- Built a retrieval eval (recall@k against the gold evidence page). The page-aware chunker beat fixed-size chunking: **recall@5 of 63% vs 43%**.
- RAG lifted dev accuracy from an **86% baseline to 93%** and cut cost per run by about a third ($1.44 → $0.94 for 42 questions).
- Measured page images vs extracted text on table questions (88% vs 93%) and kept text as the default because of that data.

### Memory
- Session memory, long-term RAG memory, a memory-as-tool notes store and an episodic context provider.
- Ran a **memory-poisoning attack**: a poisoned note won 3 of 3 runs. Designed defenses that brought it to 0 of 7.

### Orchestration and human-in-the-loop
- Workflow graph: Router (cheap nano model, conditional edges) → Research → Verifier → retry → human review → Report, with **checkpointing**.
- The router rejects out-of-scope questions (wrong company or filing): caught **42 of 42**, blocked **0 of 42** valid questions, for about $0.01.
- Built a **Verifier agent** that checks each claim against the cited evidence.
- Implemented and compared five research patterns on the same eval: single agent, sequential workflow, handoff, concurrent voting and group-chat maker-checker, plus a Magentic-style manager for multi-company comparisons.
  - Result: the single agent matched or beat the multi-agent patterns on accuracy (93%) at **2–4× lower cost** (about $0.95 vs $2.0–3.6 per 42 questions) and ~3× lower p50 latency. This is evidence for "use one agent until data says otherwise".
- Termination and safety: a shared whole-run budget (dollars, tool calls, wall clock) across agents, mid-run cancellation, and composite exit conditions. I also reproduced a runaway loop when terminations were removed.
- Human approvals: a tool approval gate for side-effecting tools, plus workflow pauses for low-confidence or unverified answers that **survive a process restart**. Added an idempotency guard so one request can't be approved twice.

### Observability, cost and debugging (weeks 4–5)
- OpenTelemetry tracing to a local dashboard and Application Insights, with a deliberate policy on content capture so no secrets or PII reach traces.
- Middleware: logging, a cost meter that counts cached tokens, a tool allowlist with argument validation, PII redaction and a loop guard.
- Cost analysis per architecture and per role (nano vs gpt-5.4), plus prompt-cache hit rate. `[TBD: final numbers]`
- Context compaction (truncation, observation masking, rolling summary, sub-agent summary), measured as accuracy vs tokens. `[TBD: table]`
- Root-caused failed questions from traces and labelled each against a failure taxonomy.

### Evaluation and testing
- Eval harness from day one: numeric match within tolerance, an LLM judge, citation hit rate and support, tokens (input, cached, output), $ cost, p50/p95 latency and tool calls. Results are logged to a leaderboard with **20+ configurations**.
- Strict dev/test split by company. Tuning happened only on dev; the held-out test set ran once at the end. `[TBD: final test accuracy, $/question, p50/p95]`
- LLM-as-judge calibrated against human labels. `[TBD: agreement %]`
- Ablation leaderboard changing one variable at a time (prompts, tool descriptions, retrieval k/reranker, model per role, pattern).
- Offline test suite (100+ tests): unit tests, MCP contract tests, stub-LLM wiring tests, replay tests, and an eval regression gate.

### Responsible AI and security
- Planted a **prompt injection** inside a filing and showed the agent obeying it, then defended with middleware / Azure Prompt Shields. `[TBD: before/after result]`
- Groundedness gating, a "not investment advice" output policy, and a Responsible-AI checklist review.

### Deployment (final step)
- Public demo: FastAPI + SSE backend and React frontend with a live agent and tool timeline, cited page images, approval dialogs, $ per question and an eval dashboard.
- Two Azure Container Apps (public app, internal MCP server), managed identity + RBAC with no keys in the cloud, Key Vault, Cosmos DB checkpoints so approvals survive scale-out, rate limits, per-request $ budget, scale to zero, and Bicep/azd for deploy and teardown. `[TBD: public URL]`

## C. Skills (safe to list under Microsoft, because I use them in the BCDR work)

- Microsoft Agent Framework (C#/.NET and Python): agents, function tools, structured output, workflows, checkpointing, human-in-the-loop.
- Agent architecture: when to use one agent vs a workflow vs autonomous multi-agent patterns, and evidence-grounded verification.
- MCP tool design; tool-boundary and ownership design across platform and business teams.
- LLM evaluation design: metrics, held-out splits, LLM judges, cost and latency tracking.
- Observability for agents (Application Insights, OpenTelemetry).
- Responsible AI: human-in-the-loop, read-only tool access, prompt-injection and memory-poisoning defenses.
- Azure: AI Foundry, AI Search, Container Apps, Cosmos DB, Key Vault, managed identity/RBAC.

## Suggested resume bullets (edit, don't copy blindly)

**Microsoft (BCDR):**
- Designed and delivered an advisory AI agent on Microsoft Agent Framework (.NET) that reviews BCDR assessment evidence and gives submitters and approvers a cited first pass, with a human always making the final decision.
- Defined the agent platform's ownership model (platform: orchestration, observability, eval; business: MCP tools and prompts) with the platform architect.

**Projects (FinSight):**
- Built a multi-agent 10-K analyst (Microsoft Agent Framework, Azure AI Foundry, Azure AI Search, MCP) that answers FinanceBench questions with page-cited, verifier-checked answers. Raised dev accuracy from 86% to 93% with RAG while cutting cost by about a third.
- Benchmarked five orchestration patterns on the same eval. Showed a single agent matched multi-agent accuracy at 2–4× lower cost, and documented when extra agents are worth it.
- Reproduced and defended against memory poisoning (3/3 → 0/7 attack success) and prompt injection. Added restart-safe human approvals and whole-run cost/tool budgets.
- Deployed a public demo on Azure Container Apps with managed identity, streaming agent timeline, and per-request cost limits.
