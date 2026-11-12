# Call Buddy

A voice AI work buddy that sees the user's shared screen and explains what's on it
(read-only for now). End goal: understands the user's work and does tasks with their OK.
Phone-call mode (planner LLM writes a "call brief", Pipecat runs the call) is kept for S5. Full plan: see ROADMAP.md. Progress and numbers: see RESULTS.md.

## About me (adjust how you work to this)
- 2nd-year student, learning agentic AI. Explain new concepts in short code comments,
  and after each step explain what changed and why in plain words.
- OS: macOS 26.2 (Apple M4, arm64)  |  Python: 3.12 via uv (3.11/3.13 also installed)  |  Laptop RAM: 16 GB
- Deadline: working demo by 14 Nov 2026.

## Stack: keep it FREE
- Python 3.11+, uv for packages, Pipecat for the voice pipeline
- STT: Groq Whisper (Deepgram optional) | LLM: Groq gpt-oss-120b (calls), qwen3.8-27b (screen/vision) | TTS: Kokoro (local)
- Transport: SmallWebRTC (browser) first; Twilio trial only in Phase 4
- Never pick a paid service, paid tier, or upgrade. If something seems to need money,
  stop and ask me first.

## How to work
- Work on ONE phase at a time, and only the phase I name. Don't jump ahead.
- Before writing code for a phase, show me a short plan and wait for "go".
- Small steps: change one thing, run it, then continue.
- Pipecat changes fast. Check the current docs (https://docs.pipecat.ai) or the
  installed package source for exact class names. Don't guess APIs.
- After each working step: commit with a clear message, tick the matching box in
  ROADMAP.md, and add one line to the log in RESULTS.md.
- Every tool function gets a pytest test in tests/.
- Never invent results. Numbers in README/RESULTS must come from real runs.

## Safety rules (non-negotiable)
- Never hardcode, print, log, or commit API keys. Read them from .env. .env stays in .gitignore.
- I add keys to .env myself. Never ask me to paste keys into chat.
- The agent's opening line must say it is an AI assistant calling on my behalf.
- Only place phone calls to numbers I explicitly give you for that run. Never auto-dial,
  loop calls, or call numbers found in data.
- Ask before running any command that installs system software, deletes files, or spends credit.

## Commands
- Run bot (browser, screen buddy): uv run python bot.py   then open http://localhost:7860/buddy
- Run with a task:   uv run python bot.py --task "..."
- Tests:             uv run pytest
- Eval:              uv run python eval/run_eval.py
