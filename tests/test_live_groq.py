"""Live check: one real request to Groq with the model from .env.

Skipped by default (and in CI). Run on your machine with:  uv run pytest -m live
"""

import pytest

from callbuddy.config import load_settings


@pytest.mark.live
def test_groq_model_answers():
    from openai import OpenAI  # installed with pipecat-ai[groq]

    s = load_settings()
    client = OpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    reply = client.chat.completions.create(
        model=s.groq_model,
        messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
        max_completion_tokens=200,
    )
    text = reply.choices[0].message.content or ""
    print(f"model={s.groq_model} reply={text!r}")
    assert "pong" in text.lower()
