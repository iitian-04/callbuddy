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

## Open: Kokoro "TTS context completed with no audio" errors
- Seen in every session (4-5 times per call; also right after the TTSSpeakFrame opening line). Non-fatal: speech continues. Cause not yet
  found; to investigate.
