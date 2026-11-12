"""Screen understanding (S1): let the LLM see the latest picture of your shared screen.

How screenshots reach the bot (no video over WebRTC):

  Call Buddy page (/buddy) --- every 2 s: small JPEG, HTTP POST /screen ---> ScreenStore
  mic audio -> ... -> user aggregator -> [ScreenInjector] -> LLM

Why not WebRTC screen video? We tried: the bot had to decode a full-resolution screen
stream at up to 30 fps in Python. That froze the event loop for ~30 s, the audio output
timed out, and you stopped hearing the bot (notes/failures.md #6). Now the BROWSER does the
work: it grabs a frame, shrinks it to max 1280 px and sends one JPEG every 2 seconds.

- ScreenStore keeps ONLY the newest screenshot in memory (nothing is saved to disk).
- ScreenInjector runs right before the LLM. Each time you finish speaking, it adds the
  newest screenshot to the conversation as "this is my screen right now". Older
  screenshots are replaced by a short note, so the context doesn't grow every turn.
"""

import io
import time
from dataclasses import dataclass

from loguru import logger
from PIL import Image
from pipecat.frames.frames import Frame, LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

MAX_SIDE = 1280  # px; big enough to read text, small enough to keep requests fast
MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # reject anything bigger than 3 MB
MAX_AGE_S = 10.0  # ignore a screenshot older than this (sharing probably stopped)
OLD_SCREENSHOT_NOTE = "[older screenshot removed]"
SCREENSHOT_TEXT = "This is my screen right now."


@dataclass
class Screenshot:
    jpeg: bytes
    size: tuple[int, int]
    at: float  # time.monotonic() when received


def normalize_jpeg(data: bytes) -> tuple[bytes, tuple[int, int]]:
    """Any image bytes -> JPEG bytes no bigger than MAX_SIDE, plus its size.

    Raises ValueError if `data` is not an image we can open.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:  # PIL raises several error types for bad data
        raise ValueError(f"not an image: {e}") from None
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # keeps aspect ratio, never upscales
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=75)
    return out.getvalue(), img.size


class ScreenStore:
    """Holds the newest screenshot in memory. One per bot process (one local user)."""

    def __init__(self):
        self.latest: Screenshot | None = None

    def put(self, data: bytes, now: float | None = None) -> Screenshot:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("screenshot too large")
        jpeg, size = normalize_jpeg(data)
        if self.latest is None:
            logger.info(f"Screen sharing: first screenshot received ({size[0]}x{size[1]})")
        self.latest = Screenshot(jpeg, size, time.monotonic() if now is None else now)
        return self.latest

    def clear(self):
        self.latest = None

    def fresh(self, now: float | None = None) -> Screenshot | None:
        now = time.monotonic() if now is None else now
        if self.latest is not None and now - self.latest.at <= MAX_AGE_S:
            return self.latest
        return None


# The one store the web endpoint writes and the pipeline reads.
SCREEN_STORE = ScreenStore()


def strip_old_screenshots(messages: list) -> list:
    """Return messages with every image part replaced by a short text note."""
    cleaned = []
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list) and any(p.get("type") == "image_url" for p in content):
            parts = [p for p in content if p.get("type") != "image_url"]
            parts.append({"type": "text", "text": OLD_SCREENSHOT_NOTE})
            m = {**m, "content": parts}
        cleaned.append(m)
    return cleaned


async def attach_screenshot(context, shot: Screenshot) -> None:
    """Replace older screenshots in `context` with a note, then add `shot` as the newest."""
    context.set_messages(strip_old_screenshots(context.get_messages()))
    await context.add_image_frame_message(
        format="image/jpeg", size=shot.size, image=shot.jpeg, text=SCREENSHOT_TEXT
    )
    logger.debug(f"Attached screenshot {shot.size[0]}x{shot.size[1]}, {len(shot.jpeg) // 1024} KB")


class ScreenInjector(FrameProcessor):
    """Adds the newest screenshot to the context just before each LLM request."""

    def __init__(self, store: ScreenStore = SCREEN_STORE, **kwargs):
        super().__init__(**kwargs)
        self._store = store

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            shot = self._store.fresh()
            if shot is not None:
                await attach_screenshot(frame.context, shot)
        await self.push_frame(frame, direction)


def add_screen_routes(app, store: ScreenStore = SCREEN_STORE, page_html: str = "") -> None:
    """Add the Call Buddy page (/buddy) and the screenshot upload endpoint to the web server."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    @app.get("/buddy", response_class=HTMLResponse)
    async def buddy_page():
        return page_html

    @app.post("/screen")
    async def upload_screen(request: Request):
        data = await request.body()
        try:
            shot = store.put(data)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
        return {"ok": True, "size": list(shot.size)}

    @app.delete("/screen")
    async def stop_screen():
        store.clear()
        logger.info("Screen sharing stopped")
        return {"ok": True}
