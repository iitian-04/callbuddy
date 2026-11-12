"""Planner: turns a free-text task into a CallBrief, using one Groq LLM request.

Concept: "structured output". We send the CallBrief JSON schema and ask Groq to reply
with JSON only. Pydantic then validates it. If validation fails (missing field, opening
line without "AI"...), we send the error back once and let the model fix its answer.
"""

import json
from datetime import date

from loguru import logger
from openai import OpenAI
from pydantic import ValidationError

from callbuddy.brief import CallBrief

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

PLANNER_PROMPT = """You plan phone calls that an AI voice assistant will make for a user.
Turn the user's task into a call brief. Reply with ONE JSON object matching this schema:
{schema}

Rules:
- Use only facts from the task. Never invent phone numbers, prices, or personal details.
- If the caller's name is not in the task, use "{default_name}".
- details_to_share: always include "name for the booking: <caller name>". Then what the
  other person needs to know (party size, date, the
  preferred option). Do NOT list the acceptable range there: the agent asks for the
  preferred option first and only uses the range to judge offers.
- acceptable_options: list exactly what may be accepted, including any allowed range
  of times or alternatives the task mentions. Be concrete (write times like "8:15 pm").
- must_not_do: always include "do not accept anything outside the acceptable options",
  "do not share details that are not listed", and "do not agree to pay anything".
- opening_line: one short sentence that says it is an AI assistant calling on behalf of
  the caller, then states the request. It is read aloud by a voice engine, so write
  numbers and times in words ("a table for four at eight pm"), never digits.
- Today is {today}.
"""


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def plan_call(
    task: str,
    *,
    api_key: str,
    model: str,
    default_name: str = "the user",
    client: OpenAI | None = None,
    max_attempts: int = 2,
) -> CallBrief:
    """Ask the LLM for a CallBrief for `task`. Raises ValueError if it can't produce a valid one."""
    client = client or _client(api_key)
    system = PLANNER_PROMPT.format(
        schema=json.dumps(CallBrief.model_json_schema()),
        default_name=default_name,
        today=date.today().strftime("%A %d %B %Y"),
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]

    last_error = ""
    for attempt in range(1, max_attempts + 1):
        reply = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        text = reply.choices[0].message.content or ""
        try:
            return CallBrief.model_validate_json(text)
        except ValidationError as e:
            last_error = str(e)
            logger.warning(f"Planner attempt {attempt} gave an invalid brief: {last_error}")
            # Self-correction: show the model its answer and the error, ask for a fix.
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That JSON is invalid: {last_error}\nReply with corrected JSON only."},
            ]
    raise ValueError(f"Planner could not produce a valid CallBrief: {last_error}")
