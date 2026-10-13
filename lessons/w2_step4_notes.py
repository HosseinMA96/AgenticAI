"""Week 2, Step 4 (lesson): memory-as-tool notes across two sessions (book 4.7, D28).

Session 1 answers a Boeing question and may save a note. Session 2 is a fresh
agent and session, so the only way it knows anything is by reading the notes.

Run: uv run python lessons/w2_step4_notes.py [--feedback]

--feedback: after session 1, send the grader's verdict and the gold answer into
the same session, as an outside signal the agent can't produce itself.
"""

import asyncio
import sys

from finsight.agents.analyst import build_analyst
from finsight.dataset import DATA
from finsight.memory.notes import JsonNotesStore, make_notes_tools
from finsight.models import Answer

# A separate file, so the lesson never touches the product's notes.
STORE = JsonNotesStore(DATA / "memory" / "lesson_notes.json")
DOC = "BOEING_2022_10K"


def show_calls(response) -> None:
    for m in response.messages:
        for c in m.contents:
            if c.type == "function_call":
                print(f"  🔧 {c.name}({c.arguments})")


FEEDBACK = (
    "Your answer was graded WRONG. Gold answer: 'Effective tax rate in FY2022 was 0.62%, "
    "compared to -14.76% in FY2021.' Work out why yours differs. If there is a durable lesson "
    "about this company's filings, save it with save_note."
)


async def session(n: int, question: str, feedback: bool = False) -> None:
    print(f"=== session {n}: {question}")
    agent = build_analyst(*make_notes_tools(STORE))  # new agent, nothing carried over
    chat = agent.create_session()  # history for the feedback turn (local, D27)
    response = await agent.run(f"Filing: {DOC}\n\nQuestion: {question}", session=chat,
                               options={"response_format": Answer})
    show_calls(response)
    print(f"  → {response.value.answer}\n")
    if feedback:
        print("  [grader feedback sent]")
        response = await agent.run(FEEDBACK, session=chat)
        show_calls(response)
        print(f"  → {response.text[:300]}\n")


async def main() -> None:
    STORE.path.unlink(missing_ok=True)  # start with no notes
    feedback = "--feedback" in sys.argv
    await session(1, "How does Boeing's effective tax rate in FY2022 compare to FY2021?", feedback)
    print("notes file now:", STORE.path.read_text() if STORE.path.exists() else "(empty)", "\n")
    # A different question: does the lesson transfer, not just the memorised answer?
    await session(2, "What was Boeing's effective tax rate in FY2021? Make sure you carefully read your notes and take into account")
    print("notes file now:", STORE.path.read_text() if STORE.path.exists() else "(empty)", "\n")


asyncio.run(main())
