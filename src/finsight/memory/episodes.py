"""Episodic memory: past Q→A episodes injected automatically by a ContextProvider (book 4.7, D29).

Automatic memory: our code reads and writes on every run; the model never chooses.
Compare notes.py, where the model decides when to call read_notes.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from agent_framework import ContextProvider, Message
from pydantic import BaseModel

from finsight.dataset import DATA

EPISODES_FILE = DATA / "memory" / "episodes.json"
_FILING = re.compile(r"Filing: (\S+)")  # the first line ask() sends
_QUESTION = re.compile(r"Question: (.+)", re.S)


class Episode(BaseModel):
    company: str
    question: str
    answer: str
    pages: list[int]
    saved_at: str


class EpisodeStore(Protocol):
    def add(self, episode: Episode) -> None: ...
    def recent(self, company: str, n: int) -> list[Episode]: ...


class InMemoryEpisodeStore:
    """Lives only as long as the process. Evals use a fresh one, so every run starts empty (D29)."""

    def __init__(self) -> None:
        self.episodes: list[Episode] = []

    def add(self, episode: Episode) -> None:
        self.episodes.append(episode)

    def recent(self, company: str, n: int) -> list[Episode]:
        return [e for e in self.episodes if e.company == company][-n:]


class JsonEpisodeStore(InMemoryEpisodeStore):
    """Same, but loaded from and saved to a file, so episodes survive between runs."""

    def __init__(self, path: Path = EPISODES_FILE) -> None:
        self.path = path
        self.episodes = [Episode(**e) for e in json.loads(path.read_text())] if path.exists() else []

    def add(self, episode: Episode) -> None:
        super().add(episode)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([e.model_dump() for e in self.episodes], indent=1))


def company_of(doc_name: str) -> str:
    return doc_name.split("_")[0]  # BOEING_2022_10K -> BOEING


class EpisodicMemory(ContextProvider):
    def __init__(self, store: EpisodeStore, n: int = 3) -> None:
        super().__init__(source_id="episodic_memory")
        self.store, self.n = store, n

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        text = "\n".join(m.text for m in context.input_messages)
        if not (m := _FILING.search(text)):
            return
        state["company"] = company = company_of(m.group(1))  # after_run reads it back
        episodes = self.store.recent(company, self.n)
        if episodes:
            lines = "\n".join(f"- Q: {e.question}\n  A: {e.answer} (pages {e.pages})" for e in episodes)
            # Injected as a message, so it shows up when we print what the model saw.
            context.extend_messages(self, [Message("user", [f"Earlier questions about {company} (from memory):\n{lines}"])])

    async def after_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        company = state.get("company")
        response = context.response
        question = _QUESTION.search("\n".join(m.text for m in context.input_messages))
        try:
            answer = response.value  # the typed Answer when run with response_format
        except Exception:
            answer = None
        if not (company and question and answer is not None and hasattr(answer, "citations")):
            return  # follow-up turns (e.g. feedback) aren't episodes
        self.store.add(Episode(
            company=company, question=question.group(1).strip(), answer=answer.answer,
            pages=answer.citations, saved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ))
