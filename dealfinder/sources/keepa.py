"""Keepa API (paid, https://keepa.com/#!api) for Amazon prices and price history.

Keepa's AMAZON price type is the price when Amazon itself is the seller — exactly the
"sold and shipped by Amazon" number we want — so we don't need Amazon's affiliate-gated
Product Advertising API at all.

Prices are integers in cents; -1 means "no offer". The stats arrays are indexed by price
type: 0 = AMAZON, 1 = NEW (3rd-party new), 2 = USED. Extreme values (min, minInInterval)
are [keepaTime, price] pairs.
"""

from __future__ import annotations

from ..identity import normalize_gtin
from ..models import Condition, Offer, PriceStats
from ..urls import amazon_asin
from .base import SourceError, env, get_json, session

API = "https://api.keepa.com/product"
AMAZON, NEW, USED = 0, 1, 2
US_DOMAIN = 1


def _cents(v) -> float | None:
    if isinstance(v, list):          # [keepaTime, price] pair
        v = v[1] if len(v) == 2 else None
    if v is None or not isinstance(v, (int, float)) or v < 0:
        return None
    return round(v / 100, 2)


def _at(arr, idx):
    return arr[idx] if isinstance(arr, list) and len(arr) > idx else None


def stats_from_product(p: dict, price_type: int = AMAZON) -> PriceStats:
    s = p.get("stats") or {}
    return PriceStats(
        current=_cents(_at(s.get("current"), price_type)),
        avg_90d=_cents(_at(s.get("avg90"), price_type)),
        low_90d=_cents(_at(s.get("minInInterval"), price_type)),
        all_time_low=_cents(_at(s.get("min"), price_type)),
        source="keepa",
    )


class Keepa:
    name = "amazon"

    def __init__(self, api_key: str | None = None, http=None):
        self.api_key = api_key or env("KEEPA_API_KEY")
        self.http = http or session()
        self.stats_by_url: dict[str, PriceStats] = {}  # filled by lookups so history costs no extra tokens

    def available(self) -> bool:
        return bool(self.api_key)

    def _products(self, **params) -> list[dict]:
        if not self.api_key:
            raise SourceError("KEEPA_API_KEY not set")
        data = get_json(self.http, API, params={"key": self.api_key, "domain": US_DOMAIN,
                                                "stats": 90, **params})
        return data.get("products") or []

    def _offers(self, p: dict) -> list[Offer]:
        asin = p.get("asin")
        title = p.get("title") or ""
        url = f"https://www.amazon.com/dp/{asin}"
        gtin = normalize_gtin(next(iter(p.get("upcList") or p.get("eanList") or []), None))
        common = dict(retailer="amazon", title=title, url=url, source="keepa", gtin=gtin,
                      model_number=p.get("model") or p.get("partNumber"), brand=p.get("brand"))
        stats = stats_from_product(p)
        self.stats_by_url[url] = stats
        offers = []
        if stats.current is not None:
            offers.append(Offer(price=stats.current, condition=Condition.NEW, in_stock=True,
                                sold_by_retailer=True, **common))
        else:
            third = stats_from_product(p, NEW).current
            if third is not None:
                offers.append(Offer(price=third, condition=Condition.NEW, in_stock=True,
                                    sold_by_retailer=False, seller="Amazon marketplace seller",
                                    notes=["Amazon itself has no offer right now"], **common))
        return offers

    def search(self, query: str, limit: int = 10) -> list[Offer]:
        return []  # Keepa search costs extra tokens; look up by UPC/ASIN instead.

    def lookup(self, *, gtin: str | None = None, model: str | None = None, asin: str | None = None) -> list[Offer]:
        if asin:
            products = self._products(asin=asin)
        elif gtin and (g := normalize_gtin(gtin)):
            products = self._products(code=g.lstrip("0").zfill(12))
        else:
            return []
        return [o for p in products for o in self._offers(p)]

    def history(self, offer: Offer) -> PriceStats | None:
        if offer.url in self.stats_by_url:
            return self.stats_by_url[offer.url]
        asin = amazon_asin(offer.url)
        if not asin:
            return None
        products = self._products(asin=asin)
        return stats_from_product(products[0]) if products else None
