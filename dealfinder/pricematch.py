"""Find price-match and price-adjustment money you're entitled to.

This only *tells you* what to ask for, from whom, and by when. It never contacts a
retailer, files a claim or touches an account — price matches are granted by a person
checking the competitor listing, and automating claims would break retailer terms.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from pathlib import Path

from .models import Condition, Offer


@dataclass
class Policy:
    key: str
    name: str
    matches_competitors: list[str]
    matches_competitors_after_purchase: bool
    own_price_adjustment_days: int
    conditions: str
    policy_url: str
    checked: str


def load_policies(path: str | Path | None = None) -> dict[str, Policy]:
    if path:
        raw = json.loads(Path(path).read_text())
    else:
        raw = json.loads(resources.files("dealfinder").joinpath("policies.json").read_text())
    return {k: Policy(key=k, **v) for k, v in raw.items() if not k.startswith("_")}


@dataclass
class Purchase:
    retailer: str
    price: float
    purchased_on: date
    title: str = ""


@dataclass
class Opportunity:
    kind: str           # "price-adjustment" | "competitor-match" | "match-before-buying" | "return-and-rebuy"
    retailer: str       # who to ask
    amount: float       # money back / saved
    deadline: date | None
    evidence: Offer     # the listing to show them
    how: str

    def describe(self) -> str:
        when = f" by {self.deadline:%a %b %d}" if self.deadline else ""
        return f"[{self.kind}] Ask {self.retailer} for ${self.amount:,.2f}{when}: {self.how}"


def _eligible_evidence(o: Offer) -> bool:
    """Retailers only match new, in-stock items sold by the competitor itself."""
    return o.condition == Condition.NEW and o.sold_by_retailer and o.in_stock is not False and o.verified


def after_purchase(p: Purchase, current: list[Offer], policies: dict[str, Policy],
                   today: date | None = None) -> list[Opportunity]:
    """You already bought it — is any money owed back?"""
    today = today or date.today()
    pol = policies.get(p.retailer)
    found: list[Opportunity] = []
    if pol is None:
        return found

    deadline = p.purchased_on + timedelta(days=pol.own_price_adjustment_days)
    in_window = pol.own_price_adjustment_days > 0 and today <= deadline

    for o in current:
        if not _eligible_evidence(o) or o.price >= p.price:
            continue
        saving = round(p.price - o.price, 2)
        if o.retailer == p.retailer and in_window:
            found.append(Opportunity(
                "price-adjustment", pol.name, saving, deadline, o,
                f"{pol.name}'s own price dropped to ${o.price:,.2f}. Bring your receipt or use online chat. "
                f"Confirm terms: {pol.policy_url}"))
        elif (o.retailer in pol.matches_competitors and pol.matches_competitors_after_purchase and in_window):
            found.append(Opportunity(
                "competitor-match", pol.name, saving, deadline, o,
                f"{o.retailer} sells the identical item for ${o.price:,.2f}: {o.url} — "
                f"{pol.conditions} Confirm terms: {pol.policy_url}"))

    if not found and pol.own_price_adjustment_days == 0:
        cheaper = [o for o in current if _eligible_evidence(o) and o.retailer == p.retailer and o.price < p.price]
        if cheaper:
            o = min(cheaper, key=lambda x: x.price)
            found.append(Opportunity(
                "return-and-rebuy", pol.name, round(p.price - o.price, 2), None, o,
                f"{pol.name} doesn't adjust prices. If the item is still in its return window "
                f"and unopened, returning it and buying again at ${o.price:,.2f} gets the same result."))

    # One ask per retailer/kind: keep the biggest.
    best: dict[tuple[str, str], Opportunity] = {}
    for op in found:
        k = (op.kind, op.retailer)
        if k not in best or op.amount > best[k].amount:
            best[k] = op
    return sorted(best.values(), key=lambda op: -op.amount)


def before_purchase(preferred: str, offers: list[Offer], policies: dict[str, Policy]) -> Opportunity | None:
    """You want to buy from `preferred` (pickup today, store card, easy returns) — can they match a lower price?"""
    pol = policies.get(preferred)
    if pol is None or not pol.matches_competitors:
        return None
    own = [o for o in offers if o.retailer == preferred and o.condition == Condition.NEW]
    if not own:
        return None
    own_price = min(o.price for o in own)
    rivals = [o for o in offers if o.retailer in pol.matches_competitors and _eligible_evidence(o) and o.price < own_price]
    if not rivals:
        return None
    best = min(rivals, key=lambda o: o.price)
    return Opportunity(
        "match-before-buying", pol.name, round(own_price - best.price, 2), None, best,
        f"Show {pol.name} the {best.retailer} listing at ${best.price:,.2f} ({best.url}) at checkout or in chat. "
        f"{pol.conditions} Confirm terms: {pol.policy_url}")
