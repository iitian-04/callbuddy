# Failures and fixes

Real failures seen while testing, with the fix. Newest last.

## 1. Opening line repeated on every interruption (Phase 2, voice role-play, 2026-11-12)
- Seen: the bot said "Hello, this is an AI assistant calling on behalf of Priyanshu..." three
  times, and never answered "What is the name?".
- Cause: the opening was a developer message "Say exactly this: ...". It stayed in the LLM
  context, so after each interruption the LLM obeyed it again instead of answering.
- Fix: speak the opening line with `TTSSpeakFrame` (no LLM call). It is added to the context
  as the bot's own turn, so there is no instruction left to re-obey.

## 2. Times read aloud as "nine zero zero pm" (Phase 2, voice role-play, 2026-11-12)
- Seen: the restaurant (me) heard "00 PM" and got confused.
- Cause: the LLM wrote "9:00 pm" and Kokoro reads the digits literally.
- Fix: prompts now say to write numbers and times in words ("nine pm", "eight fifteen pm").

## 3. Agent revealed the whole acceptable window up front (Phase 2, text role-play, 2026-11-12)
- Seen: the brief put "Acceptable window: 7:30 pm to 9:00 pm" in details_to_share, so the
  agent asked for "any time between 7:30 and 9" instead of the preferred 8 pm.
- Fix: planner rule: details_to_share holds the preferred option only; the range is used
  only to judge offers.

## Open: Kokoro "TTS context completed with no audio" errors
- Seen in every session (4-5 times per call). Non-fatal: speech continues. Cause not yet
  found; to investigate.
