"""Decide whether two listings are the *same* product.

A cheap price on the wrong generation is not a deal, so matching is strict:

1. Same GTIN (UPC/EAN)            -> same product.
2. Same normalized model number   -> same product.
3. Otherwise, similar titles with *no* conflicting variant attributes
   (storage, size, generation, year, pack count, condition words) -> probable match.

Anything with a conflicting attribute is rejected even if the titles look alike.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Offer


# --- GTIN -----------------------------------------------------------------

def gtin_check_digit_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) not in (8, 12, 13, 14):
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize_gtin(raw: str | None) -> str | None:
    """UPC-A, EAN-13, EAN-8 or GTIN-14 -> zero-padded GTIN-14, or None if invalid."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not gtin_check_digit_ok(digits):
        return None
    return digits.zfill(14)


# --- Model numbers --------------------------------------------------------

def normalize_model(raw: str | None) -> str | None:
    """'MXP93LL/A' and 'mxp93ll-a' compare equal; region suffixes are kept (they matter)."""
    if not raw:
        return None
    s = re.sub(r"[\s\-_/.]", "", str(raw)).upper()
    return s or None


# --- Variant attributes ---------------------------------------------------

_STORAGE = re.compile(r"\b(\d+(?:\.\d+)?)\s?(tb|gb)\b", re.I)
_SCREEN = re.compile(r"\b(\d{2}(?:\.\d)?)\s?(?:\"|''|-?\s?inch(?:es)?|in\b|”)", re.I)
_GEN = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s?(?:gen\b|generation\b)", re.I)
_GEN_WORD = re.compile(r"\bgen(?:eration)?\s?(\d{1,2})\b", re.I)
_YEAR = re.compile(r"\b(20[1-3]\d)\b")
_PACK = re.compile(r"\b(\d{1,3})\s?(?:-\s?)?(?:pack|pk|count|ct)\b", re.I)
_COND_WORDS = {
    "refurbished": "refurbished", "renewed": "refurbished", "open box": "open-box",
    "open-box": "open-box", "pre-owned": "used", "used": "used",
}
# Words that, when present on one side only, mean a different SKU in the same family.
_EXCLUSIVE_WORDS = ("pro", "max", "plus", "ultra", "mini", "lite", "se", "air", "xl")


def variant_attributes(title: str) -> dict[str, str]:
    t = title.lower()
    attrs: dict[str, str] = {}
    storages = sorted({f"{float(n):g}{u.lower()}" for n, u in _STORAGE.findall(t)})
    if storages:
        attrs["storage"] = ",".join(storages)
    m = _SCREEN.search(t)
    if m:
        attrs["screen"] = m.group(1)
    m = _GEN.search(t) or _GEN_WORD.search(t)
    if m:
        attrs["generation"] = str(int(m.group(1)))
    years = _YEAR.findall(t)
    if years:
        attrs["year"] = max(years)
    m = _PACK.search(t)
    if m:
        attrs["pack"] = str(int(m.group(1)))
    for word, cond in _COND_WORDS.items():
        if word in t:
            attrs["condition"] = cond
            break
    words = set(re.findall(r"[a-z0-9]+", t))
    flags = sorted(w for w in _EXCLUSIVE_WORDS if w in words)
    if flags:
        attrs["tier"] = ",".join(flags)
    return attrs


def conflicting_attributes(a: str, b: str) -> list[str]:
    """Attribute names present on both titles with different values, plus tier mismatches."""
    va, vb = variant_attributes(a), variant_attributes(b)
    conflicts = [k for k in va.keys() & vb.keys() if va[k] != vb[k]]
    # "iPad Pro" vs "iPad" — a tier word on only one side is also a conflict.
    if ("tier" in va) != ("tier" in vb):
        conflicts.append("tier")
    return sorted(set(conflicts))


# --- Title similarity -----------------------------------------------------

_STOP = {"the", "with", "and", "for", "a", "an", "of", "in", "new", "-", "by", "&", "w"}


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in _STOP and len(w) > 1}


def title_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    # Overlap coefficient: retailer titles vary a lot in length, so Jaccard under-scores.
    return len(ta & tb) / min(len(ta), len(tb))


# --- Matching -------------------------------------------------------------

@dataclass
class Match:
    same: bool
    confidence: str      # "gtin", "model", "title", or "none"
    reason: str


def match(a: Offer, b: Offer, title_threshold: float = 0.75) -> Match:
    ga, gb = normalize_gtin(a.gtin), normalize_gtin(b.gtin)
    if ga and gb:
        if ga == gb:
            return Match(True, "gtin", f"same GTIN {ga.lstrip('0')}")
        return Match(False, "gtin", "different GTINs")

    ma, mb = normalize_model(a.model_number), normalize_model(b.model_number)
    if ma and mb:
        if ma == mb:
            return Match(True, "model", f"same model {a.model_number}")
        return Match(False, "model", f"different models ({a.model_number} vs {b.model_number})")

    conflicts = conflicting_attributes(a.title, b.title)
    if conflicts:
        return Match(False, "title", "titles differ on " + ", ".join(conflicts))
    sim = title_similarity(a.title, b.title)
    if sim >= title_threshold:
        return Match(True, "title", f"titles {sim:.0%} similar, no variant conflicts")
    return Match(False, "none", f"titles only {sim:.0%} similar")


def matches_reference(reference: Offer, offers: list[Offer]) -> tuple[list[Offer], list[tuple[Offer, Match]]]:
    """Split `offers` into those matching `reference` and those rejected (with the reason)."""
    kept: list[Offer] = []
    rejected: list[tuple[Offer, Match]] = []
    for o in offers:
        if o is reference:
            kept.append(o)
            continue
        m = match(reference, o)
        if m.same:
            if m.confidence == "title":
                o.notes.append("matched by title only — confirm model number")
            kept.append(o)
        else:
            rejected.append((o, m))
    return kept, rejected
