"""Pull offers for one product from every available source."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from .identity import normalize_gtin, title_similarity
from .models import Condition, Offer, PriceStats
from .sources import BestBuy, Ebay, Keepa, ProductPage, SourceError
from .urls import amazon_asin, clean_url, retailer_from_url


@dataclass
class Gathered:
    offers: list[Offer] = field(default_factory=list)
    history: dict[str, PriceStats] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    gtin: str | None = None
    model: str | None = None
    title: str | None = None
    reference: Offer | None = None   # the listing the user pointed at, if any


def _bestbuy_sku(url: str) -> str | None:
    q = parse_qs(urlsplit(url).query)
    if q.get("skuId"):
        return q["skuId"][0]
    m = re.search(r"/(\d{6,8})\.p\b", url)
    return m.group(1) if m else None


class Finder:
    def __init__(self, bestbuy: BestBuy | None = None, keepa: Keepa | None = None,
                 ebay: Ebay | None = None, page: ProductPage | None = None, include_ebay: bool = True):
        self.bestbuy = bestbuy or BestBuy()
        self.keepa = keepa or Keepa()
        self.ebay = ebay or Ebay()
        self.page = page or ProductPage()
        self.include_ebay = include_ebay

    def sources_status(self) -> dict[str, bool]:
        return {"Best Buy API": self.bestbuy.available(), "Keepa (Amazon)": self.keepa.available(),
                "eBay API": self.ebay.available(), "Product pages (JSON-LD)": True}

    def _try(self, g: Gathered, label: str, fn):
        try:
            got = fn()
            g.offers.extend(got)
            return got
        except SourceError as e:
            g.warnings.append(f"{label}: {e}")
            return []

    def _from_url(self, g: Gathered, url: str):
        url = clean_url(url)
        retailer = retailer_from_url(url)
        if retailer == "amazon" and self.keepa.available() and (asin := amazon_asin(url)):
            return self._try(g, "amazon", lambda: self.keepa.lookup(asin=asin))
        if retailer == "bestbuy" and self.bestbuy.available() and (sku := _bestbuy_sku(url)):
            return self._try(g, "bestbuy", lambda: self.bestbuy.by_sku(sku))
        return self._try(g, retailer, lambda: self.page.fetch(url))

    def gather(self, query: str | None = None, urls: list[str] | None = None,
               gtin: str | None = None, model: str | None = None, open_box: bool = True) -> Gathered:
        g = Gathered(gtin=normalize_gtin(gtin), model=model)
        seen_retailers = set()

        # 1. Pages the user gave us pin down the product identity.
        for u in urls or []:
            for o in self._from_url(g, u):
                seen_retailers.add(o.retailer)
        g.reference = g.offers[0] if g.offers else None
        for o in g.offers:
            g.gtin = g.gtin or o.gtin
            g.model = g.model or o.model_number
            g.title = g.title or o.title

        # 2. Ask each API for the same product — exact IDs first, free text last.
        def lookup(src, label):
            if g.gtin or g.model:
                got = self._try(g, label, lambda: src.lookup(gtin=g.gtin, model=g.model))
                if got or not (g.title or query):
                    return
            if g.title or query:
                self._try(g, label, lambda: src.search(g.title or query, limit=10))

        if self.bestbuy.available() and "bestbuy" not in seen_retailers:
            lookup(self.bestbuy, "bestbuy")

        # A free-text search returns a mix (accessories, other colors). Anchor on the result
        # that best matches the query, then use its UPC for every other source.
        if g.reference is None and query and g.offers:
            g.reference = max(g.offers, key=lambda o: (title_similarity(query, o.title),
                                                       o.condition == Condition.NEW, -o.price))
            g.gtin = g.gtin or g.reference.gtin
            g.model = g.model or g.reference.model_number
            g.title = g.reference.title

        if self.keepa.available() and "amazon" not in seen_retailers and g.gtin:
            self._try(g, "amazon", lambda: self.keepa.lookup(gtin=g.gtin))
        if self.include_ebay and self.ebay.available():
            lookup(self.ebay, "ebay")

        # 3. Best Buy open-box for the exact SKU(s) we found.
        if open_box and self.bestbuy.available():
            skus = {s for o in g.offers
                    if o.source == "bestbuy-api" and (not g.gtin or o.gtin == g.gtin) and (s := _bestbuy_sku(o.url))}
            for sku in list(skus)[:3]:
                self._try(g, "bestbuy open-box", lambda s=sku: self.bestbuy.open_box(s))
            # Open-box listings carry no UPC; inherit it from the new listing of the same SKU.
            ids = {o.url: (o.gtin, o.model_number) for o in g.offers if o.source == "bestbuy-api"}
            for o in g.offers:
                if o.source == "bestbuy-openbox-api" and o.url in ids:
                    o.gtin, o.model_number = ids[o.url]

        # Sources overlap (a pasted Best Buy URL plus a Best Buy UPC lookup) — keep one of each.
        seen: set[tuple] = set()
        unique = []
        for o in g.offers:
            k = (o.retailer, o.url, o.condition, o.price, o.seller)
            if k not in seen:
                seen.add(k)
                unique.append(o)
        g.offers = unique

        # 4. Amazon price history came free with the Keepa lookup.
        for o in g.offers:
            if o.url in self.keepa.stats_by_url:
                g.history[o.url] = self.keepa.stats_by_url[o.url]

        if not g.offers:
            g.warnings.append("No prices found. Add API keys (see README) or paste product page URLs.")
        return g
