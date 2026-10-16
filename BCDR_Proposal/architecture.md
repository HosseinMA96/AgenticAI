# Architecture

## Overview

```
 trigger (evidence uploaded / assessment submitted / on demand)
        │
        ▼
 ┌──────────────────────── Step runner (fan-out, no orchestration) ───────────────────────┐
 │                                                                                         │
 │   Step A agent        Step B agent        Step C agent      ...  (run in parallel)       │
 │   ┌───────────┐      ┌───────────┐      ┌───────────┐                                   │
 │   │ 1 gather  │      │           │      │           │   each = same runtime code       │
 │   │ 2 assess  │      │   same    │      │   same    │   + its own step pack            │
 │   │ 3 verify  │      │           │      │           │                                   │
 │   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘                                   │
 └─────────┼──────────────────┼──────────────────┼─────────────────────────────────────────┘
           ▼                  ▼                  ▼
     typed comments → post to assessment (idempotent)     telemetry decorator → App Insights v2 / SQL log
```

- **[Decided]** Steps are independent, so the runner is a plain fan-out with no agent-to-agent hand-off. One step failing does not block the others.
- **[Proposed]** A step's run is keyed by `(assessmentId, stepId, evidenceVersion)`. A rerun with the same key replaces the previous comments instead of adding duplicates.
- **[Open]** When does a step run? The options are: when evidence is uploaded, when the assessment is submitted, on demand from the UI, or a nightly sweep for auto-pulled data. The answer affects cost, so pick one primary trigger for v1.

## The step-agent runtime

The runtime is a single generic component. A step pack configures it (see `step-pack-contract.md`):

| Part | Comes from |
|---|---|
| Instructions | The shared base prompt, plus the step's prompt, plus the step's **business-rules file** (versioned markdown) |
| Tools | The shared read-only tools the pack enables (below) |
| Output schema | The shared `StepAssessment` contract (below); a step may add fields |
| Limits | Max model calls, max tool calls and a timeout per run. They are set explicitly per step, never left at framework defaults. |

**[Proposed]** A sketch in .NET. *This is illustrative only: MAF's .NET API changes quickly, so check exact type and method names against the package version we install.*

```csharp
// Tools wrap the existing connectors. They are read-only and scoped to the
// assessment being reviewed.
var tools = new[]
{
    AIFunctionFactory.Create(evidence.ListEvidenceAsync,  "list_evidence",  "List evidence items for this step"),
    AIFunctionFactory.Create(evidence.ReadSqlFieldsAsync, "read_fields",    "Read structured fields for this step"),
    AIFunctionFactory.Create(evidence.DownloadBlobAsync,  "read_document",  "Read one evidence document by id"),
};

var agent = new ChatClientAgent(
    chatClient: meteredClient,                      // wrapped by the telemetry decorator
    instructions: pack.BuildInstructions(),         // base + step prompt + rules.md
    tools: tools);

var result = await agent.RunAsync<StepAssessment>(pack.BuildUserMessage(assessmentId), ct);
```

## Per-step flow: gather → assess → verify

1. **Gather.** The agent calls tools to list and read the step's evidence. Tool wrappers receive the `assessmentId` from the runtime, not from the model, so the agent **cannot read other assessments**, even by mistake.
2. **Assess.** The agent checks the evidence against each rule in the rules file and returns a typed `StepAssessment` (structured output, no text parsing).
3. **Verify.** **[Proposed]** v1 uses deterministic code checks, which are cheap and catch the worst errors:
   - Every citation points to an evidence id that a tool **actually returned in this run**, so made-up citations are rejected.
   - `Met` needs at least one citation. `Missing` needs non-empty guidance.
   - Every rule in the rules file has exactly one finding, so none is skipped.
   - A failed check triggers one retry with the error message. If that also fails, the step is marked `NeedsHumanReview` and the failure is logged.

   An **LLM verifier** that re-reads the cited evidence and confirms each claim is phase 2. Add it only if evals show unsupported "Met" claims that the code checks miss.

## Output contract

**[Proposed]** One finding per rule. *"Not enough evidence to decide" is a valid answer and must be easy for the model to give.* Otherwise models tend to invent a confident answer.

```csharp
public enum FindingStatus { Met, Missing, Insufficient, NeedsHumanReview }

public record Citation(string EvidenceId, string? Location, string Quote);   // Location: page/sheet/field

public record RuleFinding(
    string RuleId,               // matches an id in rules.md
    FindingStatus Status,
    IReadOnlyList<Citation> Citations,
    string? OwnerGuidance,       // for service owners: what to add or fix
    string? ApproverNote,        // for approvers: what to check by hand
    double Confidence);          // 0..1; for sorting and later calibration, not shown as truth

public record StepAssessment(
    string StepId,
    IReadOnlyList<RuleFinding> Findings,
    string Summary);
```

The runtime adds metadata **outside** the model output, so the model can't get it wrong: `runId`, `assessmentId`, `evidenceVersion`, `promptVersion`, `rulesVersion`, `model`, `timestamp`.

## Models

- **[Proposed]** Start every step on the main reasoning model. Move a step to a cheaper model only once its eval shows no quality drop. That gives a cost lever per step, decided by data.
- **[Open]** Some evidence is screenshots or scanned PDFs. Those need a vision-capable model, or a text-extraction step before the agent reads them.
