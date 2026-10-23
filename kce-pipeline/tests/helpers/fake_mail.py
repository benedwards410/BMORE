"""MailClient fed from plain dicts: {"id", "subject", "receivedDateTime", "sender",
"bodyText", "attachments": [{"id", "name", "contentType", "isInline", "data"}]}."""
from __future__ import annotations

from datetime import datetime


class FakeMailClient:
    def __init__(self, messages: list[dict]):
        self.messages = messages
        self.downloads: list[tuple[str, str]] = []

    def list_messages_since(self, since: datetime):
        for msg in self.messages:
            yield {k: v for k, v in msg.items() if k != "attachments"}

    def list_attachments(self, message_id: str) -> list[dict]:
        for msg in self.messages:
            if msg["id"] == message_id:
                return [{k: v for k, v in att.items() if k != "data"} for att in msg.get("attachments", [])]
        return []

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        self.downloads.append((message_id, attachment_id))
        for msg in self.messages:
            if msg["id"] == message_id:
                for att in msg.get("attachments", []):
                    if att["id"] == attachment_id:
                        return att["data"]
        raise KeyError(attachment_id)
