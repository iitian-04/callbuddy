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
- [ ] `planner.py` → `CallBrief` (Pydantic): goal, caller_name, details_to_share,
      acceptable_options, must_not_do, give_up_after, opening_line (says it's an AI)
- [ ] Voice agent system prompt built from the CallBrief
- [ ] CLI: `uv run python bot.py --task "..."`
- [ ] Tests for planner with 3 example tasks
- [ ] Role-played 3 calls (easy yes / alternative time / fully booked); failures in `notes/failures.md`
Done when: "book a table for 4 at 8 pm Sat, 7:30–9 ok" works; it accepts 8:15 and refuses 10 pm.

## Phase 3: Tools + summary (9–10 Nov)
- [ ] `check_calendar(date, time)` reads `data/calendar.json`
- [ ] `record_outcome(status, details)`, where status is booked | not_available | needs_followup | failed
- [ ] `end_call(reason)`: short goodbye, pipeline ends cleanly
- [ ] Transcripts saved to `transcripts/<timestamp>.json`, outcomes to `results/`
- [ ] `summary.py`: 3-line human summary after each call
- [ ] (Optional) summary sent to me via a free Telegram bot
- [ ] pytest tests for all tools
Done when: a role-played call produces a correct saved summary.

## Phase 4: Real phone calls (11 Nov)
- [ ] Twilio trial account; my number (+ consenting friends) verified (done by me in the console)
- [ ] cloudflared/ngrok tunnel for a public URL
- [ ] `server.py`: FastAPI websocket for Twilio Media Streams, reusing the pipeline
- [ ] `call.py`: outbound call to a number I pass explicitly
- [ ] `--mode browser | --mode phone` both work
- [ ] One good call recorded for the demo
Warning (Twilio trial docs, checked 6 Nov 2026): trial accounts block the `<Stream>` verb
(which Media Streams needs), allow calls only inside the sign-up country, give 75 minutes
over 30 days, and cap calls at 10 min. Check this in the console on 7 Nov, before Phase 4.
Fallback: if Twilio blocks me, demo in the browser and note phone as "in progress".

## Phase 5: Simulator eval (12 Nov)
- [ ] `eval/scenarios.yaml`: 20 scenarios (easy yes, fully booked, alt time, asks phone no.,
      rude/hurried, hangs up, "are you a robot?", upsell, wrong number, on hold, ...)
- [ ] `eval/simulator.py`: an LLM plays the other person in TEXT mode
- [ ] `eval/run_eval.py`: max 12 turns, retries/backoff for Groq rate limits
- [ ] `eval/judge.py`: JSON {task_success, rule_violation, disclosed_ai, politeness_1to5, notes}
- [ ] `eval/results.csv` + `eval/chart.png`
- [ ] v1 run → fix top 2 failure types → v2 run (both recorded in RESULTS.md)

## Phase 6: Polish + launch (13–14 Nov)
- [ ] Per-turn latency logging; avg + p90 printed
- [ ] README: pitch, demo video, architecture (mermaid), eval table + chart, latency, cost,
      5-command quickstart, safety rules
- [ ] Repo check: no secrets, no dead code, tests pass
- [ ] `notes/what-i-learned.md`: 5 failures and fixes
- [ ] 2-minute demo video recorded
- [ ] LinkedIn/X post; resume updated; repo pinned

## Phase 7: Deploy (14 Nov, after Phase 6)
Goal: a public link where a recruiter opens a page, clicks Connect and talks to CallBuddy
in the browser. The public demo never places phone calls.
Chosen host: Render free web service + Daily WebRTC transport (see notes/setup-plan.md, section 3).
- [ ] `--transport daily` option: same pipeline, DailyTransport instead of SmallWebRTC
      (Daily carries the audio, so the server needs no UDP ports and no TURN server)
- [ ] `TTS_PROVIDER=kokoro|deepgram`: Kokoro locally, Deepgram Aura in the cloud
      (Render free has 512 MB RAM; measure Kokoro locally first, only switch if it doesn't fit)
- [ ] `Dockerfile` + `render.yaml`; keys set in the Render dashboard, never in the repo
- [ ] Demo guardrails: access code, max 3 min per session, one session at a time,
      daily session cap, so strangers can't drain the Deepgram credit or Groq limits
- [ ] Landing page: what CallBuddy is, "it's an AI", "first load can take ~1 min (free host waking up)"
- [ ] `/health` endpoint; measure cold start and one-turn latency, write both in RESULTS.md
- [ ] Phone mode is NOT deployed: it runs only on my laptop + cloudflared during my own test calls
- [ ] Tested from a different network (phone on mobile data) and from Chrome + Safari
- [ ] README "Try it" link + 2-min video as the always-works backup
Fallback A: laptop + `cloudflared tunnel --url http://localhost:7860` for a live interview demo.
Fallback B: Oracle Cloud Always Free VM (more RAM/CPU, but signup needs a card for identity check).
Done when: a friend on another network opens the link, talks to the bot, and it answers.
