"""Drop "transcriptions" that are only noise (".", "...", "-") before they reach the conversation.

Seen 2026-11-12: speech-to-text produced "." from background noise; that counted as a new user
turn and cancelled the answer the bot was about to give (notes/failures.md #10).
"""

import re

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


def is_noise(text: str) -> bool:
    """True if the text has no letters or digits at all."""
    return not re.search(r"\w", text or "")


class NoiseFilter(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and is_noise(frame.text):
            return  # swallow it
        await self.push_frame(frame, direction)
