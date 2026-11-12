"""Live: the main brain (gpt-oss) picks the right tool. No real Gmail or screen is touched."""

import json

import pytest

TODAY = "Thursday 12 November 2026"


def ask(messages, gmail=True):
    from openai import OpenAI

    from callbuddy.config import load_settings
    from callbuddy.gmail import TOOL_SPECS
    from callbuddy.prompts import build_screen_prompt
    from callbuddy.screen import LOOK_AT_SCREEN_SPEC

    s = load_settings()
    client = OpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    specs = [LOOK_AT_SCREEN_SPEC, *(TOOL_SPECS if gmail else [])]
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
              "parameters": {"type": "object", "properties": t["properties"], "required": t["required"]}}} for t in specs]
    r = client.chat.completions.create(
        model=s.groq_model, reasoning_effort=s.groq_reasoning_effort, tools=tools,
        messages=[{"role": "system", "content": build_screen_prompt(TODAY, gmail=gmail)}, *messages],
    )
    m = r.choices[0].message
    calls = [(t.function.name, json.loads(t.function.arguments or "{}")) for t in (m.tool_calls or [])]
    print(f"\ncalls={calls} text={m.content!r}")
    return calls, m.content


@pytest.mark.live
def test_searches_recent_mail_with_right_date():
    calls, _ = ask([{"role": "user", "content": "Did QUASA email me this week?"}])
    assert calls and calls[0][0] == "search_emails"
    q = calls[0][1].get("query", "")
    assert q and "2024" not in q and "2025" not in q


@pytest.mark.live
def test_asks_before_drafting():
    calls, _ = ask([{"role": "user", "content": "Draft a reply to news@quasa.io saying thanks, I'll read it tonight."}])
    assert "create_draft" not in [c[0] for c in calls]


@pytest.mark.live
@pytest.mark.parametrize("attempt", range(5))
def test_never_answers_about_unfetched_email(attempt):
    """Seen 2026-11-12: it invented 'FAME at Samsung, payment on August 26' without searching."""
    calls, _ = ask([
        {"role": "user", "content": "I want to know a recent email I received from fame."},
        {"role": "assistant", "content": "Got it, searching for that now."},
        {"role": "user", "content": "It was about a payment I made."},
    ])
    assert calls and calls[0][0] == "search_emails" and calls[0][1].get("query")


@pytest.mark.live
@pytest.mark.parametrize("utterance", ["What's this error on my screen?", "Summarize this page for me.",
                                       "Can you see what I'm looking at?"])
def test_screen_questions_use_look_at_screen(utterance):
    calls, _ = ask([{"role": "user", "content": utterance}])
    assert calls and calls[0][0] == "look_at_screen" and calls[0][1].get("question")
