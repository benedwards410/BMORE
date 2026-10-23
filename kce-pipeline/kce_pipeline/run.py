"""Batch orchestration: folder in, project JSON + reconciliation report out."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import checks, transform
from .extract import ExtractionError, build_backend, file_readiness
from .normalize import Vocabulary
from .transform import FlagList


@dataclass
class Document:
    """One input file and everything learned about it."""
    path: Path
    name: str
    doc_type: str = "unknown"
    mtx: str | None = None
    confidence: float | None = None
    reason: str | None = None
    raw: dict = field(default_factory=dict)
    error: str | None = None
    excluded: bool = False


def load_config(base_dir: Path) -> tuple[dict, dict]:
    config_dir = base_dir / "config"
    with open(config_dir / "settings.json", "r", encoding="utf-8") as handle:
        settings = json.load(handle)
    with open(config_dir / "canonical_fixtures.json", "r", encoding="utf-8") as handle:
        vocabulary = json.load(handle)
    return settings, vocabulary


def discover(folder: Path, settings: dict) -> list[Path]:
    extensions = {e.lower() for e in settings.get("inputExtensions", [])}
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith("."))


def blank_project() -> dict:
    """The exact top-level shape of section 6.1."""
    return {
        "project": {
            "name": None,
            "poNumber": None,
            "customer": None,
            "address": None,
            "contactName": None,
            "contactPhone": None,
            "revenue": None,
        },
        "supplierLines": [],
        "workOrderLines": [],
        "pieceRates": [],
        "contractorLines": [],
        "otherExpenses": [],
        "modeledCosts": [],
        # Additions beyond the outline's 6.1 shape, same spirit as modeledCosts[]
        # and flags[]: extra keys the ROI tracker ignores but a human needs.
        "inventory": [],
        "credits": [],
        "flags": [],
    }


def run_batch(folder: Path, base_dir: Path, backend_override: str | None = None) -> dict:
    """Process one project folder end to end.

    Never aborts on a single bad file: an unreadable or unclassifiable document
    is skipped and flagged, and the rest of the batch proceeds (section 3).
    """
    settings, vocabulary_config = load_config(base_dir)
    if backend_override:
        settings.setdefault("extraction", {})["backend"] = backend_override

    vocab = Vocabulary(vocabulary_config, settings.get("fuzzyMatchThreshold", 0.82))
    flags = FlagList()
    backend = build_backend(settings, base_dir)

    extensions = {e.lower() for e in settings.get("inputExtensions", [])}

    # -- pass 1: read + classify every file ---------------------------------
    documents: list[Document] = []
    for path in discover(folder, settings):
        doc = Document(path=path, name=path.name)

        if path.suffix.lower() not in extensions:
            doc.doc_type = "unknown"
            doc.error = f"unsupported file type {path.suffix!r}"
            flags.add("§4", "warning",
                      f"{path.name} is not a supported document type "
                      f"({path.suffix or 'no extension'}; the pipeline reads "
                      f"{', '.join(sorted(extensions))}). It was skipped and "
                      f"contributed nothing to the merged output.")
            documents.append(doc)
            continue

        # Pre-flight before spending an API call: a half-synced file reads as a
        # short document rather than an error, so it must be caught here.
        problem, advisory = file_readiness(path)
        if problem:
            doc.error = f"incomplete file -- {problem}"
            flags.add("§3", "critical",
                      f"{path.name} {problem}. It was NOT read, and none of its "
                      f"data is in this report. Anything that document would have "
                      f"contributed is missing -- re-run once the file is fully "
                      f"synced.")
            documents.append(doc)
            continue
        if advisory:
            flags.add("§3", "info", f"{path.name}: {advisory}.")

        try:
            payload = backend.read(path)
        except ExtractionError as exc:
            doc.error = str(exc)
            flags.add("§3", "warning",
                      f"{path.name} could not be read ({exc}). It was skipped; the rest "
                      f"of the batch was processed normally.")
            documents.append(doc)
            continue

        classification = payload.get("classification", {})
        doc.raw = payload.get("extraction", {}) or {}
        doc.doc_type = classification.get("docType", "unknown")
        doc.mtx = classification.get("mtx")
        doc.confidence = classification.get("confidence")
        doc.reason = classification.get("reason")

        if doc.doc_type == "unknown":
            flags.add("§4", "warning",
                      f"{path.name} could not be classified into any of the five known "
                      f"document types ({doc.reason or 'no reason given'}). It was "
                      f"skipped.")
        documents.append(doc)

    # -- 8.9: batch consistency before any merging --------------------------
    agreed_mtx, excluded = checks.check_mtx_consistency(documents, settings, flags)
    for doc in documents:
        if doc.name in excluded:
            doc.excluded = True

    # -- pass 2: type-specific transforms -----------------------------------
    project = blank_project()
    metas: list[tuple[str, dict]] = []
    reported_subtotals = None
    size_class_rows: list[dict] = []

    usable = [d for d in documents if not d.excluded and not d.error
              and d.doc_type != "unknown"]

    for doc in usable:
        source_doc = _source_label(doc)

        if doc.doc_type == "piece_rate_schedule":
            project["pieceRates"].extend(
                transform.transform_piece_rates(doc.raw, vocab, flags, source_doc))

        elif doc.doc_type == "supplier_invoice":
            project["supplierLines"].extend(
                transform.transform_supplier_invoice(doc.raw, vocab, flags, source_doc))

        elif doc.doc_type == "proposal_detail":
            meta, lines = transform.transform_proposal_detail(
                doc.raw, vocab, flags, source_doc)
            metas.append((source_doc, meta))
            project["workOrderLines"].extend(lines)
            size_class_rows.extend(
                {"sourceDoc": source_doc, "location": r["location"],
                 "fixtureType": r["fixtureType"], "sizeClass": r["sizeClass"],
                 "qty": r["qtyApproved"]} for r in lines)

        elif doc.doc_type == "detailed_cost":
            result = transform.transform_detailed_cost(
                doc.raw, vocab, flags, source_doc,
                settings.get("centsTolerance", 0.005))
            metas.append((source_doc, result["meta"]))
            project["modeledCosts"].extend(result["modeledCosts"])
            project["supplierLines"].extend(result["supplierLines"])
            project["otherExpenses"].extend(result["otherExpenses"])
            reported_subtotals = result["reportedLightingTotals"]
            # Confirm the report's own arithmetic: Lighting + Miscellaneous
            # should equal the SubTotals line it prints.
            misc = result.get("reportedMiscTotals")
            whole = result.get("reportedSubTotals")
            if misc is not None and whole is not None and reported_subtotals is not None:
                if abs((reported_subtotals + misc) - whole) > settings.get(
                        "centsTolerance", 0.005):
                    flags.add("§4.4", "warning",
                              f"The Detailed Cost Report's own totals do not add up: "
                              f"Lighting ${reported_subtotals:,.2f} + Miscellaneous "
                              f"${misc:,.2f} = ${reported_subtotals + misc:,.2f}, but "
                              f"it prints SubTotals ${whole:,.2f}. Check the "
                              f"extraction against the PDF.")
            size_class_rows.extend(
                {"sourceDoc": source_doc, "location": r["location"],
                 "fixtureType": r["fixtureType"], "sizeClass": r["sizeClass"],
                 "qty": r["qty"]} for r in result["modeledCosts"])

        elif doc.doc_type == "inventory_reconciliation":
            project["inventory"].extend(
                transform.transform_inventory(doc.raw, vocab, flags, source_doc))

        elif doc.doc_type == "credit_calculation":
            project["credits"].extend(
                transform.transform_credit_calculation(doc.raw, vocab, flags, source_doc))

        elif doc.doc_type == "contractor_invoice":
            fixtures, others = transform.transform_contractor_invoice(
                doc.raw, vocab, flags, source_doc)
            project["contractorLines"].extend(fixtures)
            project["otherExpenses"].extend(others)

    # -- piece rates: standard card as the default, deviations made visible --
    apply_piece_rate_policy(project, base_dir, flags)

    # -- 8.4: work-order fallback -------------------------------------------
    if not project["workOrderLines"] and project["modeledCosts"]:
        flags.add("§8.4", "warning",
                  "No Proposal Detail report is present in this batch, so approved "
                  "quantities were derived from the Detailed Cost Report as a "
                  "fallback. Its Material/Labor row pairs were de-duplicated to one "
                  "work-order row per fixture per location. Confirm against the real "
                  "proposal when it arrives.")
        for row in project["modeledCosts"]:
            project["workOrderLines"].append({
                "location": row["location"],
                "fixtureType": row["fixtureType"],
                "sizeClass": row.get("sizeClass"),
                "qtyApproved": row["qty"],
                "watts": None,
                "source": "detailed_cost_fallback",
                "sourceDoc": row["sourceDoc"],
                "sourceLine": row["line"],
                "sourceDescription": None,
            })

    # -- project metadata (section 5) ---------------------------------------
    # Proposal Detail wins as the working value; conflicts are flagged, not hidden.
    ordered_metas = sorted(metas, key=lambda m: 0 if "Proposal" in m[0] else 1)
    for _, meta in reversed(ordered_metas):
        for key in project["project"]:
            if key == "revenue":
                continue
            if meta.get(key):
                project["project"][key] = meta[key]

    if agreed_mtx and not project["project"]["poNumber"]:
        project["project"]["poNumber"] = agreed_mtx

    checks.check_metadata_conflicts(metas, flags)
    checks.check_revenue(flags)

    # -- section 8 checks ---------------------------------------------------
    checks.check_sensor_size_classes(size_class_rows, vocab, settings, flags)
    checks.check_sensor_tier_disagreement(project, vocab, flags)
    checks.check_modeled_vs_actual(project, flags)
    checks.check_missing_actual_material(project, vocab, flags)
    checks.check_blended_rates(project, flags)
    checks.check_wattage_tiers(project, vocab, flags)
    reconciliation = checks.check_quantities(project, vocab, settings, flags)
    subtotals = checks.check_modeled_subtotals(project, reported_subtotals, settings, flags)
    checks.check_inventory(project, reconciliation, vocab, flags)
    checks.check_credits(project, flags)
    checks.check_unit_cost_consistency(project, flags)

    project["flags"] = flags.sorted()

    return {
        "project": project,
        "documents": documents,
        "reconciliation": reconciliation,
        "subtotals": subtotals,
        "mtx": agreed_mtx,
        "backend": backend.name,
        "settings": settings,
        "vocab": vocab,
    }


def apply_piece_rate_policy(project: dict, base_dir: Path, flags) -> None:
    """Fall back to the standard KCE rate card, and flag any project deviation.

    Most projects use the standing card, so a batch with no rate schedule of its
    own gets it automatically rather than producing an empty pieceRates[]. A
    project that DOES supply its own card keeps it -- that card wins -- but every
    rate that differs from standard is surfaced, because a deviation is a
    commercial decision someone made and should be visible rather than silent
    (e.g. Bob Bell runs -$2/fixture because the install and the sensor
    commissioning were done by different contractors).
    """
    standard_path = base_dir / "config" / "standard_piece_rates.json"
    if not standard_path.exists():
        return

    with open(standard_path, "r", encoding="utf-8") as handle:
        standard = json.load(handle)
    standard_rates = {(r["fixtureType"], r["wattageTier"]): r["contractedRate"]
                      for r in standard.get("rates", [])}

    if not project["pieceRates"]:
        for (fixture_type, tier), rate in standard_rates.items():
            project["pieceRates"].append({
                "fixtureType": fixture_type,
                "wattageTier": tier,
                "contractedRate": rate,
                "source": "standard_rate_card",
                "sourceDoc": f"KCE Standard Piece Rate Schedule "
                             f"({standard.get('effectiveDate', 'undated')})",
                "sourceDescription": None,
            })
        flags.add("§4.1", "info",
                  f"No piece rate schedule was supplied with this project, so KCE's "
                  f"standard rate card ({len(standard_rates)} rates, effective "
                  f"{standard.get('effectiveDate', 'undated')}) was applied. Drop a "
                  f"project-specific schedule in the folder to override it.")
        return

    # A project-specific card is present -- keep it, but report the differences.
    supplied = {(r["fixtureType"], r["wattageTier"]): r["contractedRate"]
                for r in project["pieceRates"]}

    # A project card often states a category untiered ("High Bay $73") where the
    # standard card tiers it. Fall back to comparing against the fixture type's
    # standard rate when every tier of that type prices the same.
    by_type: dict = {}
    for (fixture_type, tier), rate in standard_rates.items():
        by_type.setdefault(fixture_type, set()).add(rate)

    deviations, ambiguous = [], []
    for key, rate in sorted(supplied.items(), key=lambda kv: str(kv[0])):
        fixture_type, tier = key
        if key in standard_rates:
            reference = standard_rates[key]
        elif fixture_type in by_type and len(by_type[fixture_type]) == 1:
            reference = next(iter(by_type[fixture_type]))
        elif fixture_type in by_type:
            ambiguous.append(
                f"{fixture_type} ${rate:.2f} (standard tiers price at "
                f"{', '.join(f'${r:.2f}' for r in sorted(by_type[fixture_type]))})")
            continue
        else:
            continue

        if abs(reference - rate) > 0.005:
            delta = rate - reference
            deviations.append(
                f"{fixture_type}{' ' + tier if tier else ''} "
                f"${rate:.2f} vs standard ${reference:.2f} "
                f"({'+' if delta > 0 else ''}{delta:.2f})")

    if ambiguous:
        flags.add("§4.1", "warning",
                  f"The project rate schedule states {len(ambiguous)} categor(ies) "
                  f"without a wattage tier where the standard card tiers them, and "
                  f"the standard tiers do not share one rate, so no comparison could "
                  f"be made: {'; '.join(ambiguous)}.")

    if deviations:
        flags.add("§4.1", "warning",
                  f"This project supplies its own piece rate schedule and "
                  f"{len(deviations)} rate(s) deviate from KCE's standard card: "
                  f"{'; '.join(deviations)}. The project's rates are being used. "
                  f"Confirm the deviation is intentional.")

    missing = [k for k in standard_rates if k not in supplied]
    if missing:
        flags.add("§4.1", "info",
                  f"The project's rate schedule covers {len(supplied)} of the "
                  f"{len(standard_rates)} categories on KCE's standard card. "
                  f"Fixture types billed on this job but absent from the project "
                  f"card have no contracted rate to compare against.")


def _source_label(doc: Document) -> str:
    """A short, human-meaningful name for the document a line came from."""
    raw = doc.raw or {}
    vendor = (raw.get("vendor") or "").strip()
    number = (raw.get("invoiceNumber") or "").strip()

    if doc.doc_type == "supplier_invoice" and vendor:
        return f"{vendor} Invoice #{number}" if number else f"{vendor} Invoice"
    if doc.doc_type == "contractor_invoice" and vendor:
        return f"{vendor} Invoice #{number}" if number else f"{vendor} Invoice"
    if doc.doc_type == "proposal_detail":
        return "BGE Proposal Detail Report"
    if doc.doc_type == "detailed_cost":
        return "BGE Detailed Cost Report"
    if doc.doc_type == "piece_rate_schedule":
        return "KCE Piece Rate Schedule"
    return doc.name
