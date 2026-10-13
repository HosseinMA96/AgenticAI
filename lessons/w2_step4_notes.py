"""Week 2, Step 4 (lesson): memory-as-tool notes across two sessions (book 4.7, D28).

Session 1 answers a Boeing question and may save a note. Session 2 is a fresh
agent and session, so the only way it knows anything is by reading the notes.

Run: uv run python lessons/w2_step4_notes.py
"""

import asyncio

from finsight.agents.analyst import ask, build_analyst
from finsight.dataset import DATA
from finsight.memory.notes import JsonNotesStore, make_notes_tools

# A separate file, so the lesson never touches the product's notes.
STORE = JsonNotesStore(DATA / "memory" / "lesson_notes.json")
DOC = "BOEING_2022_10K"


def show_calls(response) -> None:
    for m in response.messages:
        for c in m.contents:
            if c.type == "function_call":
                print(f"  🔧 {c.name}({c.arguments})")


async def session(n: int, question: str) -> None:
    print(f"=== session {n}: {question}")
    agent = build_analyst(*make_notes_tools(STORE))  # new agent, nothing carried over
    response = await ask(agent, DOC, question)
    show_calls(response)
    print(f"  → {response.value.answer}\n")


async def main() -> None:
    STORE.path.unlink(missing_ok=True)  # start with no notes
    await session(1, "How does Boeing's effective tax rate in FY2022 compare to FY2021?")
    print("notes file now:", STORE.path.read_text() if STORE.path.exists() else "(empty)", "\n")
    await session(2, "What was Boeing's income tax expense or benefit in FY2022?")


asyncio.run(main())
