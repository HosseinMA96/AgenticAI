# Interview question bank

Questions an interviewer could ask about FinSight. Claude adds new ones each week. You answer them out loud or in writing **without notes** during the Project review (`TODO.md`). Claude grades your answers against the `DECISIONS.md` entry in brackets.

## Week 1: one agent, tools, MCP, eval

1. Walk me through what happens, message by message, when your agent answers a question that needs a tool. What gets sent to the model on the second call? [Step 3]
   Answer: The agent discovers tool, finds out it needs to call out the tool and calls out the tool with the arguments, and on second call we send the tool call result added into the context to the model.
   **Verdict: mostly right.** Missing: the second call re-sends the _whole_ conversation (system prompt, question, the model's own tool-call request, and the result), because the model keeps no memory between calls. That's why long tool loops get expensive.
2. Your agent hit its tool-call limit and still produced a confident answer. Why is that dangerous, and how did you make it visible? [D5]
   Answer: Since it happens silently and model could be hallucinating because it couldn't use all the tools it need. We made a change to the answer shape so it counts tool calls and tells if it is equal or exceeded or tool-call limit.
   **Verdict: right idea, one detail off.** The danger is well put: a truncated answer looks just like a good one, while a runaway loop at least shows up in time and cost. The fix wasn't a change to `Answer`. After `run()`, `limits.py` counts the `function_call`s in the message list and returns a separate `limit_hit` flag. Worth adding: MAF forces the model to answer at the cap (`tool_choice="none"`), and the flag can raise false alarms, because reaching the cap doesn't prove more calls were needed.
3. Why structured output instead of parsing free text? Give a concrete case where parsing broke. [D7, D8]
   Answer: Parsing is very fragile, rather than forcing LLM response to be in a certain format. For example say we ask for a number and agent sends back 1,234 but we are looking for 1234 so here parsing breaks since we ignore comma
   **Verdict: right reason, but use the real example.** The comma case is made up; interviewers trust cases you actually hit. In lesson w1*step6 the regex grabbed **2022** (the year) instead of the revenue, because it took the first number in the sentence. Also say \_how* structured output fixes it: the API receives `Answer`'s JSON schema and the reply must match it, then Pydantic gives a typed `response.value` and validators reject bad combinations (e.g. found=false with a value).
4. The model invented a citation. Which defences stop that, and which ones can the model _not_ talk its way past? [Step 8]
   Answer: We can add a flag like has*citations and explicitly tell agent to put it false if no citations make sense. If the tool has problem (e.g. reads wrong tokens from screenshot of a page) we cannot talk model past it.
   **Verdict: first half right, second half misread the question.** "Talk its way past" means: which defences are \_prompts* (the model can ignore them) and which are _code_ (it can't). The layers:
   - Prompt-level, which the model can ignore: an honest way out (`found=false`, close to your flag), and field descriptions that say what counts as a citation.
   - Code-level, which it can't get past: the `Answer` validator runs in our code and rejects citations of pages that weren't in the evidence it was given.
   - Its limit: it catches _invented_ page numbers, not a _real_ page that doesn't support the claim. That needs the citation judge (eval) and later the Verifier.
5. When would you build a function tool, an MCP server, or an agent-as-tool? What does each cost you? [D15]
   Answer: Function when the tool is small and local. MCP when the tool is reusable. Agent-as-tool when tool is complex and we don't want to clutter main agent's context and just want the final answer of the tool.
   **Verdict: the "when" is right; the "cost" half is missing.** The question asks what each costs you:
   - Function tool: almost nothing, but it's locked inside this app and this language.
   - MCP: a separate process (more moving parts, a bit of latency), and _trust_. A third-party server's tool descriptions are a prompt written by a stranger (D13).
   - Agent-as-tool: a whole extra LLM loop (tokens, $, time). You pay that to get reasoning back instead of raw data.
     Strong extra point: the model can't tell a local tool from an MCP tool. It only sees a name and a description, so MCP changes where the code runs, not how the model uses it.
6. You added an SEC cross-check, and accuracy went from 86% to 88%. Did you ship it? Why not? [D16]
   Answer: 2% improvememnt could have been noise. We did not run A/B tests, so we did not pursue it further.
   **Verdict: noise is right, but your strongest arguments are missing.** We _did_ run an A/B: both configs on the full dev set. Make the case with numbers:
   - +2% is **one question**: 2 fixed, 1 broken, within run-to-run noise.
   - It cost **+46%** and added about 3 s per question.
   - The decisive point: numeric accuracy was **already 100%**. A cross-check on numbers had nothing left to fix. The failures were written answers.
     Lesson to say out loud: add a tool only where the agent is actually failing.
7. Two runs of the same config failed on different questions. What does that mean for how you compare configurations? [D15]
   Answer: Should run it many times and average the performance since it is non-deterministic.
   **Verdict: right, needs specifics.** Say how many and what you look at:
   - 2–3 runs per config (each run costs money, so not "many").
   - Look at the spread, not just the average. A gap smaller than the run-to-run spread is noise. Evidence: only 2 of 6 failures repeated across two identical runs.
   - Compare _per question_ (which ones flip), not only the total.
   - Only the LLM parts are noisy. Search is deterministic, so the retrieval eval needed one run.
     Now you have a live example: hybrid 95% → 88% across two runs, while vector stayed 93% → 93% with the same 3 failures (D25).

## Week 2: RAG, retrieval, multimodal, memory

_Added at the end of Week 2._

## Week 3: orchestration, workflows, approvals

_Added at the end of Week 3._

## Week 4: observability, cost, compaction, debugging

_Added at the end of Week 4._

## Week 5: evaluation, optimization, Responsible AI

_Added at the end of Week 5._
