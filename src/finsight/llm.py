"""The one place that builds model clients for FinSight.

Every agent gets its client from here, so endpoint, auth and model names
can't drift between agents. Setup gotchas are recorded in DECISIONS.md D2.
"""

import os
from pathlib import Path

from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv

from finsight.config import (
    MAIN_MODEL,
    MAX_DURATION_SECONDS,
    MAX_FUNCTION_CALLS,
    MAX_ITERATIONS,
)

# src/finsight/llm.py -> parents[3] is "Stack of Agents", where the shared .env lives.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


def get_client(model: str = MAIN_MODEL) -> OpenAIChatClient:
    load_dotenv(_ROOT_ENV)
    # No api_version: the Responses API uses Azure's versionless /openai/v1/ endpoint (D2).
    client = OpenAIChatClient(
        model=model,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    # Explicit loop limits, so we never rely on MAF's silent defaults (D5).
    # All are best-effort: MAF checks them after each batch of tool calls.
    cfg = client.function_invocation_configuration
    cfg["max_iterations"] = MAX_ITERATIONS
    cfg["max_function_calls"] = MAX_FUNCTION_CALLS
    cfg["max_duration_seconds"] = MAX_DURATION_SECONDS
    return client
