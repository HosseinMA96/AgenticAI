"""Week 2, Step 5 (lesson): episodic memory injected by a ContextProvider (book 4.7, D29).

Two fresh agents, one after the other. Neither has a notes tool: our provider
saves each Q→A after the run and injects same-company episodes before the next.

Run: uv run python lessons/w2_step5_episodes.py
"""

import asyncio

from finsight.agents.analyst import ask, build_analyst
from finsight.dataset import DATA
from finsight.memory.episodes import JsonEpisodeStore

PATH = DATA / "memory" / "lesson_episodes.json"  # never the product's file
DOC = "BOEING_2022_10K"


async def run(n: int, question: str) -> None:
    store = JsonEpisodeStore(PATH)  # re-read from disk: a "later" process
    print(f"=== session {n}: {question}")
    print(f"  memory has {len(store.recent('BOEING', 3))} Boeing episode(s) to inject")
    response = await ask(build_analyst(memory=store), DOC, question)
    for m in response.messages:
        for c in m.contents:
            if c.type == "function_call":
                print(f"  🔧 {c.name}({c.arguments})")
    print(f"  → {response.value.answer}  (input tokens: {response.usage_details.get('input_token_count')})\n")


async def main() -> None:
    PATH.unlink(missing_ok=True)  # start empty
    await run(1, "What was Boeing's effective tax rate in FY2022?")
    await run(2, "How does Boeing's FY2022 effective tax rate compare to FY2021?")
    print("episodes file:\n", PATH.read_text())


asyncio.run(main())
