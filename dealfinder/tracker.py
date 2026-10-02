"""Price tracking: remember prices over time in SQLite and raise alerts on real drops."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .models import Offer, PriceStats

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    gtin TEXT,
    model TEXT,
    target_price REAL,
    purchased_retailer TEXT,
    purchased_price REAL,
    purchased_on TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_urls (
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    PRIMARY KEY (item_id, url)
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    retailer TEXT NOT NULL,
    url TEXT NOT NULL,
    price REAL NOT NULL,
    total REAL NOT NULL,
    condition TEXT NOT NULL,
    sold_by_retailer INTEGER NOT NULL,
    in_stock INTEGER,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS obs_item_url ON observations(item_id, url, observed_at);
"""

# A drop smaller than this between two checks is noise, not news.
DROP_ALERT_FRACTION = 0.05


def default_db_path() -> Path:
    return Path(os.environ.get("DEALFINDER_DB") or Path.home() / ".dealfinder" / "prices.db")


@dataclass
class Item:
    id: int
    label: str
    gtin: str | None
    model: str | None
    target_price: float | None
    purchased_retailer: str | None
    purchased_price: float | None
    purchased_on: date | None
    urls: list[str]


@dataclass
class Alert:
    item: Item
    offer: Offer
    reason: str

    def message(self) -> str:
        return f"{self.item.label}: {self.offer.retailer} ${self.offer.total:,.2f} — {self.reason}\n{self.offer.url}"


class Tracker:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_db_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # --- items ------------------------------------------------------------

    def add(self, label: str, urls: list[str], *, gtin: str | None = None, model: str | None = None,
            target_price: float | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO items(label, gtin, model, target_price, created_at) VALUES (?,?,?,?,?)",
            (label, gtin, model, target_price, _now()))
        item_id = cur.lastrowid
        self.db.executemany("INSERT OR IGNORE INTO item_urls VALUES (?,?)", [(item_id, u) for u in urls])
        self.db.commit()
        return item_id

    def record_purchase(self, item_id: int, retailer: str, price: float, on: date):
        self.db.execute("UPDATE items SET purchased_retailer=?, purchased_price=?, purchased_on=? WHERE id=?",
                        (retailer, price, on.isoformat(), item_id))
        self.db.commit()

    def remove(self, item_id: int):
        self.db.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.db.commit()

    def items(self) -> list[Item]:
        rows = self.db.execute("SELECT * FROM items ORDER BY id").fetchall()
        out = []
        for r in rows:
            urls = [u for (u,) in self.db.execute("SELECT url FROM item_urls WHERE item_id=?", (r["id"],))]
            out.append(Item(r["id"], r["label"], r["gtin"], r["model"], r["target_price"],
                            r["purchased_retailer"], r["purchased_price"],
                            date.fromisoformat(r["purchased_on"]) if r["purchased_on"] else None, urls))
        return out

    def get(self, item_id: int) -> Item | None:
        return next((i for i in self.items() if i.id == item_id), None)

    # --- observations -----------------------------------------------------

    def record(self, item_id: int, offer: Offer, at: datetime | None = None):
        self.db.execute(
            "INSERT INTO observations(item_id, retailer, url, price, total, condition, sold_by_retailer, in_stock, observed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (item_id, offer.retailer, offer.url, offer.price, offer.total, offer.condition.value,
             int(offer.sold_by_retailer), None if offer.in_stock is None else int(offer.in_stock),
             (at or datetime.now(timezone.utc)).isoformat(timespec="seconds")))
        self.db.commit()

    def stats(self, item_id: int, offer: Offer, days: int = 90, now: datetime | None = None) -> PriceStats:
        """History for one listing (same URL *and* condition — open-box shares the new item's URL)."""
        now = now or datetime.now(timezone.utc)
        since = (now - timedelta(days=days)).isoformat(timespec="seconds")
        key = (item_id, offer.url, offer.condition.value)
        where = "item_id=? AND url=? AND condition=?"
        avg, low = self.db.execute(
            f"SELECT AVG(price), MIN(price) FROM observations WHERE {where} AND observed_at>=?", (*key, since)).fetchone()
        (all_low,) = self.db.execute(f"SELECT MIN(price) FROM observations WHERE {where}", key).fetchone()
        last = self.db.execute(
            f"SELECT price FROM observations WHERE {where} ORDER BY observed_at DESC, id DESC LIMIT 1", key).fetchone()
        return PriceStats(current=last[0] if last else None, avg_90d=avg, low_90d=low,
                          all_time_low=all_low, source="local history")

    def observation_count(self, item_id: int, offer: Offer) -> int:
        (n,) = self.db.execute("SELECT COUNT(*) FROM observations WHERE item_id=? AND url=? AND condition=?",
                               (item_id, offer.url, offer.condition.value)).fetchone()
        return n

    # --- alerts -----------------------------------------------------------

    def evaluate(self, item: Item, offer: Offer) -> list[Alert]:
        """Compare a fresh offer with stored history *before* recording it."""
        alerts: list[Alert] = []
        if offer.in_stock is False:
            return alerts
        prior = self.stats(item.id, offer)
        n = self.observation_count(item.id, offer)
        # Alert when the price first reaches the target, not on every check while it stays there.
        newly_at_target = item.target_price is not None and offer.total <= item.target_price and (
            prior.current is None or prior.current > item.target_price)
        if newly_at_target:
            alerts.append(Alert(item, offer, f"at or below your target ${item.target_price:,.2f}"))
        if prior.current is not None and offer.price < prior.current * (1 - DROP_ALERT_FRACTION):
            alerts.append(Alert(item, offer, f"dropped {1 - offer.price / prior.current:.0%} from ${prior.current:,.2f}"))
        if n >= 3 and prior.all_time_low is not None and offer.price < prior.all_time_low:
            alerts.append(Alert(item, offer, f"lowest price seen (previous low ${prior.all_time_low:,.2f})"))
        return alerts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
