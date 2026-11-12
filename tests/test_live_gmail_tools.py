"""Live: with the Gmail prompt and tool specs (no real Gmail), the model picks the right tool."""

import json

import pytest


@pytest.mark.live
def test_model_searches_recent_mail_and_asks_before_drafting():
    from openai import OpenAI

    from callbuddy.config import load_settings
    from callbuddy.gmail import TOOL_SPECS
    from callbuddy.prompts import build_screen_prompt

    s = load_settings()
    client = OpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
              "parameters": {"type": "object", "properties": t["properties"], "required": t["required"]}}} for t in TOOL_SPECS]
    system = build_screen_prompt("Thursday 12 November 2026", gmail=True)

    def ask(messages):
        r = client.chat.completions.create(model=s.vision_model, reasoning_effort=s.vision_reasoning_effort,
                                           tools=tools, messages=[{"role": "system", "content": system}, *messages])
        return r.choices[0].message

    m = ask([{"role": "user", "content": "Did QUASA email me this week?"}])
    assert m.tool_calls and m.tool_calls[0].function.name == "search_emails"
    q = json.loads(m.tool_calls[0].function.arguments)["query"]
    print(f"\nsearch query: {q}")
    assert "2024" not in q and "2025" not in q  # knows today's date / uses relative search

    m = ask([{"role": "user", "content": "Draft a reply to news@quasa.io saying thanks, I'll read it tonight."}])
    called = [t.function.name for t in (m.tool_calls or [])]
    print(f"draft turn: tools={called} text={m.content!r}")
    assert "create_draft" not in called  # must read it back and ask first
