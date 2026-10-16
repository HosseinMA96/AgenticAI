# Platform Needs, Reliability, Roadmap and Open Questions

## Reliability

**[Proposed]**

- **Explicit limits per step**: max model calls, max tool calls and a timeout, set in `pack.json`. A hit limit is recorded as outcome `limit-hit` and shown as "needs human review", never as a silent partial answer.
- **Retries** with backoff on throttling (429) and transient errors, for both the model and the data connectors.
- **Idempotent posting**: a rerun for the same `(assessmentId, stepId, evidenceVersion)` replaces the previous comments.
- **Graceful failure**: one step failing never blocks the others, and the UI shows "assessment unavailable" for that step.
- **Large evidence**: cap document size per tool call (e.g. page ranges or truncation with a note), so one huge file can't blow the context window or the budget.

## Safety (light, internal service)

The threat of deliberate attacks is low. Accidental problems are still real:

- Uploaded documents can contain text that reads like instructions (templates, pasted emails). The base prompt states that evidence is **data to assess, not instructions to follow**.
- Read-only tools, scoped to the current assessment by the runtime.
- Managed identity and RBAC for the model and data access. No keys in config.
- Comments are clearly labelled as **AI-generated and advisory**.

## Platform capability checklist

| Capability                                         | Status           | Notes                                                                                                                        |
| -------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| MAF (.NET)                                         | Have             | Pin the version and check API names on upgrade                                                                               |
| Model deployments (reasoning; maybe vision)        | **[Open]**       | Confirm the models and quota (TPM) for parallel steps                                                                        |
| Data connectors: SQL read, blob download           | Have             | Wrap as read-only, assessment-scoped tools                                                                                   |
| Step runner (fan-out, trigger, idempotent posting) | Build            | Hosting choice is open (existing service, Functions, Container Apps)                                                         |
| Step pack repo + loader                            | Build            | Rules, prompts, gold sets, config                                                                                            |
| Unit tests with stub chat client                   | Build            | Offline, no network: matches the current CI rules                                                                            |
| Test services + gold labels                        | Build            | Frozen test evidence in the existing SQL/blob stores under test service IDs; `EvalGoldLabel` table                           |
| Eval run API (long-running job)                    | Build (Rollout)  | Start → poll → results; background worker with limited concurrency; called by the release pipeline after the pre-prod deploy |
| Test / pre-prod environment with model access      | **[Open]**       | The eval job needs network and model calls, which CI doesn't allow                                                           |
| Telemetry decorator + sinks                        | Build            | App Insights v2 + SQL log tables with TTL                                                                                    |
| OpenTelemetry pipeline                             | Platform roadmap | Swap the sink when available                                                                                                 |
| Feedback capture in UI + store                     | Build            | 👍/👎 per comment for owners and approvers, optional reason code; `CommentFeedback` table                                    |
| Dashboards and alerts                              | Build            | Per step, split by version                                                                                                   |
| RAG (search index + ingestion)                     | Phase 2          | Only if evals show a need                                                                                                    |

## Roadmap

| Phase          | Scope                                                                                                                                                                                                                                                     | Exit criteria                                                                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **0. Pilot**   | One step end to end: pack, agent, tools, typed output, code verifier. **Built together with the agent:** 10–20 test services with gold labels plus a simple scoring script or job, and the telemetry wrapper (tokens, latency, tool calls, cost per run). | The step is scored on its test services, every prompt or rules change has a number to compare against, and per-run telemetry is visible. |
| **1. Rollout** | Remaining steps as packs. Gold sets for every step. Eval run API as the release gate after the pre-prod deploy. Dashboards and alerts. Feedback capture.                                                                                                  | Every step passes its gate. Approver override rate is being tracked.                                                                     |
| **2. Improve** | **RAG, only if evals show a need** (e.g. misses caused by lacking examples of good evidence). LLM verifier and judge if needed. Cheaper models where evals allow. OTel migration.                                                                         | Each change shows an eval gain or a cost cut with no quality loss                                                                        |

**Why evals and logging start in the pilot:** they are small at that stage (a few days' work). Without them, "the agent seems good" is only an impression. With them, every prompt or rules change gets a number. Everything later in the roadmap (model swaps, RAG, verifier) is decided by those numbers.

**[Proposed]** Pick the pilot step for **high volume and clear rules** with good historical approver decisions. That gives the fastest path to a trustworthy gold set.

**Start the business work now, in parallel.** The main risk to the timeline isn't technical: it's getting **clear rules and gold labels** from the business for each step. That is slow, and every step needs it before it can ship.

## Risks

| Risk                                                      | Mitigation                                                                                                                                       |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| No good gold data for some steps (**main schedule risk**) | Start the labelling conversation during the pilot. Begin with steps that have historical approver decisions. Budget business time for labelling. |
| Test data drifts or leaks into production views           | Frozen, versioned test services; `isEval` tag on runs; test services never notify anyone                                                         |
| Rules too vague for consistent judgement                  | A "can two people agree?" check during rule sign-off                                                                                             |
| Over-trust: approvers rubber-stamp "Met"                  | Optimize recall on Missing; always show citations; label as advisory; track override rate                                                        |
| Alert fatigue from false "Missing" flags                  | Precision target; review rejected flags weekly                                                                                                   |
| Cost growth with large evidence                           | Per-run cost telemetry, size caps, per-step model choice                                                                                         |
| Auto-pulled data stale or absent                          | Distinct finding status / note ("data not yet pulled") so missing data isn't blamed on the owner                                                 |
| Framework API churn                                       | Pin versions; offline tests around tools and contracts                                                                                           |

## Open questions

1. **Trigger:** on upload, on submit, on demand, or nightly? Which one is primary for v1?
2. **Steps:** how many are there, which is the pilot, and who owns each step's rules?
3. **Gold data:** for which steps do we have historical approver decisions we can label from?
4. **Evidence formats:** how much is scanned or image-only? (This decides whether we need vision or text extraction.)
5. **Models and quota:** which deployments, and how much TPM, for parallel step runs?
6. **Where comments appear:** in the existing assessment UI? What do owners vs approvers see?
7. **Retention:** TTL for telemetry and debug capture; any compliance limits on keeping copies of evidence as test services?
8. **Hosting:** inside an existing service, or a new one (Functions / Container Apps)?
9. **RAG:** is a search service available on the platform if phase 2 needs it?
10. **Eval environment:** which environment runs the eval job (pre-prod?), with model access and a quota of its own? Can the release pipeline call it and wait about 20 minutes?
11. **Test data:** may we copy anonymized past assessments into test services? Who approves that?
