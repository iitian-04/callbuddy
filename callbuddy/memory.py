"""Session memory (S2): Call Buddy keeps short notes about what you're working on.

Concepts:
- The LLM's context is its short-term memory. It grows every turn and each request gets
  slower and more expensive, so we keep only the last few turns there.
- "Notes" are a compact long-term memory: a few bullet points (task, app/file, findings,
  open questions), rewritten every few turns by a small, fast text model from the recent
  conversation. They are put at the top of the context, so the bot still knows what you were
  doing after old turns have been trimmed away.
- When you disconnect, the notes become a short session summary saved to `sessions/`
  (gitignored: it may contain things from your screen). The next session starts with the
  latest summary, so "what was I doing yesterday?" works.

Nothing here sends screenshots anywhere: the notes model only sees the text of the chat.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from loguru import logger
from pipecat.frames.frames import Frame, LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

NOTES_MARKER = "[Call Buddy notes]"
UPDATE_EVERY_TURNS = 3  # rewrite the notes after this many user turns
KEEP_LAST_MESSAGES = 16  # older chat messages are trimmed (the notes keep the gist)
MAX_NOTES = 8
SESSIONS_DIR = Path("sessions")

NOTES_PROMPT = f"""You keep short working notes for Call Buddy, a voice assistant that can see the user's screen.
Update the notes from the conversation below. Keep only what helps later: the user's current task,
the app/file/page they are on, key facts found, decisions, and open questions or next steps.
Never copy passwords, card or bank numbers, or other secrets. At most {MAX_NOTES} short bullets.
Reply with JSON only: {{"task": "<one line>", "notes": ["...", "..."]}}"""

SUMMARY_PROMPT = """Write a short summary of this work session for the user to read later.
3 to 5 plain lines: what they worked on, what was found or decided, and what's left to do.
Never include passwords, card or bank numbers, or other secrets. No markdown headings."""


# --- pure helpers (easy to test) ----------------------------------------------------


def message_text(message: dict) -> str:
    """Text of a chat message; image parts are skipped."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text").strip()
    return ""


def transcript(messages: list, limit: int = 30) -> str:
    """Last `limit` user/assistant messages as 'User: ... / Buddy: ...' lines."""
    lines = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        text = message_text(m)
        if text and not text.startswith(NOTES_MARKER):
            lines.append(f"{'User' if m['role'] == 'user' else 'Buddy'}: {text}")
    return "\n".join(lines[-limit:])


def render_notes(task: str, notes: list[str], last_session: str = "") -> str:
    parts = [NOTES_MARKER]
    if last_session:
        parts.append(f"Summary of the user's previous session:\n{last_session}")
    if task:
        parts.append(f"Current task: {task}")
    if notes:
        parts.append("Notes so far:\n" + "\n".join(f"- {n}" for n in notes[:MAX_NOTES]))
    parts.append("Use these notes to remember what the user is doing; don't read them out unless asked.")
    return "\n".join(parts)


def apply_memory(messages: list, notes_text: str, keep_last: int = KEEP_LAST_MESSAGES) -> list:
    """Old notes out, trim to the last `keep_last` messages, fresh notes in at the top.

    The trimmed list never starts with an assistant message or a tool result, so the
    conversation still reads naturally.
    """
    rest = [m for m in messages if not (isinstance(m, dict) and message_text(m).startswith(NOTES_MARKER))]
    if len(rest) > keep_last:
        rest = rest[-keep_last:]
        while rest and isinstance(rest[0], dict) and rest[0].get("role") != "user":
            rest = rest[1:]
    return [{"role": "system", "content": notes_text}, *rest]


def parse_notes(text: str) -> tuple[str, list[str]]:
    """Parse the notes model's JSON. Raises ValueError if it isn't the expected shape."""
    try:
        data = json.loads(text)
        task = str(data.get("task", "")).strip()
        notes = [str(n).strip() for n in data.get("notes", []) if str(n).strip()]
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        raise ValueError(f"bad notes JSON: {e}") from None
    return task, notes[:MAX_NOTES]


def latest_summary(sessions_dir: Path = SESSIONS_DIR) -> str:
    files = sorted(sessions_dir.glob("*.md")) if sessions_dir.exists() else []
    return files[-1].read_text().strip() if files else ""


def save_summary(summary: str, sessions_dir: Path = SESSIONS_DIR, now: datetime | None = None) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{(now or datetime.now()).strftime('%Y-%m-%d_%H-%M-%S')}.md"
    path.write_text(summary.strip() + "\n")
    return path


# --- the memory itself ----------------------------------------------------------------


class SessionMemory:
    """Holds the notes and talks to the small notes model. `client` is an AsyncOpenAI."""

    def __init__(self, client, model: str, sessions_dir: Path = SESSIONS_DIR):
        self._client = client
        self._model = model
        self.sessions_dir = sessions_dir
        self.task = ""
        self.notes: list[str] = []
        self.last_session = latest_summary(sessions_dir)
        self.user_turns = 0
        self._updating: asyncio.Task | None = None

    def text(self) -> str:
        return render_notes(self.task, self.notes, self.last_session)

    async def update(self, messages: list) -> None:
        convo = transcript(messages)
        if not convo:
            return
        current = json.dumps({"task": self.task, "notes": self.notes})
        try:
            r = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": NOTES_PROMPT},
                    {"role": "user", "content": f"Current notes: {current}\n\nConversation:\n{convo}"},
                ],
            )
            self.task, self.notes = parse_notes(r.choices[0].message.content or "")
            logger.info(f"Memory updated: task={self.task!r}, {len(self.notes)} notes")
        except Exception as e:  # memory must never break the conversation
            logger.warning(f"Memory update failed: {e}")

    def maybe_update_in_background(self, messages: list) -> None:
        """Every few user turns, refresh the notes without making the reply wait."""
        self.user_turns += 1
        if self.user_turns % UPDATE_EVERY_TURNS == 0 and not (self._updating and not self._updating.done()):
            self._updating = asyncio.create_task(self.update(list(messages)))

    async def finish(self, messages: list) -> Path | None:
        """Summarize the session and save it to sessions/. Returns the file, or None."""
        convo = transcript(messages, limit=60)
        if not convo:
            return None
        try:
            r = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": f"Notes: {self.text()}\n\nConversation:\n{convo}"},
                ],
            )
            summary = (r.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"Session summary failed: {e}")
            return None
        if not summary:
            return None
        path = save_summary(summary, self.sessions_dir)
        logger.info(f"Session summary saved to {path}")
        return path


class MemoryProcessor(FrameProcessor):
    """Before each LLM call: put the notes at the top, trim old turns, maybe refresh notes."""

    def __init__(self, memory: SessionMemory, **kwargs):
        super().__init__(**kwargs)
        self._memory = memory

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame) and not getattr(frame, "speculation", False):
            ctx = frame.context
            messages = ctx.get_messages()
            self._memory.maybe_update_in_background(messages)
            ctx.set_messages(apply_memory(messages, self._memory.text()))
        await self.push_frame(frame, direction)
