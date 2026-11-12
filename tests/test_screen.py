"""Screen module tests: offline, no browser or API needed."""

import asyncio
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pipecat.processors.aggregators.llm_context import LLMContext

from callbuddy import screen


def png_bytes(w=2880, h=1800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(out, format="PNG")
    return out.getvalue()


def image_parts(messages):
    return [p for m in messages if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "image_url"]


def test_normalize_downscales_big_screens():
    jpeg, size = screen.normalize_jpeg(png_bytes())
    assert size == (1280, 800)  # max side 1280, aspect ratio kept
    assert jpeg[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_normalize_rejects_non_images():
    with pytest.raises(ValueError, match="not an image"):
        screen.normalize_jpeg(b"hello")


def test_store_rejects_huge_uploads():
    with pytest.raises(ValueError, match="too large"):
        screen.ScreenStore().put(b"x" * (screen.MAX_UPLOAD_BYTES + 1))


def test_store_ignores_stale_screenshots():
    store = screen.ScreenStore()
    assert store.fresh() is None
    store.put(png_bytes(10, 10), now=100.0)
    assert store.fresh(now=100.0 + screen.MAX_AGE_S - 1) is not None
    assert store.fresh(now=100.0 + screen.MAX_AGE_S + 1) is None
    store.clear()
    assert store.fresh(now=100.0) is None


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
    store, ctx = screen.ScreenStore(), LLMContext()
    for turn in range(3):
        ctx.add_message({"role": "user", "content": f"question {turn}"})
        asyncio.run(screen.attach_screenshot(ctx, store.put(png_bytes())))
    assert len(image_parts(ctx.get_messages())) == 1


def test_routes_upload_stop_and_page():
    store, app = screen.ScreenStore(), FastAPI()
    screen.add_screen_routes(app, store=store, page_html="<h1>Call Buddy</h1>")
    client = TestClient(app)
    assert "Call Buddy" in client.get("/buddy").text
    r = client.post("/screen", content=png_bytes(), headers={"Content-Type": "image/png"})
    assert r.status_code == 200 and r.json()["size"] == [1280, 800]
    assert store.fresh() is not None
    assert client.post("/screen", content=b"junk").status_code == 400
    client.delete("/screen")
    assert store.fresh() is None
