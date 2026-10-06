"""The one place that builds model clients for FinSight.

Every agent gets its client from here, so endpoint, auth and model names
can't drift between agents. Setup gotchas are recorded in DECISIONS.md D2.
"""

import os
from pathlib import Path

from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv

# Deployments on atlas-foundry-hma96. Two tiers so we can later measure
# cost vs quality per role (week 4).
MAIN_MODEL = "gpt-5.4"  # reasoning + vision
CHEAP_MODEL = "gpt-5.4-nano"  # routing, extraction

# src/finsight/llm.py -> parents[3] is "Stack of Agents", where the shared .env lives.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


def get_client(model: str = MAIN_MODEL) -> OpenAIChatClient:
    load_dotenv(_ROOT_ENV)
    # No api_version: the Responses API uses Azure's versionless /openai/v1/ endpoint (D2).
    return OpenAIChatClient(
        model=model,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
