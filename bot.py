"""CallBuddy voice bot (Phase 1): talk to it in your browser.

Run:   uv run python bot.py                      (free chat)
       uv run python bot.py --task "Book a table for 4 at 8 pm Saturday, 7:30-9 ok"
                                                  (call mode: you play the restaurant)
Open:  http://localhost:7860/client  and click Connect (use headphones!)

How a voice turn flows through the pipeline (each box is a Pipecat "processor";
"frames" of audio/text flow from left to right):

  mic audio -> [transport.input] -> [STT: Deepgram] -> [user aggregator + Silero VAD]
            -> [LLM: Groq] -> [TTS: Kokoro] -> [transport.output] -> your speakers
            -> [assistant aggregator] (remembers what the bot actually said)
"""

import argparse

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
from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame  # noqa: E402
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.runner import PipelineRunner  # noqa: E402
from pipecat.pipeline.task import PipelineParams, PipelineTask  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.runner.utils import create_transport  # noqa: E402
from pipecat.services.groq.llm import GroqLLMService  # noqa: E402
from pipecat.services.kokoro.tts import KokoroTTSService  # noqa: E402
from pipecat.transports.base_transport import BaseTransport, TransportParams  # noqa: E402

from callbuddy.brief import CallBrief  # noqa: E402
from callbuddy.planner import plan_call  # noqa: E402
from callbuddy.prompts import (  # noqa: E402
    GREETING_INSTRUCTION,
    SYSTEM_PROMPT,
    build_call_prompt,
)

# Set once at startup when --task is given. None means free-chat mode (Phase 1).
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
    llm = GroqLLMService(
        api_key=settings.groq_api_key.get_secret_value(),
        settings=GroqLLMService.Settings(
            model=settings.groq_model,
            # Call mode: rules come from the CallBrief. Free chat: the short Phase 1 prompt.
            system_instruction=build_call_prompt(CALL_BRIEF) if CALL_BRIEF else SYSTEM_PROMPT,
            reasoning_effort=settings.groq_reasoning_effort,
        ),
    )

    # 3. TTS (text-to-speech): Kokoro runs locally on your CPU, free, no API key.
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice=settings.kokoro_voice))

    # 4. Conversation memory. The user aggregator collects what you said into one
    #    message; Silero VAD (voice activity detection) decides when you started and
    #    stopped talking. When VAD hears you start talking while the bot is speaking,
    #    Pipecat sends an "interruption" and the bot stops (barge-in).
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),  # audio from the browser mic
            stt,  # audio -> text
            user_aggregator,  # text -> "user said X" in the context
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
            # Free chat: ask the LLM to greet first, so you know it's working.
            context.add_message({"role": "developer", "content": GREETING_INSTRUCTION})
            await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Entry point the Pipecat runner calls when a browser connects."""
    transport_params = {
        # SmallWebRTC: a direct browser <-> laptop WebRTC connection, no account needed.
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
    parser = argparse.ArgumentParser(description="CallBuddy voice bot")
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
        logger.info("No --task given: free-chat mode")

    main(parser)
