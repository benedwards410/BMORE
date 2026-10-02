"""Core data types shared by every source, the comparer and the tracker."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class Condition(str, Enum):
    NEW = "new"
    OPEN_BOX = "open-box"
    REFURBISHED = "refurbished"
    USED = "used"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, text: str | None) -> "Condition":
        t = (text or "").strip().lower()
        if not t:
            return cls.UNKNOWN
        if "open" in t and "box" in t:
            return cls.OPEN_BOX
        if "refurb" in t or "renewed" in t or "reconditioned" in t:
            return cls.REFURBISHED
        if "used" in t or "pre-owned" in t or "preowned" in t:
            return cls.USED
        if "new" in t:
            return cls.NEW
        return cls.UNKNOWN


@dataclass
class Offer:
    """One price for one product from one seller at one moment."""

    retailer: str                    # e.g. "bestbuy", "amazon", "ebay", "target.com"
    title: str
    price: float                     # item price in `currency`, before tax
    url: str                         # clean URL (tracking params stripped)
    source: str                      # which adapter produced this ("bestbuy-api", "jsonld", ...)
    currency: str = "USD"
    shipping: float | None = None    # None = unknown, 0.0 = free
    condition: Condition = Condition.NEW
    seller: str | None = None        # marketplace seller name when not the retailer itself
    sold_by_retailer: bool = True    # False for Amazon/Walmart/eBay third-party listings
    in_stock: bool | None = None
    gtin: str | None = None          # normalized GTIN-14 (see identity.normalize_gtin)
    model_number: str | None = None
    brand: str | None = None
    regular_price: float | None = None   # retailer's own "was" price, if it reports one
    verified: bool = True            # False when price came from a snippet we couldn't confirm
    notes: list[str] = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def total(self) -> float:
        """Price plus known shipping. Unknown shipping counts as zero but is flagged in reports."""
        return round(self.price + (self.shipping or 0.0), 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["condition"] = self.condition.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Offer":
        d = dict(d)
        d["condition"] = Condition(d.get("condition", "unknown"))
        return cls(**d)


@dataclass
class PriceStats:
    """Price history summary for judging whether 'today' is genuinely low."""

    current: float | None = None
    avg_90d: float | None = None
    low_90d: float | None = None
    all_time_low: float | None = None
    source: str = ""

    def verdict(self, price: float) -> str:
        if self.low_90d is not None and price <= self.low_90d:
            return "at or below its 90-day low"
        if self.avg_90d is not None:
            diff = (price - self.avg_90d) / self.avg_90d
            if diff <= -0.10:
                return f"{abs(diff):.0%} below its 90-day average"
            if diff >= 0.05:
                return f"{diff:.0%} above its 90-day average — probably not a real sale"
            return "about its normal price"
        return "no price history"
