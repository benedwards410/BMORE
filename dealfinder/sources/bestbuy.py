"""Best Buy Products API (free key from https://developer.bestbuy.com).

Best Buy is the most useful single source: it publishes real-time sale price, regular
price, UPC and model number, *and* it still runs a competitor price-match program.
Personal use only — commercial use needs a partner agreement with Best Buy.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from ..identity import normalize_gtin
from ..models import Condition, Offer
from .base import SourceError, env, get_json, session

API = "https://api.bestbuy.com/v1/products"
OPEN_BOX_API = "https://api.bestbuy.com/beta/products/{sku}/openBox"
FIELDS = ("sku,name,salePrice,regularPrice,onSale,upc,modelNumber,manufacturer,"
          "onlineAvailability,condition,freeShipping,shippingCost")


def product_url(sku: int | str) -> str:
    # Built by hand: the API's own `url` field is a click-tracking redirect.
    return f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}"


class BestBuy:
    name = "bestbuy"

    def __init__(self, api_key: str | None = None, http=None):
        self.api_key = api_key or env("BESTBUY_API_KEY")
        self.http = http or session()

    def available(self) -> bool:
        return bool(self.api_key)

    def _query(self, criteria: str, limit: int) -> list[Offer]:
        if not self.api_key:
            raise SourceError("BESTBUY_API_KEY not set")
        url = f"{API}({criteria})"
        params = {"apiKey": self.api_key, "format": "json", "show": FIELDS,
                  "pageSize": min(limit, 100)}
        data = get_json(self.http, url, params=params)
        return [self._offer(p) for p in data.get("products", [])]

    @staticmethod
    def _offer(p: dict) -> Offer:
        free = p.get("freeShipping")
        ship = 0.0 if free else (float(p["shippingCost"]) if isinstance(p.get("shippingCost"), (int, float)) else None)
        return Offer(
            retailer="bestbuy",
            title=p.get("name", ""),
            price=float(p["salePrice"]),
            regular_price=float(p["regularPrice"]) if p.get("regularPrice") else None,
            url=product_url(p["sku"]),
            source="bestbuy-api",
            shipping=ship,
            condition=Condition.parse(p.get("condition")),
            in_stock=p.get("onlineAvailability"),
            gtin=normalize_gtin(p.get("upc")),
            model_number=p.get("modelNumber"),
            brand=p.get("manufacturer"),
        )

    def search(self, query: str, limit: int = 10) -> list[Offer]:
        terms = [t for t in re.findall(r"[A-Za-z0-9]+", query) if len(t) > 1][:8]
        if not terms:
            return []
        return self._query("&".join(f"search={quote(t)}" for t in terms), limit)

    def lookup(self, *, gtin: str | None = None, model: str | None = None) -> list[Offer]:
        if gtin and (g := normalize_gtin(gtin)):
            # Best Buy stores 12-digit UPCs; strip the GTIN-14 padding.
            return self._query(f"upc={g[-12:] if g.startswith('00') else g.lstrip('0')}", 10)
        if model:
            return self._query(f"modelNumber={quote(model, safe='')}", 10)
        return []

    def by_sku(self, sku: int | str) -> list[Offer]:
        return self._query(f"sku={int(sku)}", 1)

    def open_box(self, sku: int | str) -> list[Offer]:
        """Open-box offers for one SKU (Best Buy 'Buying Options' beta API)."""
        data = get_json(self.http, OPEN_BOX_API.format(sku=sku), params={"apiKey": self.api_key})
        offers = []
        for res in data.get("results", []):
            title = (res.get("names") or {}).get("title", "")
            for o in res.get("offers", []):
                price = (o.get("prices") or {}).get("current")
                if price is None:
                    continue
                offers.append(Offer(
                    retailer="bestbuy", title=title, price=float(price),
                    regular_price=(o.get("prices") or {}).get("regular"),
                    url=product_url(res.get("sku", sku)), source="bestbuy-openbox-api",
                    condition=Condition.OPEN_BOX, in_stock=True,
                    notes=[f"open-box grade: {o.get('condition', '?')}"],
                ))
        return offers
