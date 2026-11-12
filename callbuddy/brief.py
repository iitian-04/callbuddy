"""The CallBrief: a structured plan for one phone call.

Concept: instead of giving the voice agent a vague task ("book a table"), a planner LLM
first turns the task into this typed object. The voice agent's system prompt is then
built from it, so the rules (what's OK, what's not, when to give up) are explicit.
Pydantic validates the planner's JSON, so a malformed plan fails loudly, not mid-call.
"""

from pydantic import BaseModel, Field, field_validator


class CallBrief(BaseModel):
    goal: str = Field(description="One sentence: what a successful call achieves.")
    caller_name: str = Field(description="Name of the person the AI is calling for.")
    details_to_share: list[str] = Field(
        default_factory=list,
        description="Facts the agent may tell the other person (party size, date, name...).",
    )
    acceptable_options: list[str] = Field(
        default_factory=list,
        description="Outcomes the agent may accept, including allowed alternatives "
        "(e.g. 'any time from 7:30 pm to 9:00 pm on Saturday').",
    )
    must_not_do: list[str] = Field(
        default_factory=list,
        description="Hard limits (e.g. 'do not accept times after 9 pm', 'do not pay').",
    )
    give_up_after: str = Field(
        description="When to stop trying and end politely (e.g. 'if no time in the window is free').",
    )
    opening_line: str = Field(
        description="First sentence of the call. Must say it is an AI assistant calling for the caller.",
    )

    @field_validator("opening_line")
    @classmethod
    def opening_line_discloses_ai(cls, v: str) -> str:
        # Safety rule from CLAUDE.md: the agent must always say it is an AI.
        if "AI" not in v:
            raise ValueError("opening_line must say it is an AI assistant")
        return v
