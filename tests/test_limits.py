"""Offline tests for the tool-call-cap flag (D5). Hand-built responses, no model."""

from agent_framework import AgentResponse, Content, Message

from finsight.limits import count_tool_calls, limit_hit


def make_response(n_calls: int) -> AgentResponse:
    # Mimics a real run: user question, then call/result pairs, then the answer.
    messages = [Message("user", ["What is the growth rate?"])]
    for i in range(n_calls):
        messages.append(Message("assistant", [Content.from_function_call(f"c{i}", "calculator", arguments="1+1")]))
        messages.append(Message("tool", [Content.from_function_result(f"c{i}", result="2")]))
    messages.append(Message("assistant", ["The answer is 2."]))
    return AgentResponse(messages=messages)


def test_counts_only_function_calls():
    assert count_tool_calls(make_response(3)) == 3


def test_no_tools_no_flag():
    assert not limit_hit(make_response(0), max_calls=2)


def test_under_cap_no_flag():
    assert not limit_hit(make_response(1), max_calls=2)


def test_reaching_cap_flags():
    assert limit_hit(make_response(2), max_calls=2)
