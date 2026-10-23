"""Turn mailbox messages into Candidates. Pure logic over a MailClient so tests
can feed recorded JSON; GraphClient is the live implementation."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, Protocol

from ..config import Config
from ..filer import Candidate
from ..identify import find_mtx
from ..state import State, parse_iso, utcnow

log = logging.getLogger("kce_intake.outlook")

INTUIT_LINK_RE = re.compile(r"https://connect\.intuit\.com/[^\s\"'<>)]+", re.I)
INVOICE_NO_RE = re.compile(r"invoice\s*#?\s*([A-Za-z0-9-]+)", re.I)


class MailClient(Protocol):
    def list_messages_since(self, since: datetime) -> Iterator[dict]: ...
    def list_attachments(self, message_id: str) -> list[dict]: ...
    def download_attachment(self, message_id: str, attachment_id: str) -> bytes: ...


@dataclass
class LinkRequest:
    """A Beacon-style message whose invoice is only reachable through a link."""
    message: dict
    link: str
    invoice_number: str


def _sender_allowed(sender: str, allowlist: list[str]) -> bool:
    sender = (sender or "").lower()
    for rule in allowlist:
        rule = rule.lower().strip()
        if not rule:
            continue
        if "@" in rule:
            if sender == rule:
                return True
        elif sender.endswith("@" + rule) or sender.endswith("." + rule):
            return True
    return False


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text or "", re.I) for p in patterns)


def default_since(cfg: Config, state: State) -> datetime:
    watermark = state.mail_watermark
    if watermark:
        return watermark - timedelta(minutes=int(cfg.mail.get("overlapMinutes", 10)))
    return utcnow() - timedelta(days=int(cfg.mail.get("lookbackDaysFirstRun", 60)))


def find_candidates(cfg: Config, client: MailClient, state: State, since: datetime,
                    on_link: "callable | None" = None) -> Iterator[Candidate]:
    """Yield Candidates for every eligible attachment received after `since`.

    Beacon-style link-only messages are handed to `on_link(LinkRequest)`.
    State is updated as messages are consumed (seen attachments + watermark)."""
    mail = cfg.mail
    allow = list(mail.get("senderAllowlist", []))
    patterns = list(mail.get("filenamePatterns", []))
    skip = list(mail.get("skipAttachments", []))
    link_senders = list(mail.get("quickbooksLinkSenders", []))
    exts = cfg.input_extensions

    for msg in client.list_messages_since(since):
        received = parse_iso(msg["receivedDateTime"]) if msg.get("receivedDateTime") else utcnow()
        subject, body, sender = msg.get("subject", ""), msg.get("bodyText", ""), msg.get("sender", "")
        mtx_in_mail = bool(find_mtx(subject) or find_mtx(body))
        sender_ok = _sender_allowed(sender, allow)
        context = {
            "messageId": msg["id"],
            "internetMessageId": msg.get("internetMessageId"),
            "subject": subject,
            "sender": sender,
            "received": received,
            "bodyText": body,
        }

        attachments = client.list_attachments(msg["id"]) if (sender_ok or mtx_in_mail or _any(patterns, subject)) else []
        eligible = []
        for att in attachments:
            name = att.get("name") or ""
            if att.get("isInline") or att.get("odataType", "").endswith("itemAttachment"):
                continue
            if _any(skip, name):
                continue
            suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
            if suffix not in exts:
                continue
            if not (sender_ok or mtx_in_mail or _any(patterns, name)):
                continue
            eligible.append(att)

        for att in eligible:
            key = f"{msg['id']}/{att['id']}"
            if state.seen_attachment(key):
                continue
            try:
                data = client.download_attachment(msg["id"], att["id"])
            except Exception as exc:  # noqa: BLE001 - one bad attachment must not stop the sweep
                log.warning("could not download %r from %r: %s", att.get("name"), subject, exc)
                continue
            state.mark_attachment(key, received)
            yield Candidate(name=att["name"], data=data, source="outlook",
                            context=dict(context, attachmentId=att["id"]))

        if not eligible and on_link and _sender_allowed(sender, link_senders):
            link_match = INTUIT_LINK_RE.search(body or "")
            if link_match:
                key = f"{msg['id']}/link"
                if not state.seen_attachment(key):
                    number = INVOICE_NO_RE.search(subject or "")
                    on_link(LinkRequest(message=dict(msg, received=received), link=link_match.group(0),
                                        invoice_number=number.group(1) if number else "unknown"))
                    state.mark_attachment(key, received)

        state.advance_mail_watermark(received)
