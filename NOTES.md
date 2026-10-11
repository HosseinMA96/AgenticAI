# FinSight — Reflection notes

Answers in your own words. Claude reviews them and points out gaps; it doesn't write them.

## Week 1

### 1. Tool vs MCP tool vs agent-as-tool
When would you use each one? What does each cost you, and what does it buy you?

_Your answer:_
Tool: Simple local function. MCP: More advanced reusable function to be shared. AaaT: When task is complex and we don't want to clutter main agent context


> **Claude's review (gaps):**
> - MCP isn't "more advanced"; it runs as a separate program. That's what makes it shareable (with other apps, even other languages). Cost: an extra process, a bit more latency, and trust (the fetch server's tool description told our agent what to do, D13).
> - The model can't tell a local tool from an MCP tool: it sees only a name and a description. MCP only changes where the code runs.
> - Agent-as-tool costs a whole extra LLM call (tokens, money, time). You pay that to get reasoning back instead of just data.


### 2. Why build the eval before tuning the prompt?

_Your answer:_
Eval: We need a benchmark foundation to evaluate against based on the improvements that we make so that stuff are measurable and have real gains (or we can measure tradeoff in different dimensions)

> **Claude's review (gaps):**
> - Noise: two runs of the same prompt failed on different questions (only 2 of 6 overlapped). A +1 change means nothing without the baseline.
> - Gut feeling would have fooled us: the cross-check sounded like an improvement; only the eval showed +46% cost for no real gain (D16).
