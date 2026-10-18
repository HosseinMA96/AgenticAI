# Discussion Log: Platform Boundary (with the Architect)

**Dates:** 2026-10-17 / 18
**Status:** a record of the discussion and our assessment. **The other docs in this folder have not been updated for it yet** (see the last section).

## 1. The architect's position

- **The platform owns the agent runtime:**
  - MAF,
  - the A2A server,
  - orchestration (later),
  - observability,
  - evaluation.
- **No MAF logic in the business layer.** Business apps don't define workflows or call MAF directly.
- **Business developers write MCP servers and tools.** The tools use the platform's existing hexagonal connectors (SQL, Cosmos DB, Azure AI Search).
- **The business supplies the prompts** for its agents.
- **v1 supports single agents only.** Workflows and orchestration come later.
- **The platform is generic, not tailored to each app.** It's a general agent platform that acts on whatever MCP tools an app defines.
- **Rationale:** standardization, so each team doesn't build its own version. That makes troubleshooting easier and matches how connectors already work on the shared platform.
- **On observability and eval:** most of those details are platform-internal, and the business developer's concern is the MCP tool definitions. Eval suites that business teams can run are **likely** planned.

## 2. Our position

- Business owns the **levers that decide quality**: prompts, rules and MCP tools. Whoever owns a lever needs the gauge for it, so business needs telemetry and evals for its own agents.
- **Example:** retrieval settings (vector vs keyword vs hybrid, with or without a reranker). The best choice depends on the app's data. If the platform fixes one setting for everyone, some apps get suboptimal results. That's the tradeoff of this kind of standardization.

## 3. Assessment

### Where the architect is right

- **MAF churn is paid once.** The framework changes quickly. We saw this while learning: renamed classes, a changed structured-output API, checkpoint types that fail silently. One platform means one team absorbs that.
- **Consistency:** one agent loop, retry policy, tracing setup, auth model and place to manage quota. That's easier to troubleshoot on a shared platform.
- **It fits BCDR.** Our steps are independent single agents, so "single agents only" costs us nothing in v1.
- **Business developers don't need to write the agent loop.** Tool calling and A2A plumbing are generic.

### The gap

- **Running reliably is a platform property.** The platform can guarantee it.
- **Producing correct BCDR findings is not.** That comes from prompts, rules, tools and data, which are all business-owned. Only BCDR gold labels can tell us whether a finding is right.
- So the disagreement isn't **where** the boundary is. It's **what crosses it**:
  - **In** (app → platform): per-agent settings, our eval content (test services, gold labels, success criteria).
  - **Out** (platform → app): eval results and telemetry for our own agents.
- With those flows, the boundary works well. Without them, business owns quality but has nothing to measure it with.

### Platform eval suites (the architect said these are likely)

This closes most of the gap, **if** the suites support:

1. **Our own data and scoring:** our test services, gold labels and metrics (e.g. recall on missing evidence), not only generic checks.
2. **Per-case results:** which case failed, what the agent said, which tools it called.
3. **Cost and timing in results:** tokens, cost, latency and tool calls per run. Experiments (e.g. hybrid vs vector) can then happen *through* eval runs, without wider telemetry access.
4. **Comparing two configurations:** the same suite with one change (prompt version, model, retrieval setting), side by side.
5. **When it runs:** on demand while iterating, and in the release pipeline as a gate.

What's left after that is **production debugging**: read-only access to the trace of one real run, for example after a 👎 on a comment.

## 4. The retrieval-config argument

**Why it holds up:** retrieval settings change results, and the best choice depends on the data. In the FinSight learning project, on a single dataset:
- page-aware chunks reached 63% recall@5, against 43% for fixed-size chunks;
- vector search beat hybrid, which isn't the usual default.

BCDR evidence (SQL fields, test reports, screenshots) looks nothing like 10-K filings, so its best settings will probably differ.

**Stronger framing: standardize the mechanism, set parameters per app.**
- The platform owns the retrieval code. Each agent's config sets the parameters (search mode, reranker on or off, top-k), with sensible defaults.
- Azure AI Search already works this way: one service, with options on each query.
- This keeps the architect's standardization and removes most of the downside. It's a request for **config knobs**, not for a different boundary.

**Check where RAG sits:**
- If retrieval is a **tool** the agent calls, it's already on our side. Our MCP server calls the AI Search connector with the settings we choose, and no MAF is involved.
- If the platform **injects** retrieved context automatically, the config argument applies in full.

**Weakness:** the argument is hypothetical until we measure it on BCDR data. The likely reply is "the defaults are good enough." The fix is to run the same eval suite with two retrieval settings and show the difference, once eval suites exist.

**Expect pushback on chunking.** It's chosen when documents are indexed, not at query time, so a different chunking means a separate index. Concede this first if needed.

## 5. Questions for the architect / platform team

1. **Eval suites:** can we bring our own test data, gold labels and scorers? Do we get per-case outputs, cost and latency per run, A/B comparison of two configs? Can they run on demand and as a release gate?
2. **Per-agent config:** which settings can an agent definition set (model, reasoning effort, structured output schema, tool-call limits, retrieval settings)?
3. **RAG placement:** is retrieval a tool (on our side) or platform-injected context?
4. **Production debugging:** read-only traces and metrics for our own agents?
5. **Prompts:** how are prompts versioned and deployed, and is the version recorded on each run?
6. **Feedback:** who owns 👍/👎 capture on comments, us or the platform?
7. **Timeline:** when do eval suites and telemetry access arrive? If later than our pilot, what's the interim option (e.g. our own eval job calling the A2A endpoint)?

## 6. Impact on this proposal (pending; not yet applied)

If the boundary is confirmed:

| Doc | Change |
|---|---|
| `architecture.md` | The agent runtime and verifier become platform concerns. Our part is the **BCDR MCP server** (read-only, assessment-scoped tools over connectors, good tool descriptions and output sizes), plus prompts/rules and the output contract as a requirement. |
| `observability.md` | Split into **what the platform must expose to us** and **what our MCP server logs itself** (tool latency, errors, result size, retrieval settings used). |
| `evaluation.md` | The eval run API becomes a **platform ask**. We provide test services, gold labels and success criteria. Unit tests of our MCP tools stay ours. |
| `step-pack-contract.md` | Becomes what we hand the platform per agent: prompt/rules, tool list, output schema, config, gold set. |
| `platform-and-open-questions.md` | The checklist becomes a **platform asks** table. Add the risks of one-size-fits-all settings and of the platform's timeline. |
| `learning-and-memory.md` | Mostly unchanged. Feedback ownership is open (question 6). |
