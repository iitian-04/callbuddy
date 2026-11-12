# CallBuddy

An AI agent that makes phone calls for you: you type a task, a planner LLM writes a call brief,
a Pipecat voice pipeline runs the call, and you get a summary back.

> Work in progress (Phase 1: voice bot in the browser). See [ROADMAP.md](ROADMAP.md) and [RESULTS.md](RESULTS.md).

## Quickstart (macOS / Linux)

```bash
git clone <this repo> && cd callbuddy
uv sync                      # installs Python 3.12 deps from uv.lock
cp .env.example .env         # then add your own DEEPGRAM_API_KEY and GROQ_API_KEY
uv run python bot.py         # open http://localhost:7860/client, click Connect, use headphones
uv run pytest                # unit tests (no API calls)
```

`uv run pytest -m live` runs one real Groq request to check your key and model.

## Troubleshooting
- **First run is slow**: Kokoro downloads ~350 MB of model files to `~/.cache/pipecat/kokoro-onnx/`.
- **Kokoro fails to load after a slow or interrupted download**: delete
  `~/.cache/pipecat/kokoro-onnx/` and run again (a half-downloaded file is not re-downloaded on its own).
- **Bot talks to itself**: use headphones.

## Safety
Keys live only in `.env` (gitignored). The bot says it is an AI. It only calls numbers you give it for that run.
