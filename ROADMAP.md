# CallBuddy Roadmap (7–14 Nov 2026)

Rule for Claude Code: work only on the phase I name. Tick boxes `[x]` as items finish.

## Phase 0: Setup (6–7 Nov)
- [x] Python 3.11+, git, uv installed
- [ ] GitHub repo `callbuddy` created and cloned
- [ ] Deepgram + Groq accounts; keys in `.env` (added by me)
- [x] `.gitignore` includes `.env`, `transcripts/`, `results/`, recordings
- [ ] Headphones ready for testing

## Phase 1: Voice bot in the browser (7 Nov)
Goal: talk to a bot at http://localhost:7860/client.
- [ ] `bot.py`: Pipecat pipeline. SmallWebRTCTransport, Deepgram STT, Groq LLM
      (`openai/gpt-oss-120b`, set via `GROQ_MODEL` in .env), Kokoro TTS, Silero VAD
      Note: Groq's deprecations page lists `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`
      as shut down on 16 Aug 2026 (replacements: `openai/gpt-oss-120b` / `openai/gpt-oss-20b`).
      Confirm with one real request on day 1 before building on it.
- [ ] System prompt: friendly, replies under 2 sentences
- [ ] Interrupting the bot mid-sentence works
- [ ] I can explain every stage of bot.py
Done when: it answers out loud and stops when I interrupt.

## Phase 2: Call brief (8 Nov)
Goal: turn a text task into a plan the voice agent follows.
- [x] `planner.py` → `CallBrief` (Pydantic): goal, caller_name, details_to_share,
      acceptable_options, must_not_do, give_up_after, opening_line (says it's an AI)
- [x] Voice agent system prompt built from the CallBrief
- [x] CLI: `uv run python bot.py --task "..."`
- [x] Tests for planner with 3 example tasks
- [x] Role-played 3 calls (easy yes / alternative time / fully booked); failures in `notes/failures.md`
Done when: "book a table for 4 at 8 pm Sat, 7:30–9 ok" works; it accepts 8:15 and refuses 10 pm.

## Direction change (12 Nov 2026)
Call Buddy is now a voice **work buddy that sees your screen**. Read-only first, safe actions later.
End goal: an assistant that understands what you're working on and does tasks for you, with your OK.
The phone-call work (Phases 0–2) stays and returns in S5. Old phone-call Phases 3–7 are replaced below.

## S1: See and explain (12 Nov)
Goal: share your screen, talk, and Call Buddy answers about what's on it. No actions.
- [x] Rename to "Call Buddy" (spoken name, prompts, README)
- [x] Screen sharing via the /buddy page: browser sends one 1280 px JPEG every 2 s over HTTP
      (WebRTC screen video froze the bot, see notes/failures.md #6)
- [x] `callbuddy/screen.py`: keep newest screenshot in memory only, attach it (JPEG, max 1280 px)
      before each LLM call, older screenshots replaced by a note
- [x] Vision LLM on Groq free tier (`qwen/qwen3.8-27b`, `VISION_MODEL` in .env)
- [x] Greeting with AI + privacy disclaimer (screenshots go to Groq), spoken word for word
- [x] Unit tests for screen.py; live test: model reads an error from a fake screenshot
- [ ] Real test: share screen, ask about an error / an email / a web page (3 checks)
Done when: you share a screen with an error and it explains the error out loud.

## S2: Memory (session) (12 Nov)
- [x] Running notes of what you're working on (task, app/file, findings, next steps), rewritten every
      3 turns by a small model (`openai/gpt-oss-20b`) in the background, from chat text only
- [x] Old turns trimmed to the last 16 messages; the notes keep the gist (faster, cheaper requests)
- [x] Short summary when you disconnect, saved to `sessions/` (gitignored: may contain screen
      content, so not `notes/sessions/` as first planned); next session starts with it
- [x] Tests for the notes logic (unit + live)
- [ ] Real test: work for a few minutes, ask "what was I doing?", reconnect and ask again

## S3: Suggestions (still read-only)
- [ ] Notices changes on screen (new error, failed test, new message) and offers a hint
- [ ] Rate limit: at most one unprompted hint per minute; "be quiet" mutes it
- [ ] Tests for the change detector

## S4: Safe actions with your OK
- [ ] Small allow-list of tools: open URL, open app, draft text to clipboard, make a note
- [ ] Always asks "Should I do X?" and waits for a yes; nothing destructive, no passwords/payments
- [ ] Every tool has a pytest test

## S5: Phone calls for you
- [ ] Reuse the Phase 2 call planner; Twilio trial (my number + consenting friends only)
- [ ] Tools: check calendar, record outcome, end call; 3-line summary after the call
- [ ] Only call numbers I give explicitly for that run
