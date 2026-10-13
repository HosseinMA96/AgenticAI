"""Offline tests for memory-as-tool notes. A temp file instead of data/."""

from finsight.memory.notes import JsonNotesStore, make_notes_tools


def test_save_then_read_across_store_instances(tmp_path):
    path = tmp_path / "notes.json"
    save, _ = make_notes_tools(JsonNotesStore(path))
    save.func("Boeing", "Tax note flips signs in loss years.")
    # A new store on the same file = a later session: the note survives.
    _, read = make_notes_tools(JsonNotesStore(path))
    assert "flips signs" in read.func("BOEING")  # company match ignores case


def test_notes_are_per_company(tmp_path):
    save, read = make_notes_tools(JsonNotesStore(tmp_path / "n.json"))
    save.func("Boeing", "a Boeing lesson")
    assert read.func("CVS Health") == "No notes for this company yet."
