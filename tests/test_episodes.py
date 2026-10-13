"""Offline tests for episodic memory (D29). No model calls: the provider hooks are called directly."""

import asyncio

from agent_framework import Message, SessionContext

from finsight.memory.episodes import Episode, EpisodicMemory, InMemoryEpisodeStore, JsonEpisodeStore
from finsight.models import Answer


def _ep(company: str, q: str) -> Episode:
    return Episode(company=company, question=q, answer="a", pages=[1], saved_at="t")


def test_recent_is_per_company_and_capped():
    store = InMemoryEpisodeStore()
    for i in range(5):
        store.add(_ep("BOEING", f"q{i}"))
    store.add(_ep("CVSHEALTH", "other"))
    assert [e.question for e in store.recent("BOEING", 3)] == ["q2", "q3", "q4"]


def test_json_store_survives_a_new_instance(tmp_path):
    JsonEpisodeStore(tmp_path / "e.json").add(_ep("BOEING", "q"))
    assert len(JsonEpisodeStore(tmp_path / "e.json").recent("BOEING", 3)) == 1


def test_fresh_in_memory_store_is_empty():
    # Evals build a new one per run (D29), so earlier answers can't leak in.
    assert InMemoryEpisodeStore().recent("BOEING", 3) == []


def test_before_run_injects_same_company_episodes_only():
    store = InMemoryEpisodeStore()
    store.add(_ep("BOEING", "tax rate?"))
    store.add(_ep("CVSHEALTH", "capex?"))
    ctx = SessionContext(input_messages=[Message("user", ["Filing: BOEING_2022_10K\n\nQuestion: margin?"])])
    asyncio.run(EpisodicMemory(store).before_run(agent=None, session=None, context=ctx, state={}))
    injected = "\n".join(m.text for ms in ctx.context_messages.values() for m in ms)
    assert "tax rate?" in injected and "capex?" not in injected


def test_after_run_saves_the_typed_answer():
    store = InMemoryEpisodeStore()
    ctx = SessionContext(input_messages=[Message("user", ["Filing: BOEING_2022_10K\n\nQuestion: margin?"])])

    class FakeResponse:  # only .value is read
        value = Answer(reasoning="r", found=True, answer="10%", value=10, unit="%", citations=[5], confidence="high")

    ctx._response = FakeResponse()
    asyncio.run(EpisodicMemory(store).after_run(agent=None, session=None, context=ctx, state={"company": "BOEING"}))
    assert store.recent("BOEING", 3)[0].model_dump(exclude={"saved_at"}) == {
        "company": "BOEING", "question": "margin?", "answer": "10%", "pages": [5]}
