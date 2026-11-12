"""Call Buddy voice bot: talk to it in your browser, and share your screen so it can see.

Run:   uv run python bot.py                      (screen buddy, the default)
       uv run python bot.py --task "Book a table for 4 at 8 pm Saturday, 7:30-9 ok"
                                                  (call mode: you play the restaurant)
Open:  http://localhost:7860/buddy   click Connect (use headphones!), then "Share screen".

How a voice turn flows through the pipeline (each box is a Pipecat "processor";
"frames" of audio/text flow from left to right):

  /buddy page --- one small JPEG every 2 s, POST /screen ---> ScreenStore (newest only)
  mic audio -> [transport.input] -> [STT] -> [user aggregator + Silero VAD]
            -> [ScreenInjector: adds newest screenshot]
            -> [LLM: Groq] -> [TTS: Kokoro] -> [transport.output] -> your speakers
            -> [assistant aggregator] (remembers what the bot actually said)
"""

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from callbuddy.config import load_settings
from callbuddy.logging_setup import setup_logging

# Load settings first, so a missing key fails fast with a friendly message.
settings = load_settings()
setup_logging(
    settings.log_level,
    secrets=[
        settings.groq_api_key.get_secret_value(),
        settings.deepgram_api_key.get_secret_value() if settings.deepgram_api_key else "",
    ],
)

logger.info("Loading Pipecat (first run downloads the Silero and Kokoro models)...")

from pipecat.audio.vad.silero import SileroVADAnalyzer  # noqa: E402
from pipecat.frames.frames import TTSSpeakFrame  # noqa: E402
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.runner import PipelineRunner  # noqa: E402
from pipecat.pipeline.task import PipelineParams, PipelineTask  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.turns.user_start.min_words_user_turn_start_strategy import (  # noqa: E402
    MinWordsUserTurnStartStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies  # noqa: E402
from pipecat.runner.utils import create_transport  # noqa: E402
from pipecat.services.groq.llm import GroqLLMService  # noqa: E402
from pipecat.services.kokoro.tts import KokoroTTSService  # noqa: E402
from pipecat.transports.base_transport import BaseTransport, TransportParams  # noqa: E402

from callbuddy.brief import CallBrief  # noqa: E402
from callbuddy.planner import plan_call  # noqa: E402
from callbuddy.prompts import GREETING, SYSTEM_PROMPT, build_call_prompt, split_sentences  # noqa: E402
from callbuddy.memory import MemoryProcessor, SessionMemory  # noqa: E402
from callbuddy.screen import ScreenInjector, add_screen_routes  # noqa: E402

KOKORO_DIR = Path.home() / ".cache" / "pipecat" / "kokoro-onnx"

# Set once at startup when --task is given. None means screen-buddy mode (the default).
CALL_BRIEF: CallBrief | None = None


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    # 1. STT (speech-to-text): Deepgram if you have a key (streams audio, fastest),
    #    otherwise Groq's hosted Whisper (sends each finished utterance, same Groq key).
    if settings.resolved_stt_provider == "deepgram":
        from pipecat.services.deepgram.stt import DeepgramSTTService

        stt = DeepgramSTTService(api_key=settings.deepgram_api_key.get_secret_value())
    else:
        from pipecat.services.groq.stt import GroqSTTService

        stt = GroqSTTService(api_key=settings.groq_api_key.get_secret_value())
    logger.info(f"STT provider: {settings.resolved_stt_provider}")

    # 2. LLM (the brain): Groq's OpenAI-compatible API. Streams the reply token by token,
    #    so TTS can start speaking before the whole answer is finished.
    #    Call mode: gpt-oss (text) with rules from the CallBrief.
    #    Screen mode: a model that can read images, since it gets screenshots.
    if CALL_BRIEF:
        llm_settings = GroqLLMService.Settings(
            model=settings.groq_model,
            system_instruction=build_call_prompt(CALL_BRIEF),
            reasoning_effort=settings.groq_reasoning_effort,
        )
    else:
        llm_settings = GroqLLMService.Settings(
            model=settings.vision_model,
            system_instruction=SYSTEM_PROMPT,
            reasoning_effort=settings.vision_reasoning_effort,
        )
    llm = GroqLLMService(api_key=settings.groq_api_key.get_secret_value(), settings=llm_settings)

    # 3. TTS (text-to-speech): Kokoro runs locally on your CPU, free, no API key.
    model_path = KOKORO_DIR / settings.kokoro_model
    if not model_path.exists():
        # Pipecat would download the FULL model to this path if it is missing, so fall back.
        logger.warning(f"{model_path} not found, using the default Kokoro model")
        model_path = None
    tts = KokoroTTSService(
        model_path=str(model_path) if model_path else None,
        settings=KokoroTTSService.Settings(voice=settings.kokoro_voice),
    )

    # 4. Conversation memory. The user aggregator collects what you said into one
    #    message; Silero VAD (voice activity detection) decides when you started and
    #    stopped talking. When VAD hears you start talking while the bot is speaking,
    #    Pipecat sends an "interruption" and the bot stops (barge-in).
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            # While the bot is talking, you need at least 3 words to interrupt it, so short
            # "yes" / "so," / "thank you" don't cut it off (notes/failures.md #8). When the bot
            # is quiet, one word still starts your turn.
            user_turn_strategies=UserTurnStrategies(start=[MinWordsUserTurnStartStrategy(min_words=3)]),
        ),
    )

    # 5. Memory (screen mode): short notes about what you're working on, a summary on exit.
    memory = None
    if not CALL_BRIEF:
        from openai import AsyncOpenAI

        notes_client = AsyncOpenAI(
            api_key=settings.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1"
        )
        memory = SessionMemory(notes_client, settings.memory_model)
        if memory.last_session:
            logger.info("Memory: loaded the summary of your previous session")
    memory_processors = [MemoryProcessor(memory)] if memory else []

    pipeline = Pipeline(
        [
            transport.input(),  # audio from the browser mic
            stt,  # audio -> text
            user_aggregator,  # text -> "user said X" in the context
            *memory_processors,  # notes at the top, old turns trimmed (screen mode only)
            ScreenInjector(),  # adds "this is my screen right now" + newest screenshot
            llm,  # context -> reply text (streamed)
            tts,  # reply text -> audio
            transport.output(),  # audio -> browser speakers
            assistant_aggregator,  # store what the bot said (cut short if interrupted)
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")
        if CALL_BRIEF:
            # Call mode: speak the planned opening line directly (no LLM call). TTSSpeakFrame
            # also adds it to the context as the bot's turn. Earlier we asked the LLM to
            # "say exactly this", but that instruction stayed in the context and the bot
            # repeated the opening line every time it was interrupted (notes/failures.md #1).
            await task.queue_frames([TTSSpeakFrame(CALL_BRIEF.opening_line)])
        else:
            # Screen mode: fixed greeting with the privacy disclaimer, spoken word for word.
            # One frame per sentence: Kokoro makes each frame in one go, so the whole greeting
            # as one frame took ~10 s before you heard anything; the first sentence takes ~1 s.
            await task.queue_frames([TTSSpeakFrame(s) for s in split_sentences(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        if memory:
            # Save a short summary of this session to sessions/ (gitignored), max 15 s.
            try:
                await asyncio.wait_for(memory.finish(context.get_messages()), timeout=15)
            except asyncio.TimeoutError:
                logger.warning("Session summary took too long, skipped")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Entry point the Pipecat runner calls when a browser connects."""
    transport_params = {
        # SmallWebRTC: a direct browser <-> laptop WebRTC connection, no account needed.
        # Audio only: screenshots come over HTTP from the /buddy page, not as WebRTC video.
        "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    }
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    # The Pipecat dev runner starts a web server on :7860 with a ready-made test page
    # at /client, and calls bot() for each browser that connects.
    from pipecat.runner.run import main

    # Our own flag. The same parser is handed to Pipecat's runner, which adds its flags
    # (--host, --port, ...) to it, so `--task` and the runner flags work together.
    parser = argparse.ArgumentParser(description="Call Buddy voice bot")
    parser.add_argument("--task", help="Task for the call, e.g. 'Book a table for 4 at 8 pm Sat'")
    known, _ = parser.parse_known_args()

    if known.task:
        # Plan once at startup, so a bad plan fails before anyone connects.
        CALL_BRIEF = plan_call(
            known.task,
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            default_name=settings.caller_name or "the user",
        )
        logger.info("Call brief:\n" + CALL_BRIEF.model_dump_json(indent=2))
    else:
        logger.info(f"No --task given: screen-buddy mode (vision model {settings.vision_model})")

    # Add the Call Buddy page (/buddy) and the screenshot endpoint to the runner's web server.
    from pipecat.runner.run import app

    page = (Path(__file__).parent / "callbuddy" / "static" / "buddy.html").read_text()
    add_screen_routes(app, page_html=page)
    logger.info("Open http://localhost:7860/buddy to talk and share your screen")

    main(parser)
