"""Week 1 · Step 3 📘: look inside. What is actually sent on each model call? (book 4.2, 4.12)"""

import asyncio

from agent_framework import Agent, ChatContext, chat_middleware

from finsight.llm import get_client
from finsight.tools.calculator import calculator


def describe(message) -> str:
    # A message is a role plus a list of typed contents (text, function_call, function_result).
    parts = []
    for c in message.contents:
        if c.type == "text":
            parts.append(f"text {c.text[:60]!r}")
        elif c.type == "function_call":
            parts.append(f"function_call {c.name}({c.arguments})")
        elif c.type == "function_result":
            parts.append(f"function_result {str(c.result)[:40]!r}")
        else:
            parts.append(c.type)
    return f"{message.role:<9} " + " | ".join(parts)


call_no = 0


# Chat middleware wraps EVERY model call, so we see exactly what goes over the wire.
@chat_middleware
async def peephole(context: ChatContext, call_next) -> None:
    global call_no
    call_no += 1
    print(f"\n── model call {call_no}: sending {len(context.messages)} message(s)")
    for m in context.messages:
        print("   ", describe(m))
    # Does Azure keep state for us? These options would point at a stored conversation.
    linked = {k: v for k, v in context.options.items() if k in ("conversation_id", "previous_response_id", "store")}
    print("    server-side link:", linked or "none")
    await call_next()
    usage = context.result.usage_details or {}
    print(f"    tokens: in={usage.get('input_token_count')} out={usage.get('output_token_count')}")


agent = Agent(
    client=get_client(),
    name="analyst",
    instructions="You are a concise financial analyst. Use the calculator for every arithmetic step.",
    tools=[calculator],
    middleware=[peephole],
)


async def main() -> None:
    response = await agent.run(
        "Revenue was $18,902.1M and net income was $2,413.7M. What is the net margin in percent? "
        "Then what would it be if net income were 10% higher?"
    )
    print("\n══ final response.messages (what the run produced):")
    for m in response.messages:
        print("   ", describe(m))


asyncio.run(main())
