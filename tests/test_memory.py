"""Memory tests: offline, with a fake async LLM client."""

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from callbuddy import memory as mem


class FakeAsyncClient:
    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        msg = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def chat(n: int) -> list[dict]:
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"question {i}"})
        out.append({"role": "assistant", "content": f"answer {i}"})
    return out


def test_message_text_skips_images():
    m = {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "x"}}]}
    assert mem.message_text(m) == "hi"


def test_transcript_ignores_notes_and_system():
    msgs = [{"role": "system", "content": "secret rules"}, *chat(2)]
    msgs.insert(1, {"role": "user", "content": mem.NOTES_MARKER + " old"})
    text = mem.transcript(msgs)
    assert "secret rules" not in text and "old" not in text
    assert text.splitlines()[0] == "User: question 0"


def test_apply_memory_trims_and_puts_notes_first():
    out = mem.apply_memory(chat(20), "NOTES", keep_last=6)
    assert out[0] == {"role": "system", "content": "NOTES"}
    assert len(out) <= 7 and out[1]["role"] == "user"
    assert out[-1]["content"] == "answer 19"


def test_apply_memory_replaces_old_notes():
    first = mem.apply_memory(chat(1), mem.NOTES_MARKER + " v1")
    second = mem.apply_memory(first, mem.NOTES_MARKER + " v2")
    notes = [m for m in second if mem.message_text(m).startswith(mem.NOTES_MARKER)]
    assert len(notes) == 1 and notes[0]["content"].endswith("v2")


def test_parse_notes_and_bad_json():
    task, notes = mem.parse_notes(json.dumps({"task": "fix bug", "notes": ["a", "", "b"] + ["x"] * 20}))
    assert task == "fix bug" and notes[:2] == ["a", "b"] and len(notes) == mem.MAX_NOTES
    try:
        mem.parse_notes("not json")
        raise AssertionError("should fail")
    except ValueError:
        pass


def test_update_every_few_turns_in_background(tmp_path):
    reply = json.dumps({"task": "fix pandas import", "notes": ["error in report.py"]})
    client = FakeAsyncClient(reply)
    m = mem.SessionMemory(client, "m", sessions_dir=tmp_path)

    async def run():
        for _ in range(mem.UPDATE_EVERY_TURNS):
            m.maybe_update_in_background(chat(2))
        await m._updating

    asyncio.run(run())
    assert len(client.requests) == 1  # only on the Nth turn
    assert m.task == "fix pandas import"
    assert "error in report.py" in m.text()


def test_failed_update_keeps_old_notes(tmp_path):
    m = mem.SessionMemory(FakeAsyncClient("garbage"), "m", sessions_dir=tmp_path)
    m.task, m.notes = "old task", ["old note"]
    asyncio.run(m.update(chat(1)))
    assert m.task == "old task" and m.notes == ["old note"]


def test_finish_saves_summary_and_next_session_loads_it(tmp_path):
    m = mem.SessionMemory(FakeAsyncClient("Worked on report.py.\nFixed the pandas import."), "m", sessions_dir=tmp_path)
    path = asyncio.run(m.finish(chat(2)))
    assert path is not None and path.parent == tmp_path
    nxt = mem.SessionMemory(FakeAsyncClient(), "m", sessions_dir=tmp_path)
    assert "pandas import" in nxt.last_session
    assert "previous session" in nxt.text()


def test_finish_with_empty_chat_saves_nothing(tmp_path):
    m = mem.SessionMemory(FakeAsyncClient(), "m", sessions_dir=tmp_path)
    assert asyncio.run(m.finish([])) is None
    assert list(tmp_path.iterdir()) == []


def test_latest_summary_picks_newest(tmp_path):
    mem.save_summary("old", tmp_path, now=datetime(2026, 11, 1))
    mem.save_summary("new", tmp_path, now=datetime(2026, 11, 12))
    assert mem.latest_summary(tmp_path) == "new"
