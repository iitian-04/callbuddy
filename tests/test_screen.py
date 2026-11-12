"""Screen module tests: offline, no browser or API needed."""

import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from callbuddy import screen


def png_bytes(w=2880, h=1800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(out, format="PNG")
    return out.getvalue()


def test_normalize_downscales_big_screens():
    jpeg, size = screen.normalize_jpeg(png_bytes())
    assert size == (1024, 640)  # max side 1024, aspect ratio kept
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


def test_routes_upload_stop_and_page():
    store, app = screen.ScreenStore(), FastAPI()
    screen.add_screen_routes(app, store=store, page_html="<h1>Call Buddy</h1>")
    client = TestClient(app)
    assert "Call Buddy" in client.get("/buddy").text
    r = client.post("/screen", content=png_bytes(), headers={"Content-Type": "image/png"})
    assert r.status_code == 200 and r.json()["size"] == [1024, 640]
    assert store.fresh() is not None
    assert client.post("/screen", content=b"junk").status_code == 400
    client.delete("/screen")
    assert store.fresh() is None


class FakeVision:
    def __init__(self, reply="The error says: No module named pandas."):
        self.reply, self.requests = reply, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


def test_look_at_screen_without_sharing_tells_user_how():
    out = asyncio.run(screen.look_at_screen(FakeVision(), "m", "what's this?", screen.ScreenStore()))
    assert "Share screen" in out["error"]


def test_look_at_screen_sends_newest_screenshot_and_question():
    store, vision = screen.ScreenStore(), FakeVision()
    store.put(png_bytes())
    out = asyncio.run(screen.look_at_screen(vision, "qwen", "what is this error?", store))
    assert out == {"seen_on_screen": "The error says: No module named pandas."}
    req = vision.requests[0]
    parts = req["messages"][-1]["content"]
    assert req["model"] == "qwen" and parts[0]["text"] == "what is this error?"
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_look_at_screen_with_empty_question_still_works():
    store, vision = screen.ScreenStore(), FakeVision()
    store.put(png_bytes())
    asyncio.run(screen.look_at_screen(vision, "m", "", store))
    assert "Describe" in vision.requests[0]["messages"][-1]["content"][0]["text"]
