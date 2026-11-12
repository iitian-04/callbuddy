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

## 4. Didn't give the booking name (Phase 2, voice role-play #2, 2026-11-12)
- Seen: restaurant asked "What is the name?"; agent said "I'm an AI assistant helping
  Priyanshu; I don't have a name to give."
- Cause: nothing told it the caller's name is the booking name.
- Fix: planner always puts "name for the booking: <caller>" in details_to_share; prompt says
  to give the caller's name when asked. Live test `test_agent_gives_caller_name` added.

## 5. Misread spoken times from speech-to-text (Phase 2, voice role-play #2, 2026-11-12)
- Seen: STT wrote "850" (8:50, inside the window) and the agent refused; STT wrote "8.15."
  and the agent said it would "check with Priyanshu" instead of accepting.
- Cause: the LLM didn't treat "850" / "8.15" as times.
- Fix: prompt explains these STT formats and says to accept times inside the acceptable
  outcomes, or ask to repeat if unclear. Live scenarios "stt 8.15" and "stt 850" added; both pass.

## 6. Bot went silent as soon as screen sharing started (S1, 2026-11-12)
- Seen: the moment the screen share started you could no longer hear the bot.
- Log: one Kokoro sentence took 31.9 s (normally ~2 s), then "SmallWebRTCOutputTransport timed
  out after 10.0s writing audio ... the peer has stopped reading", output marked unusable.
  Adding the screen track also renegotiated the WebRTC connection mid-call.
- Cause: the bot received the screen as WebRTC video and had to decode a full-resolution stream
  at up to 30 fps in Python. That starved the event loop for ~30 s, so audio output timed out.
- Fix: no WebRTC video at all. New page /buddy: the browser grabs the screen, shrinks one frame
  to a 1280 px JPEG every 2 s and POSTs it to /screen; the bot only keeps the newest one.
  Voice stays audio-only, so nothing renegotiates. Tests for the store and the routes added.

## 7. "Not able to see my screen": wrong share button (S1, 2026-11-12)
- Seen: user shared with the voice panel's own monitor icon; 0 screenshots reached the bot
  (log: trackStatus receiver 2 enabled, no POST /screen). Bot kept saying it can't see the screen.
- Cause: two share buttons on /buddy; the panel's one sends WebRTC video, which the bot now ignores.
- Fix: /buddy hides the panel's screen-share and camera buttons, so only the working button is
  left; the bot now tells you to click the blue "Share screen" button at the top.

## 8. Questions went unanswered, answers took up to 11 s (S1/S2, 2026-11-12)
- Seen: "What is your point of view on this?" never got an answer; one reply took 11.3 s.
- Log: each time the user added a short phrase ("So,", "Thank you", "I think so") the pending
  reply was cancelled ("broadcasting interruption" 0.1-2 s after the LLM request).
  Groq headers: qwen free tier = 8,000 tokens/minute; a screenshot is ~800-1,500 tokens and we
  attached one to every turn, so Groq made us wait (benchmark: 8.6-19 s with an image).
- Fix: no screenshot for replies of 3 words or fewer; screenshots 1024 px instead of 1280;
  while the bot speaks you need 3+ words to interrupt (MinWordsUserTurnStartStrategy).

## 9. Gmail: invented an email, went silent, slow (S3, 2026-11-12)
- Seen: "That email was from FAME at Samsung, about a payment on August 26" with NO search behind
  it (only 3 tool calls all session); 3x the bot went silent; LLM replies avg 3.6 s, max 20 s.
- Causes: (1) the model answered from imagination; (2) it sometimes sent a tool call with an
  empty argument and Groq rejected the whole reply ("missing properties: 'query'"); (3) every model
  on Groq free tier = 8,000 tokens/min, and prompt + notes + 16 messages + tool results were big;
  (4) speech-to-text misheard the name ("fan", "famine" for FAME).
- Fixes: prompt rule "never describe an email you haven't fetched", broader retry search, spelled
  letters joined; no "required" fields in tool schemas (checked in code, model gets a hint);
  temperature 0.3 (live: 10/10 searched, was 4/5 with one junk reply); snippets 120 chars,
  context 10 messages, previous-session summary capped at 400 chars.

## 10. Gmail still slow and answers lost (S3, 2026-11-12, second test)
- Seen: after "latest email about payment" the search ran (5 results) but no answer was ever spoken;
  LLM avg 4.3 s, max 15.6 s.
- Log: the vision model (qwen) sent broken tool calls (`{}`, `{'param-value': ...}`), so one question
  cost 3-4 requests of ~1,500-2,200 tokens each: over the 8,000 tokens/min free limit. A "." noise
  transcription and "Hello" counted as new turns and cancelled the pending answer.
- Fix (new design, "vision as a tool"): main brain is gpt-oss-120b (clean tool calls in tests:
  10/10 searched, 6/6 used look_at_screen for screen questions). The screen is only sent to the
  vision model when needed, via look_at_screen(question). Tools keep running if you interrupt
  (cancel_on_interruption=False). NoiseFilter drops transcriptions with no words.

## Open: Kokoro "TTS context completed with no audio" errors (0 in the last session)
- Seen in every session (4-5 times per call; also right after the TTSSpeakFrame opening line). Non-fatal: speech continues. Cause not yet
  found; to investigate.
