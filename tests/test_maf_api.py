"""Tripwire for MAF API drift. Offline: builds a client with a fake key, never calls it.

MAF moves fast (CLAUDE.md "API caution"). If an upgrade renames something we
rely on, this fails loudly here instead of silently somewhere else.
"""

import inspect

from agent_framework import Agent, AgentResponse, ChatContext, Content, Message, chat_middleware, tool
from agent_framework.openai import OpenAIChatClient


def test_names_we_import_exist():
    assert all([Agent, AgentResponse, ChatContext, Content, Message, chat_middleware, tool])


def test_client_takes_azure_args_and_has_loop_limits():
    client = OpenAIChatClient(model="m", azure_endpoint="https://x.openai.azure.com", api_key="x")
    # llm.py writes these keys (D5). A rename would otherwise be ignored silently.
    assert {"max_iterations", "max_function_calls", "max_duration_seconds"} <= set(
        client.function_invocation_configuration
    )


def test_structured_output_surface():
    # Structured output is agent.run(..., options={"response_format": Model}) -> response.value.
    assert "options" in inspect.signature(Agent.run).parameters
    assert isinstance(inspect.getattr_static(AgentResponse, "value"), property)


def test_function_content_helpers():
    assert callable(Content.from_function_call) and callable(Content.from_function_result)
