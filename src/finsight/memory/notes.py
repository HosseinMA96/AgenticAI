"""Memory-as-tool: notes the agent chooses to save and read across sessions (book 4.7, D28).

On-demand memory: the model decides when to write and when to read. Compare the
episodic ContextProvider, where our code injects memories on every call.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Protocol

from agent_framework import FunctionTool, tool
from pydantic import BaseModel, Field

from finsight.dataset import DATA

NOTES_FILE = DATA / "memory" / "notes.json"


class Note(BaseModel):
    company: str
    text: str
    saved_at: str


class NotesStore(Protocol):
    """Where notes live. JSON file today; Cosmos DB when deployed (D28)."""

    def add(self, note: Note) -> None: ...
    def for_company(self, company: str) -> list[Note]: ...


class JsonNotesStore:
    def __init__(self, path: Path = NOTES_FILE):
        self.path = path

    def _load(self) -> list[Note]:
        if not self.path.exists():
            return []
        return [Note(**n) for n in json.loads(self.path.read_text())]

    def add(self, note: Note) -> None:
        notes = self._load() + [note]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([n.model_dump() for n in notes], indent=1))

    def for_company(self, company: str) -> list[Note]:
        # casefold so "Boeing" and "BOEING" are the same company.
        return [n for n in self._load() if n.company.casefold() == company.casefold()]


def make_notes_tools(store: NotesStore) -> list[FunctionTool]:
    """The two tools, bound to a store. The descriptions are the save policy: they're all the model sees."""

    def save_note(
        company: Annotated[str, Field(description="Company name, e.g. 'Boeing'.")],
        # Neutral example on purpose: an example naming a real quirk we test on leaks the answer.
        note: Annotated[str, Field(description="One sentence, e.g. 'Segment revenue is in the segment note, not in MD&A.'")],
    ) -> str:
        """Save a lesson about how this company's filings work, for future questions.
        When: after you have the answer, if something took extra searches or surprised you,
        e.g. a figure in an unexpected place, a sign or unit convention, or a definition that differs from the usual one.
        Save only durable lessons like these. Never save the answer to the current question."""
        store.add(Note(company=company, text=note, saved_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        return "saved"

    def read_notes(
        company: Annotated[str, Field(description="Company name, e.g. 'Boeing'.")],
    ) -> str:
        """Read lessons saved from earlier questions about this company. Call it before searching the filing."""
        notes = store.for_company(company)
        if not notes:
            return "No notes for this company yet."
        return "\n".join(f"- {n.text} (saved {n.saved_at})" for n in notes)

    return [tool(save_note), tool(read_notes)]
