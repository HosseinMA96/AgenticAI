# BCDR Advisory Agent: Requirements & Preliminary Design

**Status:** draft for the planning cycle (2026-10-15).
**Labels used in these docs:**
- **[Decided]**: a known platform fact or a firm requirement.
- **[Proposed]**: our recommendation; validate it during the build.
- **[Open]**: needs an answer from the business or the platform team.

## Problem

A BCDR assessment has several steps. Service owners upload evidence or type it in, and some of it is pulled in automatically. Approvers then review it. Today, nobody gets fast feedback on whether the evidence is complete and good enough before review starts.

## Goal

The goal is an **advisory first pass** on every assessment step, written for two audiences:

| Audience | What the agent tells them |
|---|---|
| Service owner (submitter) | What is missing or weak, and concrete guidance on how to fix it. |
| Approver / business owner | Whether the evidence already looks good, or exactly what they should check by hand. |

## Non-goals (v1)

- Approving or rejecting an assessment. A human always decides.
- Editing or deleting evidence. The agent's data access is read-only.
- Cross-step reasoning. Each step is assessed on its own.
- Defending against determined attackers. The service is internal and its users are Microsoft employees. Accidental bad input still matters (see `platform-and-open-questions.md`).

## Shape of the system

- **[Decided]** One agent per assessment step. The steps are independent, so there is **no orchestrator**: steps run in parallel and none depends on another step's output.
- **[Decided]** The platform is C# / .NET with Microsoft Agent Framework (MAF). Tools are local function calls that wrap the **existing data connectors** (SQL read, blob download). No MCP in v1.
- **[Proposed]** Every step uses the same runtime code. Steps differ only in their **step pack**: rules file, prompt, output schema, tools and gold tests. Adding a step means adding a pack, not writing a new agent.

## Must-haves

1. **Per-step test cases with gold answers and a written definition of success.** Each deployment runs them and is blocked if quality drops. See `evaluation.md`.
2. **Observability** for every agent: tokens, cost, latency, tool calls, failures and versions. See `observability.md`.
3. **Learning that survives sessions** without "bad memory". See `learning-and-memory.md`.

## Approach: start simple, measure from day one

1. **Pilot:** one step with its agent, tools, rules and typed output. In the same phase, add a **small eval** (10–20 test services with gold labels) and **basic telemetry**.
2. **Rollout:** all steps; an eval run API as the release gate; dashboards; feedback capture.
3. **Improve:** RAG, an LLM verifier or judge, cheaper models and OTel, **each only if the evals show it helps**.

**Feasibility:** the platform already has what v1 needs: MAF, the data connectors and App Insights. The main risk is getting **clear rules and gold labels** from the business for each step, so start that work during the pilot. Details are in `platform-and-open-questions.md`.

## Documents in this folder

| File | Contents |
|---|---|
| `architecture.md` | Runtime, per-step flow, tools, output contract, verifier |
| `step-pack-contract.md` | What each step team must deliver before its agent ships, with templates |
| `evaluation.md` | Gold sets, metrics, the deployment gate, online quality signals |
| `observability.md` | Telemetry design on App Insights v2 plus a SQL log table, and the OTel migration path |
| `learning-and-memory.md` | How the system improves over time without poisoned memory; RAG as phase 2 |
| `platform-and-open-questions.md` | Reliability, platform checklist, roadmap, risks, open questions |
| `architect-discussion.md` | Log of the platform-boundary discussion with the architect (2026-10-17/18): positions, assessment, questions, pending impact on these docs |
