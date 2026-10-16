# Learning and Memory

## What "learning" should mean here

The system should get better over time, and the improvement must **survive across sessions and deployments**. It must also be **reviewable**: a person can see what changed, why, and whether it helped. A model silently changing its own behaviour does not meet that bar.

## Recommended v1: learning through reviewed artifacts

```
 agent comment ──► user feedback (👍 / 👎 + optional reason)
                        │
                        ▼
              weekly triage (rule owner + engineer)
               │                         │
               ▼                         ▼
     new gold test case          proposed rules.md / prompt.md edit (PR)
               │                         │
               └──────► eval run on dev ◄┘
                              │
                     passes gate? ──► merge → next deployment uses it
```

1. **Business rules as versioned markdown** (`rules.md` per step). The business owns them and changes them by PR. Every change runs that step's eval before merge. This is the main "memory" of the system, and it is human-written, versioned and tested.
2. **Thumbs up / down** on each comment from owners and approvers, stored in SQL with the finding id, role, versions and reason code (schema in `evaluation.md`).
3. **Feedback → test cases.** A confirmed agent mistake becomes a gold case, so the same mistake is caught automatically from then on.
4. **Feedback → rule edits.** When many people vote 👎 on the same kind of finding, the rule is usually unclear. The fix is a clearer rule, reviewed by the owner.
5. **Optional, low effort:** an LLM summarizes a week of 👎 findings into *suggested* rule edits for the triage meeting. A person accepts or discards each one.

This works even if the business only edits a markdown file by hand. Nothing in v1 depends on RAG.

## Why not let the agent write its own memory (v1)

We tested agent-written memory in a learning project (FinSight, Week 2). It failed in two ways that matter here:

- **The agent saved a false lesson.** Told it was wrong (by a bad gold label), it invented a plausible but false excuse and saved it as a "note". Later runs trusted that note.
- **Poisoned memory won.** One planted note that discredited a source document changed the answer in 3 out of 3 runs, until explicit defences were added.

For an advisory tool that approvers rely on, a wrong memory spreads silently to every future assessment. Human-reviewed rules plus eval gates avoid that.

## Phase 2 option: RAG

Add RAG only if evals show the agent needs **examples or reference material** that don't fit in the rules file. Candidates:

| Source | Use | Guardrails |
|---|---|---|
| Past assessments **signed off by approvers** | "Here is what good evidence for R3 looked like" (few-shot examples) | Curated set only. Each item has provenance (assessment id, approver, date). No raw history. |
| Policy / standards documents | Look up the meaning of a requirement | Versioned source. Re-index on change. |
| Common-issues FAQ written by rule owners | Better guidance text | Human-written, reviewed like rules |

**Rules for any RAG source [Proposed]:**
- **Only curated, human-approved content goes into the index.** Agent output never goes in by itself.
- Retrieved text is treated as reference material, never as instructions.
- Retrieval quality gets its own small eval (did we fetch the right example?) before it touches step accuracy.
- Adding RAG to a step needs a dev eval that beats the non-RAG baseline. Otherwise it isn't adopted.

## Short-term memory

Each step run is **stateless**: a fresh conversation with no history from earlier runs. A run doesn't need earlier conversations, and stateless runs are reproducible, which evals need.
