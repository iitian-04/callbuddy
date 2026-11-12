"""Screen understanding: Call Buddy can look at your shared screen when you ask about it.

How screenshots reach the bot (no video over WebRTC):

  Call Buddy page (/buddy) --- every 2 s: small JPEG, HTTP POST /screen ---> ScreenStore

Why not WebRTC screen video? Decoding a full-resolution stream in Python froze the bot for
~30 s and the audio died (notes/failures.md #6). The browser now sends one JPEG every 2 s.

"Vision as a tool" (notes/failures.md #10): the main brain is a fast text model. When you ask
about your screen, it calls the tool `look_at_screen(question)`; only then is the newest
screenshot sent to a vision model, which answers the question in words. Before, we attached a
screenshot to EVERY turn: ~1,000 extra tokens each time on Groq's 8,000 tokens/minute free tier.
ScreenStore keeps ONLY the newest screenshot in memory; nothing is saved to disk.
"""

import base64
import io
import time
from dataclasses import dataclass

from loguru import logger
from PIL import Image

MAX_SIDE = 1024  # px; readable text, fewer image tokens (Groq free tier: 8,000 tokens/min)
MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # reject anything bigger than 3 MB
MAX_AGE_S = 10.0  # ignore a screenshot older than this (sharing probably stopped)

VISION_PROMPT = """You look at a screenshot of the user's screen and answer their question about it.
Be concise (at most 3 sentences unless asked for more). Quote exact text, names and numbers you
see. If the answer isn't visible on the screenshot, say exactly that. Don't read out passwords,
codes, or card/bank numbers."""


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


LOOK_AT_SCREEN_SPEC = {
    "name": "look_at_screen",
    "description": "Look at the user's shared screen right now and answer a question about it. "
    "Use this whenever the user refers to their screen or says things like 'this', 'here', "
    "'what's this error', 'summarize this page'.",
    "properties": {
        "question": {"type": "string", "description": "What to find out from the screen, in full"},
    },
    "required": [],  # checked in code: a missing field makes Groq reject the whole reply
}


async def look_at_screen(client, model: str, question: str, store: "ScreenStore", temperature: float = 0.2) -> dict:
    """Ask the vision model about the newest screenshot. `client` is an AsyncOpenAI."""
    shot = store.fresh()
    if shot is None:
        return {"error": "No screen is being shared. Ask the user to click the blue 'Share screen' "
                "button at the top of the page and pick a window."}
    question = (question or "").strip() or "Describe what is on the screen."
    url = "data:image/jpeg;base64," + base64.b64encode(shot.jpeg).decode()
    try:
        r = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            reasoning_effort="none",
            messages=[
                {"role": "system", "content": VISION_PROMPT},
                {"role": "user", "content": [{"type": "text", "text": question},
                                             {"type": "image_url", "image_url": {"url": url}}]},
            ],
        )
    except Exception as e:
        logger.warning(f"look_at_screen failed: {e}")
        return {"error": str(e)[:300]}
    answer = (r.choices[0].message.content or "").strip()
    logger.info(f"look_at_screen({question!r}) -> {len(answer)} chars")
    return {"seen_on_screen": answer}


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
