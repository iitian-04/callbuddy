"""Screen module tests: offline, no browser or API needed."""

import asyncio

from PIL import Image
from pipecat.frames.frames import InputImageRawFrame
from pipecat.processors.aggregators.llm_context import LLMContext

from callbuddy import screen


def make_frame(w=2880, h=1800, source=screen.SCREEN_SOURCE) -> InputImageRawFrame:
    img = Image.new("RGB", (w, h), "white")
    f = InputImageRawFrame(image=img.tobytes(), size=(w, h), format="RGB")
    f.transport_source = source
    return f


def image_parts(messages):
    return [p for m in messages if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "image_url"]


def test_to_jpeg_downscales_big_screens():
    f = make_frame()
    jpeg, size = screen.to_jpeg(f.image, f.size, f.format)
    assert max(size) == screen.MAX_SIDE and size == (1280, 800)  # aspect ratio kept
    assert jpeg[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_strip_old_screenshots_keeps_text():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "x"}}]},
        {"role": "assistant", "content": "hello"},
    ]
    out = screen.strip_old_screenshots(msgs)
    assert image_parts(out) == []
    assert {"type": "text", "text": "hi"} in out[0]["content"]
    assert out[1] == msgs[1]


def test_only_one_screenshot_in_context_after_many_turns():
    ctx = LLMContext()
    for turn in range(3):
        ctx.add_message({"role": "user", "content": f"question {turn}"})
        asyncio.run(screen.attach_screenshot(ctx, make_frame()))
    assert len(image_parts(ctx.get_messages())) == 1


def test_buffer_ignores_stale_frames():
    buf = screen.ScreenBuffer()
    assert buf.fresh_frame() is None
    buf.latest, buf.latest_at = make_frame(10, 10), 100.0
    assert buf.fresh_frame(now=100.0 + screen.MAX_AGE_S - 1) is not None
    assert buf.fresh_frame(now=100.0 + screen.MAX_AGE_S + 1) is None
