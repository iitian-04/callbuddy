"""Live text-mode role-play of the Phase 2 "Done when" check (no audio, real Groq calls).

The restaurant's lines are scripted. The agent replies using the system prompt built
from the CallBrief. A second LLM call judges whether the agent accepted the offer.
Run: uv run pytest -m live -s
"""

import json

import pytest

TASK = "Book a table for 4 at 8 pm Saturday, 7:30-9 ok"

SCENARIOS = [
    # (name, what the restaurant says, should the agent accept?)
    ("alternative 8:15", "Sorry, 8 is full. I can do 8:15 pm on Saturday for four, does that work?", True),
    ("only 10 pm", "We're fully booked until late. The only table for four on Saturday is at 10 pm.", False),
    ("easy yes", "Yes, 8 pm Saturday for four is available. Shall I book it?", True),
    # From the 2026-11-12 voice role-play: speech-to-text wrote times like this.
    ("stt 8.15", "8.15.", True),
    ("stt 850", "and if we get 850, is it possible?", True),
]


@pytest.mark.live
def test_agent_gives_caller_name(setup):
    client, model, brief = setup
    reply = agent_reply(client, model, brief, "What is the name?")
    print(f"\n[name] agent: {reply}")
    assert "Priyanshu" in reply


@pytest.fixture(scope="module")
def setup():
    from openai import OpenAI

    from callbuddy.config import load_settings
    from callbuddy.planner import GROQ_BASE_URL, plan_call

    s = load_settings()
    client = OpenAI(api_key=s.groq_api_key.get_secret_value(), base_url=GROQ_BASE_URL)
    brief = plan_call(TASK, api_key="", model=s.groq_model, default_name="Priyanshu", client=client)
    return client, s.groq_model, brief


def agent_reply(client, model, brief, restaurant_line: str) -> str:
    from callbuddy.prompts import build_call_prompt

    r = client.chat.completions.create(
        model=model,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": build_call_prompt(brief)},
            {"role": "assistant", "content": brief.opening_line},
            {"role": "user", "content": restaurant_line},
        ],
    )
    return r.choices[0].message.content or ""


def judge_accepted(client, model, restaurant_line: str, reply: str) -> bool:
    r = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": f'A restaurant said: "{restaurant_line}"\nThe caller replied: "{reply}"\n'
                'Did the caller accept the offered booking? Reply JSON: {"accepted": true|false}',
            }
        ],
    )
    return bool(json.loads(r.choices[0].message.content)["accepted"])


@pytest.mark.live
@pytest.mark.parametrize("name,line,should_accept", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_agent_follows_brief(setup, name, line, should_accept):
    client, model, brief = setup
    reply = agent_reply(client, model, brief, line)
    accepted = judge_accepted(client, model, line, reply)
    print(f"\n[{name}] restaurant: {line}\n[{name}] agent: {reply}\n[{name}] accepted={accepted}")
    assert accepted == should_accept
