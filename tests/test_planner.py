"""Planner tests. Unit tests use a fake LLM client (free, offline, run in CI).
The live test at the bottom calls Groq for real: uv run pytest -m live
"""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from callbuddy.brief import CallBrief
from callbuddy.planner import plan_call
from callbuddy.prompts import build_call_prompt


class FakeClient:
    """Pretends to be OpenAI(): returns the queued replies in order and records requests."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        msg = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def brief_json(**overrides) -> str:
    data = {
        "goal": "Book a table",
        "caller_name": "Priyanshu",
        "details_to_share": ["party of 4"],
        "acceptable_options": ["Saturday 7:30 pm to 9:00 pm"],
        "must_not_do": ["do not accept anything outside the acceptable options"],
        "give_up_after": "no time in the window is free",
        "opening_line": "Hi, I'm an AI assistant calling on behalf of Priyanshu.",
    }
    data.update(overrides)
    return json.dumps(data)


# Three example tasks (ROADMAP Phase 2). The fake LLM returns a plausible brief for each;
# we check the planner sends the task, parses the reply, and keeps the AI disclosure.
EXAMPLES = [
    (
        "Book a table for 4 at 8 pm Saturday, 7:30-9 ok",
        brief_json(acceptable_options=["Saturday, any time from 7:30 pm to 9:00 pm"]),
    ),
    (
        "Book a haircut for Priyanshu tomorrow at 5 pm, 4-6 pm ok, under 500 rupees",
        brief_json(goal="Book a haircut", acceptable_options=["tomorrow 4 pm to 6 pm"]),
    ),
    (
        "Ask the dentist to move my Monday 10 am appointment to Tuesday morning",
        brief_json(goal="Reschedule dentist appointment", acceptable_options=["Tuesday before 12 pm"]),
    ),
]


@pytest.mark.parametrize("task,reply", EXAMPLES)
def test_plan_call_parses_brief(task, reply):
    client = FakeClient(reply)
    brief = plan_call(task, api_key="x", model="m", client=client)
    assert isinstance(brief, CallBrief)
    assert "AI" in brief.opening_line
    sent = client.requests[0]
    assert sent["messages"][-1] == {"role": "user", "content": task}
    assert sent["response_format"] == {"type": "json_object"}


def test_planner_retries_once_on_invalid_json():
    bad = brief_json(opening_line="Hi, I'm calling for Priyanshu.")  # no AI disclosure
    client = FakeClient(bad, brief_json())
    brief = plan_call("Book a table", api_key="x", model="m", client=client)
    assert "AI" in brief.opening_line
    assert len(client.requests) == 2
    # The second request shows the model its mistake.
    assert "invalid" in client.requests[1]["messages"][-1]["content"]


def test_planner_gives_up_after_max_attempts():
    client = FakeClient("not json", "still not json")
    with pytest.raises(ValueError, match="could not produce"):
        plan_call("Book a table", api_key="x", model="m", client=client)


def test_brief_requires_ai_disclosure():
    with pytest.raises(ValidationError, match="AI"):
        CallBrief.model_validate_json(brief_json(opening_line="Hello, calling for Priyanshu."))


def test_call_prompt_contains_the_rules():
    brief = CallBrief.model_validate_json(brief_json())
    prompt = build_call_prompt(brief)
    for text in ["Priyanshu", "Book a table", "party of 4", "7:30 pm to 9:00 pm", "no time in the window"]:
        assert text in prompt
    assert "never digits" in prompt


@pytest.mark.live
def test_live_planner_book_table():
    from callbuddy.config import load_settings

    s = load_settings()
    brief = plan_call(
        "Book a table for 4 at 8 pm Saturday, 7:30-9 ok",
        api_key=s.groq_api_key.get_secret_value(),
        model=s.groq_model,
    )
    print(brief.model_dump_json(indent=2))
    assert "AI" in brief.opening_line
    options = " ".join(brief.acceptable_options).lower()
    # Times may be digits or words ("seven thirty pm"), since the prompt asks for spoken style.
    assert ("7:30" in options or "seven thirty" in options) and ("9" in options or "nine" in options)
