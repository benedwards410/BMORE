"""Read the price from any product page the user pastes, via schema.org structured data.

Most retailer and manufacturer product pages embed a schema.org `Product` block
(JSON-LD) with price, availability, condition, GTIN and MPN, because search engines need
it. Reading that block is far more reliable than scraping visible HTML.

This is for *one page at a time, on request*: it checks robots.txt, identifies itself
honestly and never retries around bot protection. Large retailers (Amazon, Walmart)
usually block automated fetches; when that happens the price is reported as unavailable
instead of guessed.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import urlsplit

import requests

from ..identity import normalize_gtin
from ..models import Condition, Offer
from ..urls import clean_url, retailer_from_url
from .base import TIMEOUT, USER_AGENT, SourceError, session


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_ld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self.blocks.append("".join(self._buf))
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)


def _walk(node):
    """Yield every dict in a JSON-LD tree (handles @graph and nested lists)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _is_type(d: dict, name: str) -> bool:
    t = d.get("@type")
    return t == name or (isinstance(t, list) and name in t)


def _price(v) -> float | None:
    if v is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(v)))
    except ValueError:
        return None


def _condition(v) -> Condition:
    s = str(v or "").rsplit("/", 1)[-1].lower()
    return {"newcondition": Condition.NEW, "refurbishedcondition": Condition.REFURBISHED,
            "usedcondition": Condition.USED, "damagedcondition": Condition.USED}.get(s, Condition.NEW)


def _stock(v) -> bool | None:
    s = str(v or "").rsplit("/", 1)[-1].lower()
    if not s:
        return None
    return s in {"instock", "limitedavailability", "onlineonly", "instoreonly", "presale", "preorder"}


def _seller_is_retailer(seller_name: str | None, retailer: str) -> bool:
    if not seller_name:
        return True
    a = re.sub(r"[^a-z0-9]", "", seller_name.lower())
    b = re.sub(r"[^a-z0-9]", "", retailer.lower().split(".")[0])
    return a == b or a.startswith(b) or b.startswith(a)


def parse_product_page(html: str, url: str) -> list[Offer]:
    """Extract offers from a product page's JSON-LD (falls back to og/product meta tags)."""
    c = _Collector()
    c.feed(html)
    retailer = retailer_from_url(url)
    clean = clean_url(url)
    offers: list[Offer] = []

    for raw in c.blocks:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        for prod in (d for d in _walk(data) if _is_type(d, "Product")):
            gtin = next((prod.get(k) for k in ("gtin", "gtin12", "gtin13", "gtin14", "gtin8") if prod.get(k)), None)
            brand = prod.get("brand")
            brand = brand.get("name") if isinstance(brand, dict) else brand
            model = prod.get("mpn") or (prod.get("model") if isinstance(prod.get("model"), str) else None)
            raw_offers = prod.get("offers") or []
            for off in raw_offers if isinstance(raw_offers, list) else [raw_offers]:
                if not isinstance(off, dict):
                    continue
                price = _price(off.get("price")) or _price(off.get("lowPrice"))
                if price is None:
                    ps = off.get("priceSpecification")
                    ps = ps[0] if isinstance(ps, list) and ps else ps
                    price = _price(ps.get("price")) if isinstance(ps, dict) else None
                if price is None:
                    continue
                seller = off.get("seller")
                seller_name = seller.get("name") if isinstance(seller, dict) else seller
                is_retailer = _seller_is_retailer(seller_name, retailer)
                offers.append(Offer(
                    retailer=retailer, title=str(prod.get("name") or ""), price=price,
                    currency=off.get("priceCurrency", "USD"), url=clean, source="jsonld",
                    condition=_condition(off.get("itemCondition")), in_stock=_stock(off.get("availability")),
                    seller=None if is_retailer else seller_name, sold_by_retailer=is_retailer,
                    gtin=normalize_gtin(gtin), model_number=model,
                    brand=brand,
                    notes=["lowest of several offers on page"] if off.get("lowPrice") and not off.get("price") else [],
                ))
    if offers:
        return offers

    amount = c.meta.get("product:price:amount") or c.meta.get("og:price:amount") or c.meta.get("price")
    if _price(amount) is not None:
        return [Offer(retailer=retailer, title=c.meta.get("og:title", ""), price=_price(amount), url=clean,
                      source="meta-tags", currency=c.meta.get("product:price:currency", "USD"),
                      notes=["price from page meta tags — less reliable than structured data"])]
    return []


def allowed_by_robots(url: str, http: requests.Session | None = None) -> bool:
    parts = urlsplit(url)
    rp = robotparser.RobotFileParser()
    try:
        r = (http or session()).get(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=TIMEOUT)
    except requests.RequestException:
        return True  # unreachable robots.txt: the standard treats this as "no rules"
    if r.status_code in (401, 403):
        return False
    if r.status_code >= 400:
        return True
    rp.parse(r.text.splitlines())
    return rp.can_fetch(USER_AGENT, url)


class ProductPage:
    name = "page"

    def __init__(self, http=None, respect_robots: bool = True):
        self.http = http or session()
        self.respect_robots = respect_robots

    def available(self) -> bool:
        return True

    def fetch(self, url: str) -> list[Offer]:
        if self.respect_robots and not allowed_by_robots(url, self.http):
            raise SourceError(f"{retailer_from_url(url)} disallows automated fetching of this page (robots.txt)")
        try:
            r = self.http.get(url, timeout=TIMEOUT, headers={"Accept": "text/html"})
        except requests.RequestException as e:
            raise SourceError(f"{retailer_from_url(url)}: {e}") from e
        if r.status_code in (403, 429, 503):
            raise SourceError(f"{retailer_from_url(url)} blocked the request (HTTP {r.status_code}); "
                              "check the price manually")
        if r.status_code >= 400:
            raise SourceError(f"{retailer_from_url(url)}: HTTP {r.status_code}")
        offers = parse_product_page(r.text, url)
        if not offers:
            raise SourceError(f"{retailer_from_url(url)}: no machine-readable price on the page")
        return offers
