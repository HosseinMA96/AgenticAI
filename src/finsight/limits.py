"""Detect when a run stopped because it hit the tool-call cap (D5).

MAF's only signal is a logger.info line: it forces a text answer and returns
a response that looks complete. So we count the tool calls ourselves.
"""

from agent_framework import AgentResponse

from finsight.config import MAX_FUNCTION_CALLS


def count_tool_calls(response: AgentResponse) -> int:
    # Same message list we printed in Step 3: each tool run is one function_call content.
    return sum(c.type == "function_call" for m in response.messages for c in m.contents)


def limit_hit(response: AgentResponse, max_calls: int = MAX_FUNCTION_CALLS) -> bool:
    # ">=" because MAF stops once the total reaches the cap. Reaching it doesn't
    # prove more calls were needed, so this may raise false alarms (D5).
    return count_tool_calls(response) >= max_calls
