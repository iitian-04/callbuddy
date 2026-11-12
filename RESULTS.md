# CallBuddy Results

Only real numbers from real runs. Claude Code updates this after each phase.

| Metric | Value |
|---|---|
| Repo URL | |
| Demo video URL | |
| LLM / STT / TTS | Groq `openai/gpt-oss-120b` / Deepgram / Kokoro |
| Eval v1 (passed / 20) | |
| Eval v2 (passed / 20) | |
| Rule violations (v2) | |
| Avg response latency (s) | |
| p90 latency (s) | |
| Avg turns per call | |
| Real phone calls made | |
| Money spent ($) | 0 |

## Biggest failures and fixes
1.

## Resume bullet (fill in at the end)
Built CallBuddy, a real-time AI phone agent (Python, Pipecat, Twilio, tool-calling LLM) that plans
and completes calls for users; built an LLM-simulated caller eval (X/20 scenarios passed, 0 rule
violations) with ~Y s average response latency, at near-zero cost.

## Measurements
- Kokoro TTS (cloud dev container, 4-core x86 Linux, not the Mac): model files 325.5 MB + 28.2 MB voices;
  load 2.9 s; one 4.7 s sentence synthesized in 1.9 s; peak process memory 593 MB.
  So Kokoro does not fit Render's 512 MB free tier (Phase 7 uses Deepgram Aura in the cloud).

## Daily log
- 2026-11-06: Env checked on Mac (macOS 26.2, M4, 16 GB, uv 0.11.33, git 2.50.1). Research for Phase 7 done.
  Groq's llama-3.3-70b-versatile is shut down (16 Aug 2026), switched to openai/gpt-oss-120b.
- 2026-11-06: Phase 0 scaffold (uv project, Python 3.12, pinned pipecat-ai 1.15.0, .gitignore, .env.example,
  CI) and Phase 1 bot.py written. 8 unit tests pass. Server starts and serves /client. Not yet talked to
  with real keys.
- 2026-11-12: Phase 2 call brief: brief.py (CallBrief), planner.py (Groq JSON + 1 self-correction retry),
  call prompt from the brief, `bot.py --task`. 16 unit tests pass. Live: planner gave a valid brief for
  "Book a table for 4 at 8 pm Saturday, 7:30-9 ok" (window 7:30-9:00 pm); text role-play with Groq:
  accepted 8:15 pm, refused 10 pm, accepted 8 pm (3/3). Voice role-play still to do.
- 2026-11-12: Phase 2 voice role-plays (2 sessions, voice af_sky). Fixed: opening line repeated on
  interruption, digits read aloud badly, window revealed up front, booking name not given, STT time
  formats ("850", "8.15") misread. See notes/failures.md. Live text checks 6/6 (accept 8:15, 8:50,
  8 pm; refuse 10 pm; gives name). Session 2 TTFB avg: STT 0.61 s, LLM 0.40 s, Kokoro TTS 1.95 s
  (max 5.66 s). Bot process RSS after 2 calls: 656 MB.
- 2026-11-12: Direction change to a screen-aware work buddy, renamed "Call Buddy". S1 built: screen
  sharing (1 frame/s), newest frame attached as JPEG before each LLM call, vision model
  qwen/qwen3.8-27b on Groq, spoken AI + privacy disclaimer. 20 unit tests pass. Live: model read
  "ModuleNotFoundError: No module named 'pandas'" from a fake 1440x900 screenshot (2.5 s test).
- 2026-11-12: S1 real test with the /buddy page (HTTP screenshots): no freeze, no disconnect. 38 screenshots
  uploaded (1280x598, ~49 KB each), attached on every turn. It read a web dashboard correctly (totals, monthly
  amount) and converted an amount to rupees on request (rate from model knowledge, not live). TTFB avg:
  STT 0.64 s, LLM (qwen3.8-27b + image) 0.79 s (max 2.61), Kokoro 3.83 s (max 13.5). RSS 525 MB.
  Still to test: an error message on screen (S1 "done when").
