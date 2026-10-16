# Step Pack Contract

A **step pack** holds everything that makes one assessment step's agent different from the others. The runtime code is shared. **A step ships only once its pack is complete.**

## Layout

**[Proposed]** Packs live in a repo, so every change is a reviewed PR with history:

```
steps/
  <step-id>/
    rules.md            # business rules (owned by the business)
    prompt.md           # step-specific instructions (owned by engineering, reviewed by the business)
    pack.json           # tools enabled, limits, model, schema extensions, versions
    success.md          # definition of success and target numbers
    gold.md             # which test services cover this step, where they came from, who labelled them
```

The test evidence and gold labels themselves live in the test environment's SQL and blob storage, not in the repo (see `evaluation.md`).

## 1. `rules.md`: business rules

- One rule per heading, each with a **stable id** (e.g. `R3`), so findings, tests and feedback can refer to it.
- Each rule states:
  - what evidence satisfies it,
  - what counts as missing,
  - what counts as insufficient,
  - example guidance for the owner.
- The rule text is written for a careful new employee. If a person can't apply it consistently, the agent can't either.

```markdown
## R3: Recovery test performed in the last 12 months
- Met when: a test report dated within 12 months of the assessment date shows RTO achieved.
- Missing when: no test report is attached.
- Insufficient when: the report is older than 12 months, or doesn't state the measured RTO.
- Owner guidance: attach the latest failover test report, including the measured recovery time.
- Approver check: confirm the tested scope matches the service's critical components.
```

## 2. `pack.json`: configuration

```json
{
  "stepId": "recovery-testing",
  "rulesVersion": "2026-10-15.1",
  "promptVersion": "3",
  "model": "main",
  "tools": ["list_evidence", "read_fields", "read_document"],
  "limits": { "maxModelCalls": 8, "maxToolCalls": 20, "timeoutSeconds": 120 }
}
```

## 3. Gold test cases: test services + gold labels

A gold case is a **test service**: frozen evidence stored in the same SQL tables and blob containers as real evidence, under a test service ID. Each test service has one **gold label** per rule in the `EvalGoldLabel` table (see `evaluation.md`). For example:

| TestServiceId | StepId | RuleId | ExpectedStatus | MustCiteEvidenceIds | Notes |
|---|---|---|---|---|---|
| test-svc-014 | recovery-testing | R3 | Insufficient | ev-551 | Report is 14 months old; approver flagged it in the real review |
| test-svc-014 | recovery-testing | R4 | Met | | |

**Pilot minimum [Proposed]:** 10–20 test services for the pilot step, enough to start measuring.

**Minimum for a step to ship in Rollout [Proposed]:**
- **20 dev cases plus 10 holdout cases.**
- Coverage:
  - at least 5 fully good,
  - at least 5 with something missing,
  - at least 5 insufficient or partial,
  - plus edge cases (wrong document type, unreadable file, auto-pulled data missing).
- Labels come from **historical approver decisions** where possible. Label disagreements are settled by the rule owner.

## 4. `success.md`: definition of success

Each step fills in its targets. The defaults are a starting point:

| Metric | Meaning | Default target |
|---|---|---|
| Missing-evidence recall | Of the rules that are really Missing or Insufficient, the share the agent flagged | **≥ 95%** (most important: a false "looks good" misleads approvers) |
| Flag precision | Of the rules the agent flagged, the share that were really a problem | ≥ 80% (too many false alarms and people stop reading) |
| Status accuracy | Exact status match per rule | ≥ 85% |
| Citation validity | The cited evidence actually supports the finding | ≥ 95% |
| Guidance quality | Judge score on a rubric (actionable, specific, correct) | ≥ 4 / 5 average |
| Cost / latency | $ per step run, p95 latency | Set per step after the baseline |

## Definition of done for a step

- [ ] `rules.md` reviewed and signed off by the rule owner
- [ ] Test services and gold labels loaded in the test environment, meeting the minimum size and coverage, with their source documented in `gold.md`
- [ ] `success.md` targets agreed with the business
- [ ] Baseline eval run recorded. Targets met, or gaps accepted in writing.
- [ ] Telemetry visible for the step on the dashboard
- [ ] Named owners: rules (business), prompt and pack (engineering)
