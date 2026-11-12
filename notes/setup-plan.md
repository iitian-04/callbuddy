# CallBuddy: setup, deployment and Phase 0 + 1 plan

Written 6 Nov 2026. All provider facts below were checked on the providers' own pages today
(links at the bottom). Anything not confirmed is marked **unverified**. No code has been written.

---

## 1. Environment check

Your linked device is a **MacBook Air, Apple Silicon (arm64), macOS**. Versions of Python, uv,
git and your RAM still need to be read on the Mac itself. Two ways:

- **Remote Control** (I asked for approval in the thread): a session on your Mac runs the
  read-only checks and reports back. Nothing gets installed.
- **Copy-paste instead:** run [`check_env.sh`](check_env.sh) in Terminal (`bash check_env.sh`)
  and paste the output in the thread. It is read-only and never prints keys.

**Result (checked on your Mac, 6 Nov):** macOS 26.2, Apple M4, 10 cores, 16 GB RAM. Xcode, Homebrew 6.0.15,
git 2.50.1, uv 0.11.33 (with Python 3.11, 3.12, 3.13 available), gh 2.97.0, ffmpeg, Docker, Node and
Claude Code are all installed. Missing: `cloudflared` (only needed from Phase 4: `brew install cloudflared`).
To do: set `git config --global user.email`, check which GitHub account gh is logged into, and free some
disk (19 GB free, 96% full).

What we need, and the install command for each if it is missing (I will tell you exactly
which ones apply once I see the output; per CLAUDE.md I won't run any of these myself):

| Tool | Need | Install on macOS |
|---|---|---|
| Xcode Command Line Tools (gives git) | required | `xcode-select --install` |
| Homebrew | recommended | see https://brew.sh (one-line installer) |
| git | required | comes with Xcode CLT, or `brew install git` |
| uv | required | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or `brew install uv` |
| Python 3.11+ | required (Pipecat needs >=3.11) | `uv python install 3.12` (uv manages it; no system Python change) |
| git identity | required | `git config --global user.name "Priyanshu Srivastava"` and `git config --global user.email "<your GitHub email>"` |
| GitHub CLI | optional, makes repo setup easy | `brew install gh` then `gh auth login` |
| cloudflared | Phase 4 / 7 fallback | `brew install cloudflared` |
| Headphones | required for testing | stops the bot hearing itself |

RAM note: Kokoro, Silero VAD and Pipecat run comfortably on any Apple Silicon Mac with 8 GB+;
we will measure actual memory use in Phase 1 rather than guess.

---

## 2. What I need from you (accounts, keys, manual steps)

You add every key to `.env` yourself. Never paste a key in chat.

### Phase 0: blocks Phase 1
1. **GitHub**: create a public repo named `callbuddy` (https://github.com/new). I can't create
   repos from here. Then [Connect GitHub](https://claude.ai/connect-github) so I can push to it.
2. **Deepgram** (STT): sign up at https://console.deepgram.com/signup, create an API key.
   $200 free credit, no card, no expiry. Put it in `.env` as `DEEPGRAM_API_KEY`.
3. **Groq** (LLM): sign up at https://console.groq.com, create a key at
   https://console.groq.com/keys, put it in `.env` as `GROQ_API_KEY`. Then open
   https://console.groq.com/settings/limits and note the free limits for `openai/gpt-oss-120b`
   and `openai/gpt-oss-20b` (see Risk 1 for why not llama).
4. **Install tools** from section 1 that the check says are missing.
5. **Headphones.**

### Phase 1
- Nothing new. Allow microphone access in the browser when it asks. Kokoro downloads its
  model files on the first run (a few minutes, once).

### Phase 3 (optional)
- **Telegram bot** for summaries: message `@BotFather` in Telegram, `/newbot`, put the token in
  `.env` as `TELEGRAM_BOT_TOKEN`, and your chat id as `TELEGRAM_CHAT_ID`.

### Phase 4 (phone)
- **Twilio trial**: sign up at https://www.twilio.com/try-twilio (no card; verify email + phone).
- **Verified Caller IDs**: Console > Phone Numbers > Verified Caller IDs. Max 5 numbers,
  SMS verification only. Your sign-up number is verified automatically. Friends only with consent.
- **Trial number**: get the free trial number in the console.
- **Check first (7 Nov, 10 minutes)**: Twilio's trial docs say `<Stream>` is blocked on trial
  accounts and calls are limited to your sign-up country. If that holds, the phone phase cannot
  be done at $0 (see Risk 2). Keys: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
- `brew install cloudflared` (no Cloudflare account needed for quick tunnels).

### Phase 5
- Nothing new (uses Groq).

### Phase 6
- Screen + audio recording for the demo video (QuickTime is free on macOS).
- LinkedIn / X accounts for the post.

### Phase 7 (deploy)
- **Render**: sign up with GitHub at https://dashboard.render.com/register. Free web service.
- **Daily**: sign up at https://dashboard.daily.co, copy the API key into Render's environment
  settings as `DAILY_API_KEY` (and into your local `.env` for testing).
- Set all keys in the Render dashboard (Environment tab), never in the repo.

---

## 3. Deployment research (Phase 7)

What a public browser demo needs: (a) a server that runs the Pipecat bot, (b) a way for audio
to reach a stranger's browser through NATs and firewalls (WebRTC), (c) enough RAM/CPU for the
pipeline, (d) $0 and ideally no card.

Key facts that shape the choice:
- **Hugging Face Spaces** is no longer an option for free: its docs now say Gradio and Docker
  Spaces "require a paid plan to create" (PRO). Static Spaces stay free but can't run Python.
- **SmallWebRTC in the cloud needs TURN**: Pipecat's docs say ICE servers become important once
  peers are on different networks, and TURN is "recommended" for production and needed for macOS
  or strict NAT. Most free hosts (Render, Cloud Run) only accept HTTP(S) in, not WebRTC's UDP.
- **Daily transport avoids that**: with Pipecat's `DailyTransport`, the bot connects *out* to
  Daily's WebRTC servers, and the browser connects to Daily too. The host only needs outbound
  internet. Daily gives 10,000 free participant minutes per month.

### Comparison

| | Render free + Daily (recommended) | Oracle Cloud Always Free VM | Laptop + cloudflared (fallback) |
|---|---|---|---|
| Cost / card | $0. Card not stated as required | $0, but **card required** for identity check (temporary hold) | $0, no account |
| Resources | 512 MB RAM; CPU not stated (small) | Arm Ampere A1 VM; exact OCPU/RAM **unverified** (docs page failed to load; historically up to 4 OCPU / 24 GB) | Your Mac |
| Cold start | Spins down after 15 min idle; ~1 min to wake | None (always on). Idle *accounts* (30 days) may be suspended | None while laptop is on |
| Limits | 750 instance hours/month; may restart any time | Capacity in Indian regions can be hard to get (**unverified**) | Quick tunnel: no uptime guarantee, 200 in-flight requests, URL changes every restart |
| Kokoro fits? | **Unlikely** in 512 MB next to Pipecat + onnxruntime (**unverified**, will measure locally). Use Deepgram Aura TTS in the cloud (paid from the $200 credit: $0.030 per 1k chars for Aura-2) | Yes, plenty of RAM | Yes |
| WebRTC works? | Yes via Daily (no inbound UDP needed). SmallWebRTC would need a TURN server | Yes, SmallWebRTC directly (open UDP in the VM firewall) or Daily | Signaling goes through the tunnel; audio is peer-to-peer and may need TURN on some networks. Daily transport also works and needs no tunnel |
| Twilio endpoint | Possible (HTTPS + websocket), but we won't deploy phone mode publicly | Possible | **This is where phone mode runs**, only during your own calls |

Other options checked and rejected: **Koyeb** (no free compute instance any more; Pro plan
$29/mo), **Fly.io** (card required, no free allowance stated), **Google Cloud Run** (free
monthly quota exists but a billing account with a card is required), **Pipecat Cloud** (from
$0.01 per active agent minute; no free credit stated).

### Recommendation
- **Primary: Render free web service running the bot with Daily transport and Deepgram Aura TTS.**
  It is the only option that is truly $0 with no card, gives a stable public URL, and needs no
  TURN server. The ~1 minute wake-up is handled with an honest "waking up" message on the page.
  Kokoro stays the TTS for local runs; the cloud picks TTS by env var.
- **Guardrails are mandatory for a public link**: access code you share with recruiters, 3-minute
  session cap, one session at a time, daily cap. Otherwise a stranger can burn your Deepgram
  credit and Groq limits.
- **Fallback A: laptop + cloudflared** for live interviews (`cloudflared tunnel --url http://localhost:7860`).
- **Fallback B: Oracle Always Free**, only if you're fine giving a card for verification.
- **Always:** the 2-minute video in the README, so the demo "works" even when a host is asleep.
- **Phone endpoint:** never public. It runs on your laptop + tunnel only while you make your own
  calls to numbers you give me for that run.

---

## 4. Project structure

```
callbuddy/
├── bot.py                 # entry point: uv run python bot.py [--task "..."] [--mode browser|phone]
├── call.py                # Phase 4: places ONE outbound call to a number passed on the command line
├── callbuddy/             # the actual code, as a small package
│   ├── __init__.py
│   ├── config.py          # Settings class: reads .env, keys are SecretStr (never printed)
│   ├── logging_setup.py   # one place to configure logs (loguru, which Pipecat already uses)
│   ├── pipeline.py        # builds the Pipecat pipeline (STT -> LLM -> TTS), shared by browser + phone
│   ├── planner.py         # Phase 2: task -> CallBrief
│   ├── brief.py           # Phase 2: CallBrief Pydantic model
│   ├── tools.py           # Phase 3: check_calendar, record_outcome, end_call
│   ├── summary.py         # Phase 3
│   └── server.py          # Phase 4: FastAPI websocket for Twilio
├── data/calendar.json     # Phase 3
├── eval/                  # Phase 5: scenarios.yaml, simulator.py, judge.py, run_eval.py
├── tests/                 # pytest; one test file per module
├── notes/                 # failures.md, what-i-learned.md
├── transcripts/ results/  # gitignored, created at runtime
├── .github/workflows/ci.yml
├── .env.example           # names of every variable, no values; committed
├── .env                   # your keys; gitignored, never committed
├── .gitignore
├── pyproject.toml + uv.lock  # uv pins every version, so Pipecat can't change under us
├── CLAUDE.md  ROADMAP.md  RESULTS.md  README.md
```
Only the files for the current phase get created. Phase 1 is just `bot.py`, `config.py`,
`logging_setup.py`, `pipeline.py`, one test file, and the setup files.

**Config:** `pydantic-settings`. One `Settings` class lists every variable with a type and default
(`GROQ_MODEL`, `TTS_PROVIDER`, `LOG_LEVEL`...). Keys are `SecretStr`, so printing settings shows
`**********`. If a required key is missing, startup fails with a clear "DEEPGRAM_API_KEY missing
in .env" message instead of a crash deep in the pipeline.

**Logging:** loguru (Pipecat already uses it, so one logger for everything). Level from
`LOG_LEVEL`. Console output by default; a log file in `logs/` (gitignored). A small filter masks
anything that looks like a key, as a second safety net.

**Tests:** pytest. Unit tests never call real APIs (fast, free, run in CI). Tests that hit
Groq/Deepgram are marked `@pytest.mark.live` and skipped unless you run `uv run pytest -m live`.

**CI:** GitHub Actions on every push and PR: checkout, `astral-sh/setup-uv`, `uv sync --locked`,
`uv run pytest -m "not live"`. About 20 lines of YAML. No secrets are needed in CI.

---

## 5. Top 5 risks this week

1. **The planned LLM no longer exists.** Groq's deprecations page lists `llama-3.3-70b-versatile`
   and `llama-3.1-8b-instant` as shut down on 16 Aug 2026 ("requests to deprecated model IDs will
   return errors"), replaced by `openai/gpt-oss-120b` / `openai/gpt-oss-20b`.
   *Avoid:* model name lives in `.env` (`GROQ_MODEL`), default `openai/gpt-oss-120b`; first
   step of Phase 1 is one real request to confirm it works and to check it does tool calls.
   I updated ROADMAP.md Phase 1 to say this. CLAUDE.md doesn't name the model, so it needs no change.
2. **Twilio trial may not allow the phone phase at $0.** Twilio's trial docs list `<Stream>`
   (which Pipecat's Twilio integration uses) as blocked, and limit calls to your sign-up country
   (a US trial number calling an Indian phone would be international).
   *Avoid:* check in the console on 7 Nov. If it's blocked, I'll research the cheapest
   option (likely a small Twilio upgrade) and bring it to you before anything is spent. The
   browser version is the main demo either way.
3. **No free host has the RAM for Kokoro plus open UDP.** HF Spaces now needs PRO; Render free is
   512 MB.
   *Avoid:* Daily transport + Aura TTS in the cloud (decided above), and measure Kokoro's real
   memory in Phase 1 so we know, not guess.
4. **A public link drains free credit, or a key leaks.** *Avoid:* access code, session and daily
   caps (Phase 7); `.env` in `.gitignore` before the first commit; `SecretStr` + log masking;
   `git grep` check before every push; GitHub secret scanning stays on for the public repo.
5. **Pipecat API churn eats the deadline.** Pipecat is at v1.15.0 on PyPI, and the Kokoro docs
   already mark `voice_id`/`params` as deprecated in favour of `settings=...`.
   *Avoid:* pin the version in `uv.lock`, read the installed package source for class names,
   start from the official quickstart's structure, and one small runnable step at a time. Use
   headphones from the first test (echo is the #1 "it's broken" cause).

---

## 6. Plan for Phase 0 + Phase 1 (waiting for your "go")

**Phase 0: Setup (you + me, ~1 hr)**
1. You: run the env check (Remote Control or `check_env.sh`); install what's missing.
2. You: create the `callbuddy` GitHub repo, connect GitHub here, create Deepgram + Groq keys.
3. Me: add the repo to this thread, then commit `pyproject.toml` (Python >=3.11), `.gitignore`
   (`.env`, `transcripts/`, `results/`, `logs/`, recordings, `.venv`), `.env.example`, your
   CLAUDE.md / ROADMAP.md / RESULTS.md, the CI workflow and one placeholder test, so CI is green
   from the first push.
4. You: copy `.env.example` to `.env` and paste your keys into it (on your Mac, not in chat).
5. Me: confirm `.env` is ignored (`git check-ignore .env`), tick Phase 0, log it in RESULTS.md.

**Phase 1: Voice bot in the browser (~5 hrs)**
1. Read the installed Pipecat source for the exact class names (SmallWebRTC transport,
   Deepgram STT, Groq LLM, Kokoro TTS, Silero VAD) and the current runner. Note version.
2. `config.py` + `logging_setup.py` + a test that a missing key gives a clear error.
3. One real Groq call with `GROQ_MODEL` to confirm the model works. Commit.
4. `pipeline.py` + `bot.py`: transport -> STT -> LLM (short friendly prompt, under 2 sentences)
   -> Kokoro TTS -> output, with comments on each stage. You run `uv run python bot.py`, open
   http://localhost:7860/client, and talk. Commit.
5. Test interruption: talk over it and check it stops. Tune VAD only if needed. Commit.
6. Measure Kokoro memory and rough reply latency; write only real numbers in RESULTS.md.
7. Walk-through: I explain each stage of bot.py, then quiz you with 5 questions.

Done when: it answers out loud and stops when you interrupt (ROADMAP Phase 1).

---

## Sources (checked 6 Nov 2026)
- HF Spaces hardware & paid-plan note: https://huggingface.co/docs/hub/en/spaces-overview, https://huggingface.co/docs/hub/en/spaces-gpus
- Pipecat SmallWebRTC (STUN/TURN): https://docs.pipecat.ai/server/services/transport/small-webrtc
- Pipecat Kokoro: https://docs.pipecat.ai/server/services/tts/kokoro
- Pipecat Twilio websockets: https://docs.pipecat.ai/guides/telephony/twilio-websockets
- Pipecat quickstart: https://docs.pipecat.ai/getting-started/quickstart · PyPI: https://pypi.org/project/pipecat-ai/
- Render free: https://render.com/docs/free · https://render.com/pricing
- Daily pricing: https://www.daily.co/pricing/video-sdk/ · Pipecat Cloud: https://www.daily.co/pricing/pipecat-cloud
- Oracle Always Free: https://www.oracle.com/cloud/free/
- Cloud Run: https://cloud.google.com/run/pricing · Koyeb: https://www.koyeb.com/pricing · Fly.io: https://fly.io/docs/about/pricing/
- Cloudflare quick tunnels: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
- Twilio trial: https://www.twilio.com/docs/usage/trials · https://www.twilio.com/docs/usage/trials/try-out-voice
- Deepgram pricing: https://deepgram.com/pricing
- Groq deprecations: https://console.groq.com/docs/deprecations · limits: https://console.groq.com/docs/rate-limits
- uv install: https://docs.astral.sh/uv/getting-started/installation/
