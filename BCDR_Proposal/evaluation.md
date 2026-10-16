# Evaluation

The goal is to know, **on every deployment and every rules change**, whether each step got better or worse, and to block releases that regress.

## Two kinds of tests

| | Unit tests | Eval runs |
|---|---|---|
| Where | CI build, on every PR | Deployed test / pre-prod environment |
| Network / model calls | **None** (stub chat client or recorded responses) | Real model, real connectors |
| What they check | Tool wrappers, verifier checks, output schema, comment posting, limit handling | Quality of each step's findings against gold labels |
| Speed / cost | Seconds, free | Minutes, real $ |

- **[Decided]** CI allows only unit tests with no network calls. So quality evals run as a **post-deployment job** in an environment where network calls are allowed.

## Test services: test data that lives where real data lives

**[Proposed]** Test evidence is stored **in the same SQL tables and blob containers as real evidence**, under dedicated **test service IDs**. The agent's tools and connectors then run unchanged; only the service ID differs, so no code path exists just for tests.

- **Source:** where possible, anonymized copies of past assessments with a known approver decision. Purely made-up cases tend to be easier than real ones.
- **Frozen:** test evidence is never edited in place. A change creates a new test service, or a new version of one, so scores can't shift without an agent change.
- **Isolated:** test services are flagged as test data.
  - Their comments don't notify anyone.
  - Their runs are tagged `isEval`, so they never show up in production dashboards or metrics.

### Gold labels

Gold labels live in a SQL table next to the test data:

```
EvalGoldLabel (TestServiceId, StepId, RuleId, ExpectedStatus, MustCiteEvidenceIds,
               LabelVersion, LabelledBy, LabelledAt, Notes)
```

- Labels come from **historical approver decisions** where possible. The rule owner settles label disagreements.
- Labels are versioned. A rules change that changes the correct answer needs a label update in the same change.

## Eval run API: a long-running job

An eval run can take minutes, so it uses **start-then-poll**, never one blocking call:

| Call | Does |
|---|---|
| `POST /evals/runs` `{steps?, serviceIds?, limit?}` | Starts a run and returns **`202 Accepted`** with a `runId` right away |
| `GET /evals/runs/{runId}` | Status (`running` / `completed` / `failed`), progress (e.g. 34 of 60 cases), metrics so far |
| `GET /evals/runs/{runId}/results` | Per-step metrics, per-case details, cost, latency, and **pass/fail against the gate** |

**Behind the API [Proposed]:**
- A background worker or queue runs each step agent for each test service.
- **Limited concurrency**, so runs stay within the model's tokens-per-minute quota.
- **Results are saved per case as each one finishes.** A run that crashes can resume without paying for finished cases again.
- **One active eval run per environment**, so two pipelines don't compete for the same quota.
- A rough guide: 20 services × 5 steps = 100 step runs. At about 30–120 s each and 10 in parallel, that's roughly 5–20 minutes.

Results are stored in SQL with:
- `runId`,
- `promptVersion` / `rulesVersion` / `model` per step,
- metrics, tokens, $ cost, p50/p95 latency and the number of tool calls.

A per-step leaderboard (one row per run) shows the trend over time.

## Scoring

| What | How |
|---|---|
| Status per rule | Exact match in code. Missing/Insufficient vs Met is the key distinction. |
| Recall / precision of flags | Code, from the per-rule confusion matrix |
| Citation validity | Code checks that the cited ids exist and that the `MustCite` ids are present. Later, an LLM judge checks that the quote supports the claim. |
| Guidance quality (later) | LLM judge with a fixed rubric (actionable? specific to this evidence? consistent with the rule?) |

**[Proposed] Judge calibration** (once a judge is added): a person scores about 30 findings, and we compare them with the judge's scores. Use the judge only if agreement is at least 80%, and re-check whenever the judge prompt or model changes.

### Dev vs holdout

- Tag each test service as `dev` or `holdout`.
- Tune prompts and rules on **dev** only.
- **Holdout** runs only at release gates. If people tune against it, it stops measuring anything.

### Non-determinism

LLM output varies between runs. At the release gate, run each case 3 times and report the mean and the spread. A drop smaller than the spread is noise, not a regression.

### Cost of evals

Each eval run makes real model calls, and its $ cost is recorded. Estimate before a full run: (cases × repeats × avg tokens per case) × price. While iterating, use `limit` or a single step.

## Phasing

| Phase | Eval capability |
|---|---|
| **Pilot** | 10–20 test services with gold labels for the pilot step. A simple script or job scores them and prints a table. No gate yet. **Built alongside the first agent, not after it.** |
| **Rollout** | The eval run API above. Gold sets for every step. The pipeline calls it after deploying to pre-prod and promotes only on pass. |
| **Improve** | LLM judge for guidance quality, repeat runs at the gate, holdout set, gold sets growing from production feedback |

## The release gate (Rollout phase)

```
deploy to pre-prod → POST /evals/runs (holdout) → poll every 30–60 s (overall timeout)
     → read pass/fail → promote to prod, or stop the release
```

A run **fails the gate** in either case:
- any step is below its `success.md` target,
- or any step dropped more than a set margin (e.g. 3 points on recall) below the last released version.

## What triggers an eval run

| Change | Eval required |
|---|---|
| `rules.md` or `prompt.md` of a step | That step, dev set, before merge (run against the test environment) |
| Model or model version change | All steps, dev + holdout |
| Runtime, tool or verifier code | All steps, dev set |
| Release | All steps, holdout (gate) |

## Online quality signals (production)

Offline gold sets go stale, so these signals are measured in production:

- **Approver override rate**: how often the approver's decision contradicts the agent's finding, per step and per rule. This is the best real-world quality signal.
- **Thumbs up / thumbs down** on each comment, from both audiences (details below).
- **Verifier failure rate** and **NeedsHumanReview rate** per step.
- Overridden or thumbs-down findings are reviewed weekly. Confirmed agent errors become **new test services with gold labels**, so the test set grows where the agent is actually weak.

### User feedback: thumbs up / down

**[Proposed]** Every agent comment (one per rule finding) shows 👍 / 👎 to **service owners** and to **approvers / business owners**. A 👎 asks for an optional reason code and a free-text note. Feedback is stored in SQL. It is **not** subject to the telemetry TTL, because it is the raw material for new gold labels.

```
CommentFeedback (FeedbackId, RunId, AssessmentId, StepId, RuleId, FindingStatus,
                 Rating {Up|Down}, ReasonCode?, Comment?, UserRole {Owner|Approver|Business},
                 UserId, PromptVersion, RulesVersion, CreatedAt)
```

- **Reason codes:**
  - `WrongStatus` (e.g. said Missing but the evidence is there),
  - `WrongCitation`,
  - `GuidanceNotActionable`,
  - `RuleMisread`,
  - `Other`.
- **Role is recorded,** because the two audiences judge different things. Owners judge whether the guidance helped; approvers judge whether the verdict was right. Report them separately.
- **Versions are recorded,** so a rise in 👎 can be tied to a specific prompt or rules change.
- **Metrics per step and per rule:**
  - 👍 rate,
  - 👎 rate by reason code,
  - feedback coverage (% of comments that got any rating).
- **How it's used:**
  - The weekly triage reviews 👎 items. Confirmed errors become new test services with gold labels, and recurring reasons lead to `rules.md` edits (see `learning-and-memory.md`).
  - 👎 is a **signal to review, not a label**. A person confirms the correct answer before it enters the gold set, because users sometimes vote 👎 on a correct finding they don't like.
- **Caveat:** most comments get no rating, and people vote more often when they're unhappy. Treat feedback as a way to **find problems**, not as an accuracy number. Accuracy comes from the eval runs.
