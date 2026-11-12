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
uv run python bot.py         # open http://localhost:7860/buddy, click Connect, then Share screen
uv run pytest                # unit tests (no API calls)
```

`uv run pytest -m live` runs one real Groq request to check your key and model.

## Gmail (optional): search, read, and save reply drafts
Call Buddy can search and read your Gmail and save reply **drafts** (it can't send, delete or
change mail; you send drafts yourself). One-time setup, all free:
1. https://console.cloud.google.com → create a project "Call Buddy".
2. APIs & Services → Library → "Gmail API" → Enable.
3. APIs & Services → OAuth consent screen: User type **External**; app name "Call Buddy"; your
   email as support + developer contact; Scopes: skip; Test users: **add your own Gmail address**.
4. APIs & Services → Credentials → Create credentials → OAuth client ID → Application type
   **Desktop app** → Create → **Download JSON** → save it as `secrets/google_credentials.json`.
5. `uv run python -m callbuddy.gmail auth` → Google opens → pick your account → "Google hasn't
   verified this app" → Continue → allow → done. Token saved to `secrets/google_token.json`.
6. `uv run python -m callbuddy.gmail test` lists your last 3 emails. Restart the bot.
`secrets/` is gitignored. To disconnect: delete `secrets/google_token.json` and remove "Call Buddy" at
myaccount.google.com → Security → Third-party connections. Email text you ask about is sent to Groq.

## Faster voice (recommended on a laptop)
The int8 Kokoro model is about 2x faster than the full one on CPU. Download it once:
```bash
curl -L -o ~/.cache/pipecat/kokoro-onnx/kokoro-v1.0.int8.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
```
Without it, Call Buddy falls back to the full model.

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
