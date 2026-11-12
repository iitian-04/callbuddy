"""Live: the look_at_screen tool reads a fake screenshot with the real vision model."""

import asyncio
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from callbuddy import screen


@pytest.mark.live
def test_look_at_screen_reads_an_error():
    from openai import AsyncOpenAI

    from callbuddy.config import load_settings

    img = Image.new("RGB", (1440, 900), "white")
    font = ImageFont.load_default(size=36)
    ImageDraw.Draw(img).text((60, 400), "ModuleNotFoundError: No module named 'pandas'", fill="red", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    store = screen.ScreenStore()
    store.put(buf.getvalue())  # same path as an upload from /buddy

    s = load_settings()
    client = AsyncOpenAI(api_key=s.groq_api_key.get_secret_value(), base_url="https://api.groq.com/openai/v1")
    out = asyncio.run(screen.look_at_screen(client, s.vision_model, "What's this error on my screen?", store))
    print(f"\n{out}")
    assert "pandas" in out["seen_on_screen"].lower()
