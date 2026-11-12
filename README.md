# Call Buddy

A voice AI work buddy that can see your screen. Share your screen in the browser, talk, and it
explains what's on it: errors, emails, pages, "what should I click?". It only looks and explains
for now; safe actions (with your OK) and phone calls for you come later.

It can also run a planned phone-call conversation: `uv run python bot.py --task "..."`.

> Work in progress (S1: see and explain). See [ROADMAP.md](ROADMAP.md) and [RESULTS.md](RESULTS.md).

## Quickstart (macOS / Linux)

```bash
git clone <this repo> && cd callbuddy
uv sync                      # installs Python 3.12 deps from uv.lock
cp .env.example .env         # then add your own GROQ_API_KEY (Deepgram key optional)
uv run python bot.py         # open http://localhost:7860/client, click Connect, share your screen
uv run pytest                # unit tests (no API calls)
```

`uv run pytest -m live` runs one real Groq request to check your key and model.

## Troubleshooting
- **First run is slow**: Kokoro downloads ~350 MB of model files to `~/.cache/pipecat/kokoro-onnx/`.
- **Kokoro fails to load after a slow or interrupted download**: delete
  `~/.cache/pipecat/kokoro-onnx/` and run again (a half-downloaded file is not re-downloaded on its own).
- **Bot talks to itself**: use headphones.

## Privacy and safety
- While you share your screen, a screenshot (max 1280 px) is sent to Groq each time you speak, so it
  can answer about it. Nothing is saved to disk. Keep passwords, banking and private chats off screen.
  Call Buddy says this out loud every time you connect.
- Keys live only in `.env` (gitignored). Call Buddy always says it is an AI.
- Call mode only calls numbers you give it for that run.
