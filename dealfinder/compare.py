"""Turn a pile of offers into a ranked, vetted comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from .identity import Match, matches_reference
from .models import Condition, Offer, PriceStats

# Below this fraction of the median trusted price, a listing is treated as a likely
# counterfeit, gray-market import, pricing error or scam rather than a deal.
SUSPICIOUS_FRACTION = 0.60


@dataclass
class Ranked:
    offer: Offer
    flags: list[str] = field(default_factory=list)
    history: PriceStats | None = None

    @property
    def trusted(self) -> bool:
        return not any(f.startswith(("third-party", "suspicious")) for f in self.flags)


@dataclass
class Comparison:
    reference: Offer
    ranked: list[Ranked]
    rejected: list[tuple[Offer, Match]]
    best_new: Ranked | None
    best_alternative: Ranked | None   # open-box / refurbished from a trusted seller
    median_trusted: float | None


def _flags(o: Offer, median_trusted: float | None) -> list[str]:
    flags: list[str] = []
    if not o.sold_by_retailer:
        who = f" ({o.seller})" if o.seller else ""
        flags.append(f"third-party seller{who}")
    if median_trusted and o.total < median_trusted * SUSPICIOUS_FRACTION:
        flags.append(f"suspiciously low: {o.total / median_trusted:.0%} of typical price")
    if o.in_stock is False:
        flags.append("out of stock")
    if o.shipping is None and not o.sold_by_retailer:
        flags.append("shipping unknown")
    if not o.verified:
        flags.append("unverified price")
    flags.extend(o.notes)
    return flags


def compare(
    offers: list[Offer],
    reference: Offer | None = None,
    history: dict[str, PriceStats] | None = None,
) -> Comparison:
    """Rank offers for the same product as `reference` (default: first offer with a GTIN or model).

    `history` maps an offer URL to its PriceStats so reports can say whether a price is really low.
    """
    if not offers:
        raise ValueError("no offers to compare")
    if reference is None:
        reference = next((o for o in offers if o.gtin), None) or \
            next((o for o in offers if o.model_number), None) or offers[0]

    kept, rejected = matches_reference(reference, offers)

    # Median of first-party new prices is our yardstick for "normal".
    first_party_new = [o.total for o in kept if o.sold_by_retailer and o.condition == Condition.NEW]
    med = median(first_party_new) if first_party_new else None

    ranked = [Ranked(o, _flags(o, med), (history or {}).get(o.url)) for o in kept]
    ranked.sort(key=lambda r: (not r.trusted, r.offer.in_stock is False, r.offer.total))

    def best(pred) -> Ranked | None:
        pool = [r for r in ranked if r.trusted and r.offer.in_stock is not False and pred(r.offer)]
        return min(pool, key=lambda r: r.offer.total) if pool else None

    best_new = best(lambda o: o.condition == Condition.NEW)
    best_alt = best(lambda o: o.condition in (Condition.OPEN_BOX, Condition.REFURBISHED))
    if best_alt and best_new and best_alt.offer.total >= best_new.offer.total:
        best_alt = None  # open-box that isn't cheaper than new isn't worth mentioning
    return Comparison(reference, ranked, rejected, best_new, best_alt, med)
