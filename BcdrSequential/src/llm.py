"""Shared Azure OpenAI chat client, per the parent `Stack of Agents/CLAUDE.md`
convention: one shared root `.env`, loaded via relative path.

Decision (Phase 6, discussed before coding): the project's own CLAUDE.md
originally called for `az login`/`DefaultAzureCredential` over committed
keys, but the actual shared `.env` this project must reuse already has a
static `AZURE_OPENAI_API_KEY`, and every sibling experiment
(`Dummy/Pre6/dummy*.py`) authenticates with it directly. Matching that
established convention rather than fighting it — `OpenAIChatClient` also
accepts `credential=` for `DefaultAzureCredential` if that ever needs to
change, so this is a localized swap if the shared `.env` moves to AAD auth.
"""

import os
from pathlib import Path

from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv

# BcdrSequential/src/llm.py -> BcdrSequential -> Stack of Agents/.env
_STACK_OF_AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent
_ROOT_ENV = _STACK_OF_AGENTS_ROOT / ".env"

DEFAULT_DEPLOYMENT = "gpt-4.1-mini"  # same deployment proven working in Dummy/Pre6/dummy1.py

_env_loaded = False


def _ensure_env_loaded() -> None:
    global _env_loaded
    if not _env_loaded:
        load_dotenv(dotenv_path=_ROOT_ENV)
        _env_loaded = True


def get_chat_client() -> OpenAIChatClient:
    _ensure_env_loaded()
    return OpenAIChatClient(
        model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", DEFAULT_DEPLOYMENT),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
