"""Gmail tests with a fake Gmail API service (offline; never touches a real account)."""

import asyncio
import base64
import email

from callbuddy import gmail as gm


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def full_message(mid="m1", body_plain=None, body_html=None):
    parts = []
    if body_plain:
        parts.append({"mimeType": "text/plain", "body": {"data": b64(body_plain)}})
    if body_html:
        parts.append({"mimeType": "text/html", "body": {"data": b64(body_html)}})
    return {
        "id": mid, "threadId": "t1", "snippet": "Hi &amp; hello", "labelIds": ["INBOX", "UNREAD"],
        "payload": {
            "mimeType": "multipart/alternative", "parts": parts,
            "headers": [
                {"name": "From", "value": "QUASA <news@quasa.io>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "Token burn"},
                {"name": "Date", "value": "Wed, 12 Nov 2026 10:00:00 +0000"},
                {"name": "Message-ID", "value": "<abc@quasa.io>"},
            ],
        },
    }


class Exec:
    def __init__(self, value, log=None, call=None):
        self.value, self.log, self.call = value, log, call

    def execute(self):
        if self.log is not None:
            self.log.append(self.call)
        return self.value


class FakeService:
    """Mimics service.users().messages()/drafts() just enough for the Gmail class."""

    def __init__(self, messages):
        self.messages_by_id = {m["id"]: m for m in messages}
        self.calls = []

    def users(self):
        return self

    def messages(self):
        return self

    def drafts(self):
        return self

    def list(self, userId, q, maxResults):
        self.calls.append(("list", q, maxResults))
        ids = list(self.messages_by_id)[:maxResults]
        return Exec({"messages": [{"id": i} for i in ids]})

    def get(self, userId, id, format, metadataHeaders=None):
        return Exec(self.messages_by_id[id])

    def create(self, userId, body):
        return Exec({"id": "d1"}, self.calls, ("create", body))


def test_extract_body_prefers_plain_then_html():
    assert gm.extract_body(full_message(body_plain="Hello there", body_html="<b>x</b>")["payload"]) == "Hello there"
    text = gm.extract_body(full_message(body_html="<p>Hi&nbsp;you</p><script>bad()</script><br>Bye")["payload"])
    assert "Hi" in text and "Bye" in text and "bad()" not in text and "<" not in text


def test_search_caps_results_and_summarizes():
    svc = FakeService([full_message(f"m{i}", body_plain="x") for i in range(9)])
    results = gm.Gmail(svc).search("from:quasa", max_results=50)
    assert len(results) == gm.MAX_RESULTS and svc.calls[0] == ("list", "from:quasa", gm.MAX_RESULTS)
    first = results[0]
    assert first["subject"] == "Token burn" and first["unread"] is True and first["snippet"] == "Hi & hello"


def test_read_cuts_long_bodies():
    svc = FakeService([full_message(body_plain="a" * 5000)])
    r = gm.Gmail(svc).read("m1")
    assert r["subject"] == "Token burn" and len(r["body"]) < gm.MAX_BODY_CHARS + 20 and r["body"].endswith("[...cut]")


def test_reply_draft_threads_and_never_sends():
    svc = FakeService([full_message(body_plain="original")])
    out = asyncio.run(gm.run_tool(gm.Gmail(svc), "create_draft",
                                  {"to": "news@quasa.io", "subject": "Re: Token burn", "body": "Thanks!", "reply_to_email_id": "m1"}))
    assert out == {"saved_as_draft": True, "draft_id": "d1", "sent": False}
    body = [c for c in svc.calls if c[0] == "create"][0][1]
    assert body["message"]["threadId"] == "t1"
    raw = email.message_from_bytes(base64.urlsafe_b64decode(body["message"]["raw"]))
    assert raw["In-Reply-To"] == "<abc@quasa.io>" and raw["To"] == "news@quasa.io"
    assert "Thanks!" in raw.get_payload()


def test_gmail_class_has_no_send():
    # Safety: Call Buddy can only draft. There must be no way to send or delete mail.
    names = [n for n in dir(gm.Gmail) if not n.startswith("_")]
    assert not any(w in n for n in names for w in ("send", "delete", "trash"))
    assert {t["name"] for t in gm.TOOL_SPECS} == {"search_emails", "read_email", "create_draft"}


def test_tool_errors_are_returned_not_raised():
    class Broken:
        def users(self):
            raise RuntimeError("token expired")

    g = gm.Gmail.__new__(gm.Gmail)
    g._s = Broken()
    out = asyncio.run(gm.run_tool(g, "read_email", {"email_id": "x"}))
    assert "error" in out


def test_not_connected_without_token(tmp_path):
    assert gm.load_credentials(tmp_path / "missing.json") is None
