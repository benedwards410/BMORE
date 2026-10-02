"""eBay Browse API (free developer account at https://developer.ebay.com).

eBay is all marketplace sellers, so every offer is marked third-party and is never the
default pick — it's here to show refurbished/used options and as a sanity check on price.
"""

from __future__ import annotations

import base64
import time

from ..identity import normalize_gtin
from ..models import Condition, Offer
from ..urls import clean_url
from .base import SourceError, TIMEOUT, env, get_json, session

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"


class Ebay:
    name = "ebay"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, http=None):
        self.client_id = client_id or env("EBAY_CLIENT_ID")
        self.client_secret = client_secret or env("EBAY_CLIENT_SECRET")
        self.http = http or session()
        self._token: str | None = None
        self._token_expiry = 0.0

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _auth(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        if not self.available():
            raise SourceError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET not set")
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = self.http.post(TOKEN_URL, timeout=TIMEOUT,
                           headers={"Authorization": f"Basic {basic}",
                                    "Content-Type": "application/x-www-form-urlencoded"},
                           data={"grant_type": "client_credentials", "scope": SCOPE})
        if r.status_code >= 400:
            raise SourceError(f"eBay auth failed: HTTP {r.status_code}")
        body = r.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + float(body.get("expires_in", 7200))
        return self._token

    def _search(self, params: dict, limit: int) -> list[Offer]:
        headers = {"Authorization": f"Bearer {self._auth()}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
        params = {**params, "limit": min(limit, 50),
                  "filter": "buyingOptions:{FIXED_PRICE},itemLocationCountry:US,priceCurrency:USD"}
        data = get_json(self.http, SEARCH_URL, params=params, headers=headers)
        return [self._offer(i) for i in data.get("itemSummaries", []) if i.get("price")]

    @staticmethod
    def _offer(i: dict) -> Offer:
        seller = i.get("seller") or {}
        ship_opts = i.get("shippingOptions") or []
        ship = None
        if ship_opts and (cost := ship_opts[0].get("shippingCost")) is not None:
            ship = float(cost.get("value", 0))
        notes = []
        if seller.get("feedbackPercentage"):
            notes.append(f"seller feedback {seller['feedbackPercentage']}% ({seller.get('feedbackScore', '?')})")
        return Offer(
            retailer="ebay",
            title=i.get("title", ""),
            price=float(i["price"]["value"]),
            currency=i["price"].get("currency", "USD"),
            url=clean_url(i.get("itemWebUrl", "")),
            source="ebay-api",
            shipping=ship,
            condition=Condition.parse(i.get("condition")),
            seller=seller.get("username"),
            sold_by_retailer=False,
            in_stock=True,
            gtin=normalize_gtin(i.get("gtin")),
            notes=notes,
        )

    def search(self, query: str, limit: int = 10) -> list[Offer]:
        return self._search({"q": query}, limit)

    def lookup(self, *, gtin: str | None = None, model: str | None = None) -> list[Offer]:
        if gtin and (g := normalize_gtin(gtin)):
            return self._search({"gtin": g.lstrip("0").zfill(12)}, 20)
        if model:
            return self._search({"q": model}, 20)
        return []
