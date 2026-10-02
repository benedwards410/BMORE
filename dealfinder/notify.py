"""Deliver alerts: always to stdout, optionally to a webhook (ntfy.sh, Slack, Discord, ...)."""

from __future__ import annotations

import os

import requests

from .sources.base import TIMEOUT


def send(message: str, webhook: str | None = None) -> None:
    print(message)
    url = webhook or os.environ.get("DEALFINDER_WEBHOOK_URL")
    if not url:
        return
    try:
        if "ntfy" in url:
            requests.post(url, data=message.encode(), timeout=TIMEOUT, headers={"Title": "Price alert"})
        elif "discord" in url:
            requests.post(url, json={"content": message}, timeout=TIMEOUT)
        else:  # Slack-compatible {"text": ...}
            requests.post(url, json={"text": message}, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"(webhook failed: {e})")
