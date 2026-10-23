"""Document reading: classification pass + type-specific extraction pass.

Task outline 3 prescribes a two-pass design -- "(1) a cheap classification pass
per file (which of the 5 types is this?), (2) a type-specific extraction pass
using that type's dedicated prompt/schema. Do not use one giant prompt trying to
handle all 5 types at once."

Two interchangeable backends implement those passes:

  AnthropicBackend  -- the real thing. Sends the PDF as a document content block
                       and asks Claude for JSON. Requires ANTHROPIC_API_KEY and
                       the `anthropic` package.
  CacheBackend      -- replays a previously captured extraction from
                       extraction_cache/, keyed by sha256 of the file bytes.

Both return the same raw per-document payload, so every downstream stage
(classification routing, normalization, accessory grouping, sensor validation,
reconciliation, reporting) is identical no matter which backend produced it.
The cache doubles as a regression fixture: `--backend cache` reruns the whole
batch offline and deterministically.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
from pathlib import Path


# --------------------------------------------------------------------------
# prompts -- one per document type, plus the classifier
# --------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are classifying a single document from a commercial LED
lighting retrofit project for Key Commercial Electric (KCE).

Choose exactly one docType:

- "piece_rate_schedule": KCE's own standing subcontractor rate card. Lists fixture
  categories and per-unit install rates. NOT project-specific, has NO MTX number.
- "supplier_invoice": an invoice from an electrical supply house / distributor for
  materials KCE purchased (SKUs, qty, unit price, invoice number).
- "proposal_detail": a BGE "Proposal Detail Report" -- the utility's approved scope.
  Has Existing Description / Proposed Description columns and Qty/Watts/Hrs/KWH.
- "detailed_cost": a BGE "Detailed Cost Report" -- the utility's priced-out model.
  Recognizable by a Component/Type column splitting each line into Material and
  Labor rows AND a Program Share / Customer Share cost split.
- "contractor_invoice": an invoice from the subcontractor crew that installed the
  fixtures, billed back to KCE. Has NO Program Share / Customer Share columns.
- "inventory_reconciliation": a KCE stock sheet reconciling material DELIVERED to
  a job against what REMAINS unused. Recognizable by columns like "Total
  delivered" and "Remaining", one row per fixture type, usually with an Item
  ID/SKU column. It is not an invoice -- it has no prices.
- "credit_calculation": an internal KCE memo recomputing a contractor's invoice at
  corrected piece rates to derive a credit or overcharge. Recognizable by paired
  "Billed Rate"/"Correct Rate" or "Billed $"/"Correct $" columns and a
  "Credit Due" or "Overcharge" total.
- "unknown": anything that is not one of the types above.

Also report the MTX/project number if one appears anywhere (format like
"MTX79857647"), else null.

Return ONLY raw JSON, no markdown fences:
{"docType": "...", "confidence": 0.0-1.0, "mtx": "MTX..." or null, "reason": "one short sentence"}"""


EXTRACT_PROMPTS = {
    "piece_rate_schedule": """Read this KCE subcontractor piece rate schedule and
return EVERY rate row exactly as printed. Do not normalize, merge, expand size
ranges, or skip rows -- downstream code does all of that. Transcribe faithfully,
including any typos in the rate cell (e.g. "$30..00" must come back as "$30..00").

Return ONLY raw JSON:
{"rows": [{"section": "section heading the row sits under",
           "description": "the Fixture / Item Description cell verbatim",
           "installUnit": "the Install Unit cell verbatim or null",
           "rateText": "the Rate cell verbatim, including a literal 'Included'"}],
 "notes": "the footnote/notes block verbatim, or null"}""",

    "supplier_invoice": """Read this supplier/distributor invoice for LED fixtures.

Extract EVERY product line, including accessory/component lines (photocells, EM
battery backup modules, mounting hardware, sensor lens kits) as their OWN line --
never merge an accessory into another line and never inflate another line's
quantity with it.

Return ONLY raw JSON:
{"vendor": "...", "invoiceNumber": "...", "invoiceDate": "MM/DD/YYYY or null",
 "mtx": "MTX... or null", "projectName": "... or null",
 "lines": [{"sku": "product/service code or null", "description": "verbatim",
            "qty": number, "unitPrice": number, "amount": number}],
 "total": number or null}""",

    "proposal_detail": """Read this BGE "Proposal Detail Report" for a lighting retrofit.

Extract the Project Summary metadata and EVERY row of the Lighting table,
including any dedicated sensor row (usually Location "Sensors"). For a sensor row
the Existing Description states the fixture size/wattage the sensors correspond
to -- transcribe it verbatim, it is how the size class is later derived.

Use the PROPOSED columns for qty/watts, not the Existing ones, but return the
existing description text too.

Return ONLY raw JSON:
{"meta": {"customer": "the name after 'Proposal Detail Report for'",
          "address": "address block under the title",
          "reportDate": "...", "auditProposal": "the Audit / Proposal field verbatim",
          "accountNumber": "...", "contactName": "...", "contactPhone": "...",
          "auditorName": "...", "auditDate": "..."},
 "lines": [{"line": number, "location": "...",
            "existingDescription": "verbatim", "existingQty": number or null,
            "proposedDescription": "verbatim", "qty": number,
            "watts": number or null}],
 "totals": {"proposedWatts": number or null, "proposedKwh": number or null,
            "savings": number or null}}""",

    "detailed_cost": """Read this BGE "Detailed Cost Report" for a lighting retrofit.

Extract EVERY row of the Lighting table -- not just the fee rows at the bottom.
Each row has a Line number, Location, Proposed Equipment, Component, Type
(Material or Labor), Quantity, Price, Program Share and Customer Share. Rows
sharing a Line number belong together: a line may carry more than one Material
row (a fixture plus an accessory such as a photocell) plus one Labor row.

Transcribe every row separately and verbatim. Do NOT sum, group, or drop rows --
downstream code does the grouping.

IMPORTANT -- this report may contain MORE THAN ONE table. There is always a
"Lighting" table. There is often ALSO a "Miscellaneous" table below it, holding
non-fixture costs (lift fees, scissor/boom lift rental, other labor, wiring,
troubleshooting, permits). The Miscellaneous table restarts its own Line
numbering at 1, so its Line numbers COLLIDE with the Lighting table's -- keep the
two tables in separate arrays and never merge them.

Each table has its own Totals row. The report's SubTotals equals the Lighting
Totals PLUS the Miscellaneous Totals. Report each separately so downstream code
can check them independently. If there is no Miscellaneous table, return an
empty miscRows array and null for miscTotals.

Also extract the summary block (SubTotals, Recycling Fee, Sales Tax, Work Order
Totals) and the Project Summary metadata.

Return ONLY raw JSON:
{"meta": {"customer": "...", "address": "...", "reportDate": "...",
          "auditProposal": "verbatim", "accountNumber": "...", "contactName": "...",
          "contactPhone": "...", "auditorName": "...", "auditDate": "..."},
 "rows": [{"line": number, "location": "...", "proposedEquipment": "verbatim",
           "component": "verbatim", "type": "Material" or "Labor",
           "qty": number, "price": number,
           "programShare": number, "customerShare": number}],
 "miscRows": [{"line": number, "location": "...", "proposedEquipment": "verbatim",
               "component": "verbatim", "type": "Material" or "Labor",
               "qty": number, "price": number,
               "programShare": number, "customerShare": number}],
 "summary": {"lightingTotals": number, "miscTotals": number or null,
             "subTotals": number, "workOrderTotals": number or null},
 "feeRows": [{"label": "Recycling Fee", "price": number,
              "programShare": number or null, "customerShare": number or null}]}""",

    "contractor_invoice": """Read this installer/subcontractor invoice for a lighting
retrofit job -- an actual bill the installer sent KCE for payment.

SAFETY CHECK FIRST: if this document has Program Share / Customer Share columns it
is a utility cost allocation, NOT a contractor invoice. In that case return
{"isCostAllocation": true, "lines": []} and extract nothing else.

Otherwise extract EVERY line in one pass -- both per-fixture lines and flat
non-fixture service lines (trip charge, material pickup, disposal, scrap removal,
mobilization, permit). Do not decide which is which; transcribe them all and let
downstream code route them.

Transcribe any explanatory note attached to a line verbatim into "note" -- notes
like "$60 install and $50 fixture price" are the ONLY evidence that a rate bundles
material with labor, and code depends on that exact text.

Return ONLY raw JSON:
{"isCostAllocation": false, "vendor": "...", "invoiceNumber": "...",
 "date": "MM/DD/YYYY or null", "mtx": "MTX... or null",
 "billTo": "... or null", "projectName": "... or null",
 "lines": [{"service": number or null, "description": "verbatim, first line only",
            "note": "verbatim explanatory note attached to the line, or null",
            "unitPrice": number or null, "qty": number or null,
            "lineTotal": number or null}],
 "total": number or null}""",

    "inventory_reconciliation": """Read this KCE inventory reconciliation sheet.

It reconciles material DELIVERED to a job against what REMAINS unused. Extract
every row exactly as printed, including rows describing pre-existing stock rather
than this job's deliveries, and any handwritten-style note in a Note column (e.g.
"Justn -14" recording units transferred to another job or crew).

The Item ID / SKU column is the authoritative identifier -- transcribe it exactly,
including any hyphens, and do not merge two rows that share a SKU but differ in
their description or note.

Return ONLY raw JSON:
{"rows": [{"description": "the Fixture Type cell verbatim",
           "sku": "the Item ID / SKU cell verbatim, or null",
           "delivered": number or null,
           "remaining": number or null,
           "note": "the Note cell verbatim, or null"}]}""",

    "credit_calculation": """Read this piece-rate credit calculation memo.

It recomputes one or more contractor invoices at corrected piece rates to derive a
credit. Extract every per-invoice section and its fixture rows, plus the combined
summary if one is present.

Return ONLY raw JSON:
{"job": "job name or null", "mtx": "MTX... or null",
 "contractor": "the contractor being credited, or null",
 "correctedRateNote": "the 'Corrected piece rates:' line verbatim, or null",
 "invoices": [{"invoiceNumber": "...", "date": "...",
               "billedTotal": number or null, "correctedTotal": number or null,
               "creditDue": number or null,
               "rows": [{"description": "fixture type verbatim", "qty": number,
                         "billedRate": number, "billedAmount": number,
                         "correctRate": number, "correctAmount": number,
                         "overcharge": number}]}],
 "totalCreditDue": number or null}""",
}


# --------------------------------------------------------------------------
# cache addressing
# --------------------------------------------------------------------------

def file_digest(path: Path) -> str:
    """sha256 of the file's bytes -- the cache key.

    Content-addressed on purpose: renaming a document does not invalidate its
    cached extraction, and editing one silently cannot reuse a stale entry.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ExtractionError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# pre-flight: is this file actually all here?
# --------------------------------------------------------------------------

# OneDrive "Files On-Demand" attributes. A dehydrated file still READS fine --
# Windows recalls it transparently -- so these are advisory, not fatal. What IS
# fatal is a physically incomplete file, which the content checks below catch.
_ATTR_OFFLINE = 0x1000
_ATTR_RECALL_ON_OPEN = 0x40000
_ATTR_RECALL_ON_DATA_ACCESS = 0x400000
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

_MIN_PLAUSIBLE_BYTES = 512


def cloud_placeholder_state(path: Path) -> str | None:
    """Report OneDrive placeholder attributes, or None. Windows-only."""
    if os.name != "nt":
        return None
    try:
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    except (AttributeError, OSError):  # pragma: no cover - platform dependent
        return None
    if attributes == _INVALID_FILE_ATTRIBUTES:
        return None

    flags = []
    if attributes & _ATTR_OFFLINE:
        flags.append("OFFLINE")
    if attributes & _ATTR_RECALL_ON_OPEN:
        flags.append("RECALL_ON_OPEN")
    if attributes & _ATTR_RECALL_ON_DATA_ACCESS:
        flags.append("RECALL_ON_DATA_ACCESS")
    return ", ".join(flags) or None


def file_readiness(path: Path) -> tuple[str | None, str | None]:
    """Check a file is complete BEFORE spending an API call reading it.

    Returns (problem, advisory). A `problem` means do not read this file. An
    `advisory` is worth reporting but does not block the read.

    This exists because a half-synced PDF does not fail loudly. The model reads
    whatever bytes are present and returns fewer rows, and only the Detailed Cost
    Report carries a stated total to cross-check against -- a truncated supplier
    or contractor invoice would produce a plausible, silently wrong answer, which
    is the worst outcome this tool can have.
    """
    advisory = None
    state = cloud_placeholder_state(path)
    if state:
        advisory = (f"OneDrive lists this file as a cloud placeholder ({state}); "
                    f"it had to be recalled from the cloud to be read")

    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"could not be opened ({exc.strerror or exc})", advisory

    if size == 0:
        return "is 0 bytes -- it is still syncing, or the download failed", advisory
    if size < _MIN_PLAUSIBLE_BYTES:
        return (f"is only {size} bytes, far too small to be a real document -- "
                f"it is probably still syncing"), advisory

    if path.suffix.lower() == ".pdf":
        try:
            with open(path, "rb") as handle:
                head = handle.read(1024)
                handle.seek(max(0, size - 2048))
                tail = handle.read(2048)
        except OSError as exc:
            return f"could not be read ({exc.strerror or exc})", advisory

        if b"%PDF" not in head:
            return ("does not begin with a PDF header -- the file is corrupt or "
                    "still downloading"), advisory
        # A complete PDF ends with %%EOF. Its absence is the clearest available
        # signal that a transfer stopped part-way.
        if b"%%EOF" not in tail:
            return ("is missing its end-of-file marker, so it is TRUNCATED -- "
                    "wait for OneDrive to finish syncing, then run again"), advisory

    return None, advisory


# --------------------------------------------------------------------------
# backends
# --------------------------------------------------------------------------

class CacheBackend:
    """Replay a captured extraction. Deterministic, offline, no API spend."""

    name = "cache"

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def read(self, path: Path) -> dict:
        key = file_digest(path)
        entry = self.cache_dir / f"{key}.json"
        if not entry.exists():
            raise ExtractionError(
                f"no cached extraction for {path.name} (sha256 {key[:12]}...). "
                f"Run with --backend api and ANTHROPIC_API_KEY set to create one, "
                f"or add {entry.name} to {self.cache_dir}."
            )
        with open(entry, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload.setdefault("_meta", {})["backend"] = "cache"
        return payload


class AnthropicBackend:
    """Live two-pass read through Claude's native PDF/vision understanding."""

    name = "api"

    def __init__(self, cache_dir: Path, model: str, max_tokens: int):
        self.cache_dir = Path(cache_dir)
        self.model = model
        self.max_tokens = max_tokens
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ExtractionError(
                "the `anthropic` package is not installed -- run `pip install anthropic`"
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ExtractionError("ANTHROPIC_API_KEY is not set")
        from anthropic import Anthropic
        self.client = Anthropic()

    # -- plumbing ----------------------------------------------------------

    def _document_block(self, path: Path) -> dict:
        import base64
        data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return {"type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
        media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".webp": "image/webp", ".gif": "image/gif"}.get(suffix)
        if not media:
            raise ExtractionError(f"unsupported input type: {path.suffix}")
        return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}

    def _ask(self, path: Path, prompt: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": [self._document_block(path),
                                                   {"type": "text", "text": prompt}]}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return _loads_lenient(text)

    # -- two passes --------------------------------------------------------

    def read(self, path: Path) -> dict:
        classification = self._ask(path, CLASSIFY_PROMPT)
        doc_type = classification.get("docType", "unknown")

        extraction = {}
        if doc_type in EXTRACT_PROMPTS:
            extraction = self._ask(path, EXTRACT_PROMPTS[doc_type])

        payload = {
            "_meta": {"backend": "api", "model": self.model,
                      "sourceFile": path.name, "sha256": file_digest(path)},
            "classification": classification,
            "extraction": extraction,
        }
        self._write_cache(path, payload)
        return payload

    def _write_cache(self, path: Path, payload: dict) -> None:
        """Every live read backfills the cache, so any run can be replayed."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        entry = self.cache_dir / f"{file_digest(path)}.json"
        with open(entry, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")


def _loads_lenient(text: str) -> dict:
    """Parse model JSON, tolerating stray markdown fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end > start:
            return json.loads(stripped[start:end + 1])
        raise


def build_backend(settings: dict, base_dir: Path):
    """Resolve the configured backend, honouring 'auto'."""
    extraction = settings.get("extraction", {})
    choice = extraction.get("backend", "auto")
    cache_dir = base_dir / extraction.get("cacheDir", "extraction_cache")

    if choice == "cache":
        return CacheBackend(cache_dir)
    if choice == "api":
        return AnthropicBackend(cache_dir, extraction.get("model"), extraction.get("maxTokens", 16000))

    # auto: prefer the live API, fall back to replay.
    try:
        return AnthropicBackend(cache_dir, extraction.get("model"), extraction.get("maxTokens", 16000))
    except ExtractionError:
        return CacheBackend(cache_dir)
