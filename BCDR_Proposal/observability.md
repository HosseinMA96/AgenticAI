# Observability

## Constraints

- **[Decided]** There is no OpenTelemetry pipeline yet. The **App Insights v2 SDK** (`TelemetryClient`) is available.
- **[Proposed]** Interim second sink: log tables in SQL with a TTL. They allow ad-hoc queries and joins with assessment data while the platform adds OTel.

## Design: one decorator, swappable sinks

**[Proposed]** Agents and tools never call telemetry code themselves. Instead:

- A **decorator around the chat client** (a `DelegatingChatClient`) records every model call: tokens from the response's usage, latency, model and errors.
- A **wrapper around tool invocation** (function-invocation middleware, or a thin wrapper inside each `AIFunction`) records every tool call: name, duration, success, result size.
- The **step runner** records one row per run: outcome, finding counts, verifier result, versions and totals.
- All three write to an `IAgentTelemetrySink` interface. v1 has two implementations, App Insights v2 and SQL.

When OTel arrives, we add an OTel sink (or turn on MAF's built-in OTel instrumentation) and retire the others. **No agent code changes.**

## What we record

Everything carries `runId`, `assessmentId`, `stepId`, `promptVersion`, `rulesVersion` and `model`, so any number can be split by step and by version.

| Level | Fields |
|---|---|
| Run (one step on one assessment) | start/end, duration, outcome (ok / verifier-retry / needs-human-review / failed / limit-hit), model calls, tool calls, tokens in/cached/out, **$ cost**, finding counts by status |
| Model call | duration, tokens in/cached/out, finish reason, error/throttle (429) |
| Tool call | tool name, duration, success, error type, result size (bytes or rows) |
| Feedback | Stored separately in `CommentFeedback` (👍/👎, reason code, role; see `evaluation.md`). Not subject to the telemetry TTL. |

**Cost:** computed in code from tokens × a small price table (`pricing` config). Recorded per run, not estimated afterwards.

## App Insights v2 mapping

| Our concept | App Insights v2 |
|---|---|
| Step run | `RequestTelemetry` (or an operation started with `StartOperation`) named `step:<stepId>` |
| Model call | `DependencyTelemetry`, type `LLM`, with tokens in custom properties/metrics |
| Tool call | `DependencyTelemetry`, type `Tool`, target = tool name |
| Tokens, cost | `TrackMetric` (or custom measurements on the run) |
| Failures | `TrackException` with `stepId` / `runId` |

Model and tool calls share the run's operation id, so the portal's end-to-end transaction view shows one step run as a tree. That is the closest thing to a trace before OTel arrives.

## SQL log tables (interim)

```
AgentRun      (RunId PK, AssessmentId, StepId, StartedAt, DurationMs, Outcome, Model,
               PromptVersion, RulesVersion, ModelCalls, ToolCalls,
               TokensIn, TokensCached, TokensOut, CostUsd, CreatedAt)
AgentCall     (RunId FK, Seq, Kind {Model|Tool}, Name, DurationMs, Success, ErrorType,
               TokensIn, TokensOut, ResultSize, CreatedAt)
```

- TTL: a scheduled job deletes rows older than N days. **[Open]** N is 30–90 days.
- `AgentRun` aggregates may be kept longer, for trend charts.

## Content and privacy

- **[Proposed]** By default, record **no evidence text, prompts or model output** in telemetry. Record only metadata and numbers.
- A **debug capture** flag, per step and time-limited, stores full prompts and responses in a separate table with a short TTL (e.g. 7 days). It is used to investigate bad findings.
- Never record keys or connection strings. The decorator copies an allow-list of fields; it doesn't serialize whole objects.

## Dashboards and alerts

**Dashboard per step:**
- runs/day,
- p50/p95 latency,
- $/run and $/day,
- tokens/run,
- tool calls/run,
- outcome mix (incl. NeedsHumanReview %),
- error and throttle rate,
- split by `promptVersion` / `rulesVersion`, to see the effect of each change.

**Alerts [Proposed]:**
- failure or limit-hit rate above X%,
- p95 latency above the target,
- daily cost above the budget,
- a sudden jump in tokens/run (often a prompt or data change pulling in too much evidence).
