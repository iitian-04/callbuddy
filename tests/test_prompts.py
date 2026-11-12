from callbuddy.prompts import GREETING_INSTRUCTION, SYSTEM_PROMPT


def test_system_prompt_keeps_replies_short():
    assert "under 2 sentences" in SYSTEM_PROMPT


def test_greeting_discloses_ai():
    # Safety rule: the bot must say it is an AI.
    assert "AI" in GREETING_INSTRUCTION
