"""Shared plumbing for price sources."""

from __future__ import annotations

import os
from typing import Protocol

import requests

from ..models import Offer, PriceStats

USER_AGENT = "dealfinder/0.1 (+personal price comparison; low volume)"
TIMEOUT = 15


class SourceError(RuntimeError):
    pass


class Source(Protocol):
    name: str

    def available(self) -> bool:
        """True when credentials/config needed by this source are present."""

    def search(self, query: str, limit: int = 10) -> list[Offer]:
        """Free-text search."""

    def lookup(self, *, gtin: str | None = None, model: str | None = None) -> list[Offer]:
        """Exact lookup by GTIN/UPC or model number. Return [] if unsupported."""


class HistorySource(Protocol):
    def history(self, offer: Offer) -> PriceStats | None: ...


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.headers["Accept"] = "application/json, text/html;q=0.9"
    return s


def env(name: str) -> str | None:
    v = os.environ.get(name, "").strip()
    return v or None


def get_json(s: requests.Session, url: str, **kw) -> dict:
    try:
        r = s.get(url, timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise SourceError(f"{url.split('?')[0]}: {e}") from e
    if r.status_code == 429:
        raise SourceError(f"{url.split('?')[0]}: rate limited (HTTP 429) — slow down or wait")
    if r.status_code >= 400:
        raise SourceError(f"{url.split('?')[0]}: HTTP {r.status_code} {r.text[:200]}")
    return r.json()
