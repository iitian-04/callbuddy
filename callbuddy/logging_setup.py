"""Logging setup. Pipecat already logs with loguru, so we configure loguru once here.

Safety net: a "patcher" runs on every log line before it is written and replaces any
API key value (or anything shaped like a Groq key) with [REDACTED].
"""

import re
import sys

from loguru import logger

# Groq keys start with "gsk_". Deepgram keys are 40 hex characters.
_KEY_PATTERNS = [re.compile(r"gsk_[A-Za-z0-9]{10,}"), re.compile(r"\b[a-f0-9]{40}\b")]


def redact(text: str, secrets: list[str]) -> str:
    """Return text with every secret (and anything key-shaped) replaced."""
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    for pattern in _KEY_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def setup_logging(level: str = "INFO", secrets: list[str] | None = None) -> None:
    secret_values = secrets or []

    def _patch(record):
        record["message"] = redact(record["message"], secret_values)

    logger.remove()  # drop loguru's default handler so we control the format
    logger.configure(patcher=_patch)
    logger.add(sys.stderr, level=level.upper())
