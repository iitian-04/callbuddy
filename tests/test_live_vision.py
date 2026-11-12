"""Live check: the vision model reads a screenshot we attach the same way the bot does."""

import asyncio
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from pipecat.processors.aggregators.llm_context import LLMContext

from callbuddy import screen


@pytest.mark.live
def test_vision_model_reads_fake_screen():
    from openai import OpenAI

    from callbuddy.config import load_settings
    from callbuddy.prompts import SYSTEM_PROMPT

    # A fake 1440x900 "screen" with an error message on it.
    img = Image.new("RGB", (1440, 900), "white")
    font = ImageFont.load_default(size=36)
    ImageDraw.Draw(img).text((60, 400), "ModuleNotFoundError: No module named 'pandas'", fill="red", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    shot = screen.ScreenStore().put(buf.getvalue())  # same path as an upload from /buddy

    ctx = LLMContext()
    ctx.add_message({"role": "user", "content": "What's this error on my screen?"})
    asyncio.run(screen.attach_screenshot(ctx, shot))

    s = load_settings()
    client = OpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    r = client.chat.completions.create(
        model=s.vision_model,
        reasoning_effort=s.vision_reasoning_effort,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *ctx.get_messages()],
    )
    reply = r.choices[0].message.content or ""
    print(f"\nmodel={s.vision_model} reply={reply!r}")
    assert "pandas" in reply.lower()
