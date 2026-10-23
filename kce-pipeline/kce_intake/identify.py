"""Cheap identification with no API calls: MTX numbers, a document-type hint,
and site addresses — from filenames, email subject/body and the PDF text layer.

The pipeline still does the real classification. This module only answers
"which project folder does this belong in?"."""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass

logging.getLogger("pypdf").setLevel(logging.ERROR)  # truncated files are expected input

MTX_RE = re.compile(r"\bMTX\s?(\d{8})\b", re.IGNORECASE)

# Vocabulary = the pipeline's documentTypes plus the BGE paperwork it does not
# model (PA and the customer packet), which still belongs in the project folder.
DOC_TYPE_RULES: list[tuple[str, re.Pattern]] = [
    ("participation_agreement", re.compile(r"participation\s+agreement", re.I)),
    ("proposal_detail", re.compile(r"proposal\s+detail", re.I)),
    ("detailed_cost", re.compile(r"detailed\s+cost", re.I)),
    ("customer_packet", re.compile(r"^customer-", re.I)),
    ("docusign_packet", re.compile(r"complete\s+with\s+docusign", re.I)),
    ("inventory_reconciliation", re.compile(r"inventory\s+reconciliation", re.I)),
    ("credit_calculation", re.compile(r"credit\s+calculation", re.I)),
    ("piece_rate_schedule", re.compile(r"piece\s+rate", re.I)),
    ("work_order", re.compile(r"\bwork\s+order\b|\bWO\b", re.I)),
    ("invoice", re.compile(r"\binvoice\b", re.I)),
]

TEXT_TYPE_RULES: list[tuple[str, re.Pattern]] = [
    ("detailed_cost", re.compile(r"program\s+share.*customer\s+share", re.I | re.S)),
    ("proposal_detail", re.compile(r"proposal\s+detail\s+report", re.I)),
    ("participation_agreement", re.compile(r"participation\s+agreement", re.I)),
    ("supplier_invoice", re.compile(r"beacon\s+lighting\s+supply|earthtronics|ship\s*to", re.I)),
    ("contractor_invoice", re.compile(r"\binvoice\b.*\b(install|labor|per\s+fixture)\b", re.I | re.S)),
    ("piece_rate_schedule", re.compile(r"piece\s+rate", re.I)),
]


def find_mtx(text: str | None) -> list[str]:
    """Distinct MTX numbers in order of first appearance, normalised to MTX########."""
    if not text:
        return []
    seen: list[str] = []
    for match in MTX_RE.finditer(text):
        value = "MTX" + match.group(1)
        if value not in seen:
            seen.append(value)
    return seen


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def pdf_text(data: bytes, max_pages: int = 6) -> str:
    """Text layer of the first pages, or '' for scans and unreadable files."""
    if not is_pdf(data):
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - documented requirement
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:  # noqa: BLE001 - any parse failure just means "no text"
        return ""


def doc_type_hint(name: str, text: str = "") -> str:
    for label, pattern in DOC_TYPE_RULES:
        if pattern.search(name or ""):
            return label
    for label, pattern in TEXT_TYPE_RULES:
        if pattern.search(text or ""):
            return label
    return "unknown"


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

STREET_SUFFIX = (
    r"(?:Rd|Road|St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Hwy|Highway|"
    r"Pike|Ct|Court|Cir|Circle|Way|Pkwy|Parkway|Run|Hall|Center|Centre|Plaza|Place|"
    r"Pl|Ter|Terrace|Trl|Trail|Loop|Sq|Square|Mall|Row|Turnpike|Tpke|Path|Walk)"
)
SUITE = r"(?:Suite|Ste\.?|Unit|Apt\.?|Bldg\.?|#)\s*([A-Za-z0-9-]+)"
DIRECTIONALS = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "north", "south", "east", "west"}
_WORD = r"[A-Za-z][A-Za-z.'-]*"

# number [A] Street Name(s) Suffix [, Suite X]
ADDRESS_RE = re.compile(
    rf"(?<![\d-])(\d{{1,6}})\s+(?:([A-Z])\s+)?({_WORD}(?:\s+{_WORD}){{0,3}}?)\s+{STREET_SUFFIX}\.?(?![A-Za-z])"
    rf"(?:[\s,]*{SUITE})?",
    re.IGNORECASE,
)
# number Street Name(s) Suite X   (no street suffix in the text, common in subjects)
ADDRESS_SUITE_RE = re.compile(
    rf"(?<![\d-])(\d{{1,6}})\s+({_WORD}(?:\s+{_WORD}){{0,2}}?)[\s,]+{SUITE}",
    re.IGNORECASE,
)


# Loose form for SHORT text only (subject lines, filenames): number[A] + 1-3 words,
# no street suffix. "5124A Dorsey family dental", "9631 liberty N (vacant)".
ADDRESS_LOOSE_RE = re.compile(
    rf"(?<![\d-])(\d{{2,6}})([A-Z])?\s+({_WORD}(?:\s+{_WORD}){{0,2}})(?![\w-])",
    re.IGNORECASE,
)
LOOSE_STOPWORDS = {
    "bge", "invoice", "invoices", "mtx", "suite", "ste", "unit", "inc", "llc", "and", "for",
    "the", "re", "fw", "fwd", "of", "at", "to", "a", "an", "sensors", "sensor", "fixtures",
    "new", "led", "lights", "payment", "completed", "vacant", "no", "work", "order",
}


@dataclass(frozen=True)
class Address:
    number: str
    stem: str          # first non-directional word of the street name, lowercased
    suite: str | None  # uppercased suite/unit, or None when the text states none

    @property
    def key(self) -> tuple[str, str]:
        return (self.number, self.stem)

    def compatible(self, other: "Address") -> bool:
        if self.key != other.key:
            return False
        if self.suite is None or other.suite is None:
            return True
        return self.suite == other.suite

    def to_dict(self) -> dict:
        return {"number": self.number, "stem": self.stem, "suite": self.suite}

    @classmethod
    def from_dict(cls, d: dict) -> "Address":
        return cls(str(d["number"]), str(d["stem"]).lower(), (d.get("suite") or None))

    def __str__(self) -> str:
        return f"{self.number} {self.stem}" + (f" #{self.suite}" if self.suite else "")


def _stem(street: str) -> str | None:
    for word in re.split(r"\s+", street.strip()):
        clean = re.sub(r"[^a-z0-9]", "", word.lower())
        if clean and clean not in DIRECTIONALS:
            return clean
    return None


def extract_addresses(text: str | None, loose: bool = False) -> set[Address]:
    """Addresses in text. loose=True also accepts number + words with no street
    suffix; use it only on subjects and filenames, never on document bodies."""
    found: set[Address] = set()
    if not text:
        return found
    for match in ADDRESS_RE.finditer(text):
        number, letter, street, suite = match.groups()
        stem = _stem(street)
        if not stem:
            continue
        unit = (suite or letter or "").upper() or None
        found.add(Address(number, stem, unit))
    for match in ADDRESS_SUITE_RE.finditer(text):
        number, street, suite = match.groups()
        stem = _stem(street)
        if not stem:
            continue
        found.add(Address(number, stem, suite.upper()))
    if loose:
        strict_numbers = {a.number for a in found}
        for match in ADDRESS_LOOSE_RE.finditer(text):
            number, letter, street = match.groups()
            if number in strict_numbers:
                continue
            stem = _stem(street)
            if not stem or stem in LOOSE_STOPWORDS or stem.isdigit():
                continue
            found.add(Address(number, stem, letter.upper() if letter else None))
    # Drop a suite-less duplicate when the same site also appears with a suite.
    with_suite = {a.key for a in found if a.suite}
    return {a for a in found if a.suite or a.key not in with_suite}
