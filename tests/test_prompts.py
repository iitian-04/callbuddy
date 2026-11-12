from callbuddy.prompts import GREETING, SYSTEM_PROMPT, split_sentences


def test_system_prompt_names_call_buddy_and_stays_read_only():
    assert "Call Buddy" in SYSTEM_PROMPT
    assert "cannot click" in SYSTEM_PROMPT


def test_greeting_discloses_ai_and_privacy():
    # Safety rules: say it is an AI, and warn that screenshots go to a cloud service.
    assert "AI" in GREETING
    assert "Groq" in GREETING and "private" in GREETING


def test_split_sentences_for_faster_first_audio():
    assert split_sentences("Hi, I'm Call Buddy. Ready? Go!") == ["Hi, I'm Call Buddy.", "Ready?", "Go!"]
    assert split_sentences(GREETING)[0] == "Hi, I'm Call Buddy, an AI assistant."
