"""Screen understanding (S1): let the LLM see the latest frame of your shared screen.

How it works (two small Pipecat processors):

  transport.input() -> [ScreenBuffer] -> STT -> user aggregator -> [ScreenInjector] -> LLM

- ScreenBuffer keeps ONLY the newest screen frame in memory (nothing is saved to disk)
  and drops the video frames from the pipeline, so audio processors never see them.
- ScreenInjector runs right before the LLM. Each time you finish speaking, it shrinks the
  newest frame to a JPEG and adds it to the conversation as "what's on my screen now".
  Older screenshots are replaced by a short text note, so the context (and the cost of
  each request) doesn't grow with every turn.
"""

import io
import time

from loguru import logger
from PIL import Image
from pipecat.frames.frames import Frame, InputImageRawFrame, LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

SCREEN_SOURCE = "screenVideo"  # the source name SmallWebRTC uses for screen sharing
MAX_SIDE = 1280  # px; big enough to read text, small enough to keep requests fast
MAX_AGE_S = 15.0  # ignore a frame older than this (screen sharing probably stopped)
OLD_SCREENSHOT_NOTE = "[older screenshot removed]"
SCREENSHOT_TEXT = "This is my screen right now."


def to_jpeg(image: bytes, size: tuple[int, int], fmt: str | None) -> tuple[bytes, tuple[int, int]]:
    """Raw RGB/RGBA bytes -> downscaled JPEG bytes and the new size."""
    img = Image.frombytes(fmt or "RGB", size, image).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # keeps aspect ratio, never upscales
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=75)
    return out.getvalue(), img.size


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


async def attach_screenshot(context, shot: InputImageRawFrame) -> None:
    """Replace older screenshots in `context` with a note, then add `shot` as the newest."""
    context.set_messages(strip_old_screenshots(context.get_messages()))
    jpeg, size = to_jpeg(shot.image, shot.size, shot.format)
    await context.add_image_frame_message(format="image/jpeg", size=size, image=jpeg, text=SCREENSHOT_TEXT)
    logger.debug(f"Attached screenshot {size[0]}x{size[1]}, {len(jpeg) // 1024} KB")


class ScreenBuffer(FrameProcessor):
    """Remembers the newest screen frame; removes video frames from the pipeline."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.latest: InputImageRawFrame | None = None
        self.latest_at = 0.0

    def fresh_frame(self, now: float | None = None) -> InputImageRawFrame | None:
        now = time.monotonic() if now is None else now
        if self.latest is not None and now - self.latest_at <= MAX_AGE_S:
            return self.latest
        return None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputImageRawFrame):
            if frame.transport_source == SCREEN_SOURCE:
                if self.latest is None:
                    logger.info("Screen sharing: first frame received")
                self.latest, self.latest_at = frame, time.monotonic()
            return  # video never goes further down the pipeline
        await self.push_frame(frame, direction)


class ScreenInjector(FrameProcessor):
    """Adds the newest screenshot to the context just before each LLM request."""

    def __init__(self, buffer: ScreenBuffer, **kwargs):
        super().__init__(**kwargs)
        self._buffer = buffer

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            shot = self._buffer.fresh_frame()
            if shot is not None:
                await attach_screenshot(frame.context, shot)
        await self.push_frame(frame, direction)
