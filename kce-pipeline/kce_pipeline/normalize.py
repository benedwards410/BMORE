"""Canonical fixture-type vocabulary, size classes, wattage tiers, and defensive
number parsing.

Everything in here is driven by config/canonical_fixtures.json (task outline 6.2:
"Maintain this list as an editable JSON/YAML config file, not a hardcoded string
in a prompt").
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


# --------------------------------------------------------------------------
# text + number helpers
# --------------------------------------------------------------------------

def clean_text(value) -> str:
    """Lowercase, collapse whitespace. Matching is always done on this form."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def parse_money(value):
    """Parse a currency-ish string defensively.

    Section 4.1: "expect occasional typos in source PDFs (e.g. a price rendered
    as `$30..00`). Parse defensively -- strip repeated punctuation before parsing
    a number, don't fail the whole document over one bad cell."

    Returns a float, or None when there is no number to find (e.g. "Included").
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None
    if "included" in text.lower():
        return None

    negative = text.startswith("(") and text.endswith(")")

    # Drop currency symbols, thousands separators and stray characters.
    text = re.sub(r"[^0-9.\-]", "", text)
    # Collapse repeated dots/dashes: "$30..00" -> "30.00", "1--2" -> "1-2".
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"-{2,}", "-", text)
    # A trailing or leading stray dot ("30." / ".50") is still parseable.
    if not re.search(r"\d", text):
        return None
    # More than one dot left (e.g. "1.234.56" from a mangled thousands sep):
    # keep the last as the decimal point.
    if text.count(".") > 1:
        head, _, tail = text.rpartition(".")
        text = head.replace(".", "") + "." + tail

    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative and number > 0 else number


def parse_qty(value):
    """Parse a quantity. Returns int when integral, else float, else None."""
    number = parse_money(value)
    if number is None:
        return None
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return number


def parse_watts(value):
    """Pull a wattage out of free text: 'Exterior LED 100W Wall Mount' -> 100.0."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:w\b|watt)", str(value), re.IGNORECASE)
    return float(match.group(1)) if match else None


# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

@dataclass
class TypeMatch:
    canonical: str | None
    method: str          # "exact" | "rule" | "fuzzy" | "unmatched"
    score: float
    raw: str


class Vocabulary:
    """Canonical fixture types, size classes, wattage tiers, accessory rules."""

    def __init__(self, config: dict, fuzzy_threshold: float = 0.82):
        self.config = config
        self.fuzzy_threshold = fuzzy_threshold
        self.canonical_types: list[str] = list(config["canonicalTypes"])
        self.component_types: set[str] = set(config.get("componentTypes", []))
        self.sensor_types: set[str] = set(config.get("sensorTypes", []))
        self.wattage_tiers: dict = config.get("wattageTiers", {})
        self.accessory_rules: dict = config.get("accessoryRules", {})

        self._by_lower = {clean_text(t): t for t in self.canonical_types}
        self._rules = sorted(config.get("rules", []), key=lambda r: r.get("priority", 100))
        self._size_rules = config.get("sizeClassRules", [])
        self._sku_map = {self._sku_key(k): v
                         for k, v in (config.get("skuMap") or {}).items()}

    @staticmethod
    def _sku_key(sku) -> str:
        """SKUs get punctuated inconsistently between documents -- compare on
        alphanumerics only, so 'KEI-IFS108' and 'KEIIFS108' are the same part."""
        return re.sub(r"[^a-z0-9]", "", str(sku or "").lower())

    def match_sku(self, sku) -> TypeMatch | None:
        """Exact SKU lookup. A part number is authoritative where a description
        is only suggestive, so this is checked before any text rule."""
        key = self._sku_key(sku)
        if key and key in self._sku_map:
            return TypeMatch(self._sku_map[key], "sku", 1.0, str(sku))
        return None

    # -- fixture type ------------------------------------------------------

    def match_type(self, *texts) -> TypeMatch:
        """Resolve free text to a canonical fixture type.

        Section 6.2: "Match new incoming names against it via exact match first,
        then a fuzzy/semantic pass, before ever inventing a new canonical name."
        """
        joined = clean_text(" ".join(str(t) for t in texts if t))
        if not joined:
            return TypeMatch(None, "unmatched", 0.0, "")

        if joined in self._by_lower:
            return TypeMatch(self._by_lower[joined], "exact", 1.0, joined)

        for rule in self._rules:
            if self._rule_matches(rule, joined):
                return TypeMatch(rule["canonical"], "rule", 1.0, joined)

        best, best_score = None, 0.0
        for canonical in self.canonical_types:
            score = difflib.SequenceMatcher(None, joined, clean_text(canonical)).ratio()
            if score > best_score:
                best, best_score = canonical, score
        if best is not None and best_score >= self.fuzzy_threshold:
            return TypeMatch(best, "fuzzy", best_score, joined)

        return TypeMatch(None, "unmatched", best_score, joined)

    @staticmethod
    def _rule_matches(rule: dict, text: str) -> bool:
        for pattern in rule.get("all", []):
            if not re.search(pattern, text):
                return False
        any_patterns = rule.get("any", [])
        if any_patterns and not any(re.search(p, text) for p in any_patterns):
            return False
        for pattern in rule.get("none", []):
            if re.search(pattern, text):
                return False
        return True

    # -- size class --------------------------------------------------------

    def size_class(self, *texts) -> str | None:
        """Derive the coarse size class (2ft / 4ft / 8ft / High Bay / Exterior).

        Section 8.6: "Do not implement the sensor check using the canonical
        fixtureType field -- derive a separate, coarser sizeClass ... and sum by
        that instead."
        """
        joined = clean_text(" ".join(str(t) for t in texts if t))
        if not joined:
            return None
        for rule in self._size_rules:
            if any(re.search(p, joined) for p in rule.get("any", [])):
                return rule["sizeClass"]
        return None

    # -- classification helpers -------------------------------------------

    def is_sensor(self, canonical: str | None) -> bool:
        return canonical in self.sensor_types

    def is_component(self, canonical: str | None) -> bool:
        """Photocell / EM Battery Backup -- accessory labels, never free-floating
        top-level fixture types (6.2, 8.5)."""
        return canonical in self.component_types

    def is_reconcilable(self, canonical: str | None) -> bool:
        """Types that participate in the ordered/approved/installed check (8.8).

        Sensors DO (8.6); components do NOT (8.5).
        """
        return bool(canonical) and not self.is_component(canonical)

    # -- wattage tiers -----------------------------------------------------

    def is_tiered(self, canonical: str | None) -> bool:
        return canonical in self.wattage_tiers

    def tiers_for(self, canonical: str) -> list[dict]:
        return self.wattage_tiers.get(canonical, [])

    def tier_for_watts(self, canonical: str, watts) -> str | None:
        """Pick the wattage tier a given wattage falls into, or None."""
        if watts is None or canonical not in self.wattage_tiers:
            return None
        for tier in self.wattage_tiers[canonical]:
            low = tier.get("minW")
            high = tier.get("maxW")
            if low is not None and watts <= low:
                continue
            if high is not None and watts > high:
                continue
            return tier["tier"]
        return None

    @staticmethod
    def tier_from_text(text) -> str | None:
        """Read a tier label straight off a rate-card row description.

        'Wall Pack < 50W' -> '<50W'; 'High Bay -- up to 150 W' -> '<=150W'.
        """
        cleaned = clean_text(text)
        if not cleaned:
            return None
        patterns = [
            (r"<\s*=\s*(\d+)\s*w", "<={n}W"),
            (r"under\s*(\d+)\s*w", "<{n}W"),
            (r"up\s*to\s*(\d+)\s*w", "<={n}W"),
            (r"over\s*(\d+)\s*w", ">{n}W"),
            (r"<\s*(\d+)\s*w", "<{n}W"),
            (r">\s*(\d+)\s*w", ">{n}W"),
        ]
        for pattern, template in patterns:
            match = re.search(pattern, cleaned)
            if match:
                return template.format(n=match.group(1))
        return None

    # -- accessories -------------------------------------------------------

    def accessory_rule(self, canonical: str) -> dict:
        """Section 8.5 rule table lookup. Unknown accessories get no default."""
        return self.accessory_rules.get(canonical, {
            "confidence": "needs_confirmation",
            "flag": True,
            "parentSizeClasses": [],
            "note": "No association rule for this accessory type -- do not guess.",
        })


# --------------------------------------------------------------------------
# size-range expansion (rate cards)
# --------------------------------------------------------------------------

_RANGE_PATTERNS = [
    # "Strip -- 2 ft or 4 ft", "Standard Vapor Tight -- 2 ft or 4 ft"
    (re.compile(r"(\d)\s*(?:ft|foot|feet|')\s*(?:or|/|,|&|and)\s*(\d)\s*(?:ft|foot|feet|')",
                re.IGNORECASE), "ft"),
    # "Flat Panel -- standard (2x2 or 2x4)"
    (re.compile(r"(2\s*[x×]\s*[24])\s*(?:or|/|,|&|and)\s*(2\s*[x×]\s*[24])",
                re.IGNORECASE), "grid"),
]


def expand_size_range(description: str) -> list[str]:
    """Split a rate row covering several sizes into one string per size.

    The reference tracker states the intent directly: "If one rate covers a size
    range (e.g. '2 ft or 4 ft' strips both at $50), output one row per size using
    that same rate."

    Returns [description] unchanged when no range is present.
    """
    if not description:
        return [description]

    for pattern, kind in _RANGE_PATTERNS:
        match = pattern.search(description)
        if not match:
            continue
        first, second = match.group(1), match.group(2)
        if kind == "ft":
            first, second = f"{first} ft", f"{second} ft"
        return [
            description[: match.start()] + first + description[match.end():],
            description[: match.start()] + second + description[match.end():],
        ]

    # '6" or 8"' (recessed cans) is a trim-size range, not a fixture-length
    # range -- both map to the same canonical type, so leave it alone.
    return [description]
