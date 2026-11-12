"""Gmail for Call Buddy: search and read your mail, and save reply DRAFTS (never sends).

One-time setup (see README "Gmail"):
  1. Put your Google OAuth "Desktop app" client file at secrets/google_credentials.json
  2. Run:  uv run python -m callbuddy.gmail auth   (a Google page opens, click Allow)
     This saves secrets/google_token.json on this Mac only. secrets/ is gitignored.

Concepts:
- OAuth: you log in on Google's own page and approve what this app may do ("scopes").
  The app never sees your password; it gets a token it can refresh.
- Scopes: gmail.readonly (search/read) and gmail.compose (create drafts). Compose would also
  allow sending, so this code simply has no send function, and Call Buddy can't send mail.
- Tools ("function calling"): the LLM can't touch Gmail itself. We describe a few functions
  (search_emails, read_email, create_draft); the LLM asks for one, our code runs it and gives
  the result back, then the LLM answers you out loud.
"""

import asyncio
import base64
import html
import os
import re
import sys
from email.message import EmailMessage
from pathlib import Path

from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
SECRETS_DIR = Path("secrets")
CREDENTIALS_FILE = SECRETS_DIR / "google_credentials.json"
TOKEN_FILE = SECRETS_DIR / "google_token.json"

MAX_RESULTS = 5  # emails per search (Groq free tier: ~8,000 tokens/min)
MAX_BODY_CHARS = 1500  # characters of an email body given to the LLM
SNIPPET_CHARS = 120  # characters of preview per search result


# --- auth ------------------------------------------------------------------------------


def load_credentials(token_file: Path = TOKEN_FILE):
    """Saved credentials (refreshed if expired), or None if Gmail isn't set up yet."""
    if not token_file.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds, token_file)
    return creds if creds.valid else None


def _save_token(creds, token_file: Path = TOKEN_FILE) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    os.chmod(token_file, 0o600)  # readable by you only


def authorize() -> None:
    """Open Google's consent page in the browser and save the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS_FILE.exists():
        sys.exit(f"Missing {CREDENTIALS_FILE}. Download your OAuth Desktop client JSON there first.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    print(f"Gmail connected. Token saved to {TOKEN_FILE} (keep it private, it's gitignored).")


# --- parsing Gmail's message format (pure, easy to test) -------------------------------


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def extract_body(payload: dict) -> str:
    """Plain-text body of a Gmail message payload (falls back to HTML converted to text)."""
    plain, htmls = [], []

    def walk(part: dict):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_b64(data))
        elif data and mime == "text/html":
            htmls.append(_b64(data))
        for p in part.get("parts", []) or []:
            walk(p)

    walk(payload)
    text = "\n".join(plain).strip() or html_to_text("\n".join(htmls))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def summarize_message(msg: dict) -> dict:
    """Short form used in search results."""
    h = headers(msg.get("payload", {}))
    return {
        "id": msg["id"],
        "from": h.get("from", ""),
        "subject": h.get("subject", ""),
        "date": h.get("date", ""),
        "snippet": html.unescape(msg.get("snippet", ""))[:SNIPPET_CHARS],
        "unread": "UNREAD" in msg.get("labelIds", []),
    }


def build_draft(to: str, subject: str, body: str, reply_to: dict | None = None) -> dict:
    """Gmail API draft resource. `reply_to` is a full message we're replying to (optional)."""
    m = EmailMessage()
    m["To"] = to
    m["Subject"] = subject
    m.set_content(body)
    draft: dict = {"message": {}}
    if reply_to:
        h = headers(reply_to.get("payload", {}))
        if h.get("message-id"):
            m["In-Reply-To"] = h["message-id"]
            m["References"] = h["message-id"]
        draft["message"]["threadId"] = reply_to.get("threadId")
    draft["message"]["raw"] = base64.urlsafe_b64encode(m.as_bytes()).decode()
    return draft


# --- the Gmail client -----------------------------------------------------------------------


class Gmail:
    """Thin wrapper over the Gmail API service. Blocking; call from a thread."""

    def __init__(self, service):
        self._s = service.users()

    @classmethod
    def from_saved_token(cls) -> "Gmail | None":
        creds = load_credentials()
        if creds is None:
            return None
        from googleapiclient.discovery import build

        return cls(build("gmail", "v1", credentials=creds, cache_discovery=False))

    def search(self, query: str, max_results: int = MAX_RESULTS) -> list[dict]:
        max_results = max(1, min(int(max_results), MAX_RESULTS))
        res = self._s.messages().list(userId="me", q=query, maxResults=max_results).execute()
        out = []
        for ref in res.get("messages", []):
            msg = self._s.messages().get(
                userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            out.append(summarize_message(msg))
        return out

    def get_full(self, email_id: str) -> dict:
        return self._s.messages().get(userId="me", id=email_id, format="full").execute()

    def read(self, email_id: str) -> dict:
        msg = self.get_full(email_id)
        h = headers(msg.get("payload", {}))
        body = extract_body(msg.get("payload", {}))
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + " [...cut]"
        return {"id": email_id, "from": h.get("from", ""), "to": h.get("to", ""),
                "subject": h.get("subject", ""), "date": h.get("date", ""), "body": body}

    def create_draft(self, to: str, subject: str, body: str, reply_to_email_id: str | None = None) -> str:
        reply_to = self.get_full(reply_to_email_id) if reply_to_email_id else None
        d = self._s.drafts().create(userId="me", body=build_draft(to, subject, body, reply_to)).execute()
        return d["id"]


# --- LLM tools --------------------------------------------------------------------------------

TOOL_SPECS = [
    {
        "name": "search_emails",
        "description": "Search the user's Gmail. Returns up to 5 emails (id, from, subject, date, snippet, unread). "
        "Use Gmail search syntax, e.g. 'is:unread newer_than:2d', 'from:quasa', 'subject:invoice newer_than:7d'.",
        "properties": {
            "query": {"type": "string", "description": "Gmail search query"},
            "max_results": {"type": "integer", "description": "1 to 5, default 5"},
        },
        "required": [],
    },
    {
        "name": "read_email",
        "description": "Read one email by id (from search_emails). Returns from, to, subject, date and the body text.",
        "properties": {"email_id": {"type": "string", "description": "id from search_emails"}},
        "required": [],
    },
    {
        "name": "create_draft",
        "description": "Save an email DRAFT in the user's Gmail Drafts folder. It is NOT sent; the user sends it "
        "themselves. Only call this after reading the draft to the user and they said yes.",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "Plain-text email body"},
            "reply_to_email_id": {"type": "string", "description": "Id of the email being replied to, if any"},
        },
        "required": [],
    },
]


REQUIRED_ARGS = {"search_emails": ["query"], "read_email": ["email_id"], "create_draft": ["to", "subject", "body"]}


async def run_tool(gmail: Gmail, name: str, args: dict) -> dict:
    """Run one Gmail tool in a worker thread (Google's client is blocking)."""
    # Checked here instead of in the JSON schema: if Groq sees a missing required field it rejects
    # the whole reply and the bot goes silent; this way the model gets a hint and tries again.
    missing = [a for a in REQUIRED_ARGS.get(name, []) if not str(args.get(a) or "").strip()]
    if missing:
        return {"error": f"missing {', '.join(missing)}; call {name} again with it filled in"}
    try:
        if name == "search_emails":
            emails = await asyncio.to_thread(gmail.search, args["query"], args.get("max_results", MAX_RESULTS))
            logger.info(f"Gmail search {args['query']!r}: {len(emails)} result(s)")
            return {"emails": emails} if emails else {"emails": [], "note": "No emails matched."}
        if name == "read_email":
            return await asyncio.to_thread(gmail.read, args["email_id"])
        if name == "create_draft":
            draft_id = await asyncio.to_thread(
                gmail.create_draft, args["to"], args["subject"], args["body"], args.get("reply_to_email_id")
            )
            logger.info("Gmail draft saved (not sent)")
            return {"saved_as_draft": True, "draft_id": draft_id, "sent": False}
        return {"error": f"unknown tool {name}"}
    except Exception as e:  # tell the LLM, so it can say what went wrong instead of hanging
        logger.warning(f"Gmail tool {name} failed: {e}")
        return {"error": str(e)[:300]}


def register_gmail_tools(llm, gmail: Gmail):
    """Register the tools on a Pipecat LLM service and return a ToolsSchema for the context."""
    from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
    from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema

    for spec in TOOL_SPECS:

        async def handler(params, _name=spec["name"]):
            await params.result_callback(await run_tool(gmail, _name, dict(params.arguments)))

        llm.register_function(spec["name"], handler)
    return ToolsSchema(standard_tools=[FunctionSchema(**spec) for spec in TOOL_SPECS])


if __name__ == "__main__":
    if sys.argv[1:] == ["auth"]:
        authorize()
    elif sys.argv[1:] == ["test"]:
        g = Gmail.from_saved_token()
        if g is None:
            sys.exit("Gmail not connected. Run: uv run python -m callbuddy.gmail auth")
        for e in g.search("newer_than:3d", 3):
            print(f"- {e['date'][:16]} | {e['from'][:30]} | {e['subject'][:60]}")
    else:
        sys.exit("Usage: uv run python -m callbuddy.gmail auth | test")
