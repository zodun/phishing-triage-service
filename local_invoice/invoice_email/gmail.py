"""Read-only Gmail access for a local, single-user application."""

import base64
import os
import re
import tempfile
import time
from io import BytesIO
from urllib.parse import unquote, urlsplit
from dataclasses import dataclass, field
from html.parser import HTMLParser
from email.message import Message
from pathlib import Path

from .pdf import MAX_PDF_BYTES

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_BODY_CHARS = 30_000


@dataclass
class Attachment:
    filename: str
    attachment_id: str = ""
    data: str = ""
    size: int = 0


@dataclass
class MailLink:
    target: str
    text: str = ""


@dataclass
class MailMessage:
    id: str
    subject: str = ""
    sender: str = ""
    date: str = ""
    body: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str = ""
    links: list[MailLink] = field(default_factory=list)
    html_text: str = ""
    labels: list[str] = field(default_factory=list)
    attachment_names: list[str] = field(default_factory=list)
    scan_complete: bool = True


def pdf_links(message):
    """Recognize direct PDF URLs without visiting untrusted destinations."""
    targets = [link.target for link in message.links]
    targets.extend(re.findall(r'https?://[^\s<>"\']+', message.body, re.I))
    result = []
    for target in targets:
        target = target.rstrip(".,);]")
        try:
            parts = urlsplit(target)
            if (
                parts.scheme.lower() in ("http", "https")
                and parts.hostname
                and unquote(parts.path).lower().endswith(".pdf")
                and target not in result
            ):
                result.append(target)
        except ValueError:
            continue
    return result


def decode_data(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.hidden = 0
        self.links = []
        self.active_link = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.active_link = MailLink(dict(attrs).get("href") or "")
            self.links.append(self.active_link)
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("br", "p", "div", "tr"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag == "a":
            self.active_link = None
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
            if self.active_link:
                self.active_link.text += data


def parse_message(raw: dict, body_loader=None) -> MailMessage:
    payload = raw.get("payload", {})
    headers = {h["name"].lower(): h.get("value", "") for h in payload.get("headers", [])}
    message = MailMessage(
        raw["id"], headers.get("subject", "(No subject)"), headers.get("from", ""), headers.get("date", "")
    )
    message.reply_to = headers.get("reply-to", "")
    message.labels = raw.get("labelIds", [])
    plain, html = [], []

    def walk(part):
        mime = part.get("mimeType", "").lower()
        filename = part.get("filename", "")
        if filename:
            message.attachment_names.append(filename)
        body = part.get("body", {})
        if mime == "application/pdf" or filename.lower().endswith(".pdf"):
            message.attachments.append(
                Attachment(
                    filename or "attachment.pdf",
                    body.get("attachmentId", ""),
                    body.get("data", ""),
                    body.get("size", 0),
                )
            )
            return
        if not filename and mime in ("text/plain", "text/html"):
            data = body.get("data", "")
            if not data and body.get("attachmentId") and body_loader:
                data = body_loader(body["attachmentId"])
            if data:
                mime_headers = Message()
                for header in part.get("headers", []):
                    if header.get("name", "").lower() == "content-type":
                        mime_headers["Content-Type"] = header.get("value", "")
                        break
                charset = mime_headers.get_content_charset() or "utf-8"
                try:
                    decoded = decode_data(data).decode(charset, errors="replace")
                except LookupError:
                    decoded = decode_data(data).decode("utf-8", errors="replace")
                (plain if mime == "text/plain" else html).append(decoded)
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    parser = _HTMLText()
    parser.feed("\n".join(html))
    message.html_text = "".join(parser.text).strip()
    message.links = parser.links[:200]
    message.scan_complete = len(parser.links) <= 200 and len(message.html_text) <= MAX_BODY_CHARS
    message.body = "\n\n".join(plain) if plain else message.html_text
    message.html_text = message.html_text[:MAX_BODY_CHARS]
    if len(message.body) > MAX_BODY_CHARS:
        message.scan_complete = False
        message.body = message.body[:MAX_BODY_CHARS] + "\n[Email body truncated; invoice PDFs are read separately.]"
    return message


def _configured_path(name, default):
    value = Path(os.getenv(name, default)).expanduser()
    return value if value.is_absolute() else ROOT / value


def _save_token(path, credentials):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".token-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(credentials.to_json())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def connect_gmail(*, interactive=False, on_authorization=None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2

    token_path = _configured_path("GMAIL_TOKEN_FILE", ".credentials/gmail-token.json")
    client_path = _configured_path("GMAIL_CLIENT_SECRET_FILE", ".credentials/gmail-client.json")
    credentials = None
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                _save_token(token_path, credentials)
        except Exception:
            if not interactive:
                raise ValueError("Gmail access has expired or could not refresh. Use Connect Gmail again.") from None
            credentials = None
    if not credentials or not credentials.valid:
        if not interactive:
            raise ValueError("Connect Gmail first.")
        from .settings import read_google_client

        flow = InstalledAppFlow.from_client_config(read_google_client(client_path), SCOPES)
        if on_authorization:
            authorization_url = flow.authorization_url

            def publish_authorization(**kwargs):
                url, state = authorization_url(**kwargs)
                on_authorization(url)
                return url, state

            flow.authorization_url = publish_authorization
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            timeout_seconds=180,
            open_browser=on_authorization is None,
            authorization_prompt_message="Complete Gmail sign-in in your browser.",
            success_message="Google sign-in response received. Return to Invoice Email to check your connection.",
        )
        _save_token(token_path, credentials)
    http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
    return GmailMailbox(build("gmail", "v1", http=http, cache_discovery=False))


class GmailMailbox:
    def __init__(self, service):
        self.service = service
        self._last_request = 0.0

    def _execute(self, request):
        # Keep sequential scanning from bursting through Google's request quota.
        pause = 0.2 - (time.monotonic() - self._last_request)
        if pause > 0:
            time.sleep(pause)
        try:
            return request.execute(num_retries=3)
        finally:
            self._last_request = time.monotonic()

    def profile(self):
        return self.service.users().getProfile(userId="me").execute()["emailAddress"]

    def search(self, query: str, limit: int = 20):
        limit = max(1, min(int(limit), 50))
        messages = self.service.users().messages()
        result, token = [], None
        seen = set()
        while len(result) < limit:
            # Search the requested scope, then inspect individual messages. Gmail
            # search matches alone do not establish that a message has a PDF.
            candidates = "{has:attachment pdf}"
            args = dict(
                userId="me", q=f"({query.strip()}) {candidates}" if query.strip() else candidates, maxResults=50
            )
            if token:
                args["pageToken"] = token
            page = self._execute(messages.list(**args))
            for item in page.get("messages", []):
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                message = self.get_message(item["id"])
                if pdf_links(message) or self._has_valid_pdf(message):
                    result.append(message)
                if len(result) == limit:
                    break
            token = page.get("nextPageToken")
            if not token:
                break
        return result

    def _has_valid_pdf(self, message):
        from pypdf import PdfReader

        for attachment in message.attachments:
            # Transport failures must surface rather than silently undercount.
            try:
                data = self.download_attachment(message.id, attachment)
            except ValueError:
                continue
            if not data.lstrip().startswith(b"%PDF-"):
                continue
            try:
                PdfReader(BytesIO(data))
            except Exception:
                continue
            return True
        return False

    def get_message(self, message_id):
        raw = self._execute(self.service.users().messages().get(userId="me", id=message_id, format="full"))
        return parse_message(raw, lambda attachment_id: self._attachment_data(message_id, attachment_id))

    def _attachment_data(self, message_id, attachment_id):
        return self._execute(
            self.service.users().messages().attachments().get(userId="me", messageId=message_id, id=attachment_id)
        )["data"]

    def download_attachment(self, message_id, attachment):
        if attachment.size > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds the 15 MB attachment limit.")
        data = attachment.data
        if not data and attachment.attachment_id:
            data = self._attachment_data(message_id, attachment.attachment_id)
        if len(data) > (MAX_PDF_BYTES + 2) // 3 * 4:
            raise ValueError("PDF exceeds the 15 MB attachment limit.")
        decoded = decode_data(data)
        if len(decoded) > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds the 15 MB attachment limit.")
        return decoded
