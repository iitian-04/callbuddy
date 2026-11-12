"""Live check: the notes model turns a short chat into useful notes (real Groq call)."""

import asyncio

import pytest

from callbuddy import memory as mem


@pytest.mark.live
def test_live_notes_update(tmp_path):
    from openai import AsyncOpenAI

    from callbuddy.config import load_settings

    s = load_settings()
    client = AsyncOpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    m = mem.SessionMemory(client, s.memory_model, sessions_dir=tmp_path)
    chat = [
        {"role": "user", "content": "I'm in VS Code, report.py won't run. What's this error?"},
        {"role": "assistant", "content": "It says no module named pandas. Run pip install pandas."},
        {"role": "user", "content": "Done, now it says KeyError 'revenue' on line 42."},
        {"role": "assistant", "content": "Your CSV has no 'revenue' column. The header says 'Revenue' with a capital R."},
    ]
    asyncio.run(m.update(chat))
    print("\n" + m.text())
    text = m.text().lower()
    assert "report.py" in text and "revenue" in text
