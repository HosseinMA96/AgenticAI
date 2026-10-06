# FinSight — Multi-Agent SEC Filings Analyst (learning project)

A 4–5 week **learning project**, plus an optional final week deploying it to Azure as a public showcase. Users ask questions about real company 10-K filings. Agents:
- retrieve evidence (text, plus table/chart pages as images),
- calculate,
- write claims with page citations.

A verifier agent then checks each claim against the evidence. This mirrors the user's upcoming work project: a sequential, multimodal agent workflow that comments on BCDR assessments based on evidence.

The week-by-week checklist is in `TODO.md`. The full rationale is in the approved plan, summarized below.

## The golden rule: learning comes first

The **only** goal is that the user comes away understanding the *why* and the *how* of agentic AI. Working code is a side effect, not the deliverable. This is not a race to finish. When time is short, cut scope, never the explanation.

The user has read Victor Dibia's *Designing Multi-Agent Systems* (2025; PDF in this folder) but hasn't built a real agent project yet. Their previous project, `../BcdrSequential`, covered deterministic MAF workflows: typed executors, fan-out/fan-in, conditional edges, streaming, checkpoint/resume and serialization. Build on that knowledge and don't re-teach it.

**Pace and consistency (the user asked for this explicitly):**
- Be patient and consistent. One small idea per message, in plain words.
- Run a tiny example first, then explain what happened. Bring in framework internals only when they matter for the current step.
- Check questions are optional, one at a time, and casual. Never spring a quiz.
- **`TODO.md` is the single source of truth.** Always say which TODO step we're on. Never invent steps outside it. If something new comes up, add it to `TODO.md` first, then do it.
- Tick items in `TODO.md` as they're completed.
- **Lesson → product (D3):**
  - Each concept starts as a 📘 lesson: a tiny sandbox script in `lessons/` (`w<week>_step<n>_<name>.py`).
  - Right after, a 🏗️ product step moves what we learned into `src/finsight/`.
  - Experiment-only steps (look inside, break it) stay as lessons.
  - Always say which half we're in.
  - The user has read the book, so lessons are hands-on and cite the book section instead of re-teaching theory.

Every unit of work follows this loop. **Don't skip steps.**

1. **Walkthrough before code.** Explain the concept plainly:
   - what problem it solves,
   - how MAF implements it under the hood,
   - the relevant book section.

   Then ask 1–2 questions to check understanding before moving on.
2. **Decision.** For every real choice:
   - Present 2–3 options with their tradeoffs: cost, latency, reliability, complexity, and how each carries over to the Bcdr work.
   - Give a recommendation.
   - **The user decides.** Don't pick silently.
   - Record the decision and its *why* in `DECISIONS.md` (date, options, choice, reason).
3. **Build in small steps.** Prefer having the user write or drive the core pieces. When Claude writes code, keep it small and explain the important lines. No large code drops.
4. **Break it on purpose.** Prove each concept by triggering its failure mode first, then fixing it. Examples:
   - no termination condition → a runaway loop,
   - poisoned memory,
   - context overflow,
   - a prompt injection inside a filing.
5. **Measure.** Every "better" claim needs an eval number, compared against the previous run.
6. **Reflect.** The user answers each week's reflection questions in `NOTES.md` in their own words. Claude reviews the answers and points out gaps; Claude doesn't write the answers.

Don't move to the next TODO item until its acceptance check has actually been run and has passed. Running it means real execution, not reasoning about what would happen.

## Stack

- **Python 3.12**, managed with **`uv`**.
- **Microsoft Agent Framework** (`agent-framework`, Python).
  - **API caution:** the framework moves fast. Before using an API, verify it against the *installed* package version by checking its source or signatures and the official samples. Don't rely on remembered signatures.
  - BcdrSequential found real drift this way:
    - `Agent`, not `ChatAgent`.
    - Structured output is `agent.run(..., options={"response_format": Model})` → `response.value`.
    - The client is `agent_framework.openai.OpenAIChatClient` with `azure_endpoint=` / `api_key=`.
    - The checkpoint pickle allow-list exists, and missing types fail *silently*.
- **Azure (subscription "Visual Studio Enterprise Subscription")**
  - Foundry resource `atlas-foundry-hma96`, RG `AgenticAI`, region westus3. Deployments:
    - `gpt-5.4`: main reasoning and vision.
    - `gpt-5.4-nano`: cheap roles such as routing and extraction.
    - `text-embedding-3-large`: use `dimensions=1024`.
  - To be created as each week needs it (discuss first):
    - Azure AI Search (Free tier),
    - Application Insights,
    - optionally Cosmos DB (free tier).
  - Final step only: Container Apps environment `atlas-env` (already exists in `AgenticAI`).
  - Creating, changing or deleting Azure resources is an outward-facing action. **Confirm with the user first** and state the expected cost. Prefer free tiers.
- **Data (real and public; no synthetic data):**
  - **FinanceBench** (PatronusAI, open-source subset of 150 questions with gold answer, evidence text and evidence page). PDFs come from the `patronus-ai/financebench` GitHub repo.
  - **SEC EDGAR APIs** (`submissions`, `companyfacts`). They require a descriptive `User-Agent` header and allow at most 10 requests/second.

## Credentials and `.env`

- Use the **shared root `../.env`** (loaded by relative path, per the parent `CLAUDE.md`). Never duplicate credentials into this folder.
- Existing keys: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.
- If a new key is needed (e.g. `AZURE_SEARCH_ENDPOINT`, `SEC_USER_AGENT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`), add it to the root `.env` and document the name (never the value) in `.env.example`.
- Never print, log or trace secret values.
- When OTel content capture is on, make sure no keys end up in spans.
- In the cloud (final step), use managed identity and RBAC instead of keys.

## Data and evaluation rules

- `data/` is gitignored and holds PDFs, rendered page images and splits.
- The splits are `data/splits/dev.jsonl` (for tuning) and `data/splits/test.jsonl` (held out).
- **Never tune prompts, tools or parameters on `test`.** Run `test` only at the end of week 5, and the user must explicitly OK each run.
- Every change that might affect quality gets an eval run on `dev`. Results go to `evals/results/<timestamp>_<config>.json`, with one row per configuration in `evals/leaderboard.md`.
- Each result records:
  - accuracy (numeric match within tolerance),
  - citation hit rate,
  - tokens (input, cached and output),
  - $ cost (from `src/finsight/pricing.py`),
  - p50/p95 latency,
  - number of tool calls.
- Eval runs cost real money. Before a full-set run, state the rough $ estimate. Use a small subset (`--limit`) while iterating.

## Repo layout (target; grows week by week)

```
FinalProject/
├── CLAUDE.md  TODO.md  NOTES.md  DECISIONS.md  pyproject.toml  .env.example
├── data/                 # gitignored: pdfs/, pages/, splits/
├── src/finsight/
│   ├── agents/           # analyst, specialists, verifier, router
│   ├── prompts/          # *.md system prompts (versioned, diffable)
│   ├── tools/            # calculator, page renderer, retriever
│   ├── mcp_edgar/        # our own MCP server (FastMCP): stdio + streamable HTTP
│   ├── memory/           # notes store (memory-as-tool), episodic ContextProvider
│   ├── rag/              # ingest, chunkers, search client
│   ├── orchestration/    # workflow graph + pattern variants
│   ├── middleware/       # logging, cost meter, guards
│   ├── telemetry.py
│   └── pricing.py
├── evals/                # harness, scorers, judge, results/, leaderboard.md
├── web/                  # final step: FastAPI + SSE backend, React frontend
├── infra/                # final step: Bicep/azd, Dockerfiles
└── tests/
```

## Commands (fill in as they come to exist)

- `uv sync`: install
- `uv run pytest`: tests. They must pass **offline**, using a stub chat client or replayed responses with no Azure calls.
- `uv run python -m evals.run --split dev [--limit N] [--config NAME]`: eval run
- `uv run python -m finsight.mcp_edgar`: run the MCP server (stdio by default)

## Coding conventions

- Pydantic models for every agent output and every message that crosses an edge.
- Use structured output wherever it can replace parsing.
- System prompts live in `src/finsight/prompts/*.md`, not inline strings, so prompt changes show up as diffs and can be tied to eval results.
- Async throughout (MAF is async-first).
- Minimal is fine. Start with the simplest version that teaches the concept, and refactor only when a later week needs it.
- Comments explain *why*. Link to the book section or the `DECISIONS.md` entry when a choice isn't obvious.
- Never commit `.env`, `data/`, checkpoints or eval artifacts that contain filing text over size limits.
- Ask before committing. Commits happen only when the user asks.

## Book map (where each concept lives)

| Topic | Book section |
|---|---|
| Agent loop, tools, structured output | 4.1–4.6 |
| Memory and RAG | 4.7, 4.8 |
| Middleware, OTel | 4.9, 4.10 |
| Agents as tools, context engineering | 4.11, 4.12 |
| Humans in the loop | 4.13 |
| Workflows | Ch 6 |
| Autonomous orchestration and terminations | Ch 7, 2.3–2.5 |
| UX | Ch 3 |
| Web apps and deployment | Ch 8 |
| Frameworks | Ch 9 |
| Evaluation | Ch 10 |
| Failure modes and optimization | Ch 11 |
| MCP and A2A | Ch 12 |
| Responsible AI | Ch 13 |
| Unstructured-data workflow | Ch 14 |
| Prompts | 15.3 |
