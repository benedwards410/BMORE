"""Cross-document checks -- the nine behaviors of section 8, plus section 5's
revenue exclusion and section 4.4's batch total self-check.

Every function here only ever APPENDS to flags[]. Nothing in this module edits,
reconciles, or drops a line item: "Never let the pipeline auto-resolve a
disagreement by picking one source over another and discarding the other
silently" (section 7).
"""

from __future__ import annotations

from collections import defaultdict

# Label for the combined sensor bucket in the 8.8 reconciliation (see check_quantities).
SENSOR_POOL = "Sensor (all tiers)"


# --------------------------------------------------------------------------
# 8.9 batch consistency (MTX number)
# --------------------------------------------------------------------------

def check_mtx_consistency(documents: list, settings: dict, flags) -> tuple[str | None, set]:
    """Verify every project-specific document names the same MTX number.

    Returns (agreed_mtx, excluded_filenames). Documents whose MTX disagrees are
    excluded from the merge entirely; the rest of the batch processes normally.
    """
    exempt = set(settings.get("mtxExemptTypes", []))
    counts: dict = defaultdict(list)

    for doc in documents:
        if doc.doc_type in exempt or doc.doc_type == "unknown":
            continue
        if not doc.mtx:
            flags.add("§8.9", "warning",
                      f"{doc.name} is a project-specific document ({doc.doc_type}) but "
                      f"no MTX/PO number could be read from it, so it could not be "
                      f"included in the batch consistency check. Its data was still "
                      f"merged -- confirm it belongs to this project.")
            continue
        counts[doc.mtx].append(doc.name)

    if not counts:
        return None, set()

    # The majority MTX wins as the project's identity; ties break on document count.
    agreed = max(counts.items(), key=lambda item: (len(item[1]), item[0]))[0]
    excluded: set = set()

    for mtx, names in counts.items():
        if mtx == agreed:
            continue
        for name in names:
            excluded.add(name)
            flags.add("§8.9", "critical",
                      f"{name} references {mtx}, but the rest of the batch references "
                      f"{agreed}. Its extracted data was EXCLUDED from the merged "
                      f"output. Confirm whether this file belongs to this project.")

    return agreed, excluded


# --------------------------------------------------------------------------
# 5 project metadata
# --------------------------------------------------------------------------

def check_metadata_conflicts(metas: list[tuple[str, dict]], flags) -> None:
    """Record disagreements between BGE documents instead of silently picking one.

    Section 5: a differing auditor name "happens in real data and is usually
    benign" -- record both under an info-severity flag.
    """
    fields = ["name", "poNumber", "customer", "address", "contactName",
              "contactPhone", "auditorName"]

    for field in fields:
        values: dict = defaultdict(list)
        for source_doc, meta in metas:
            value = meta.get(field)
            if value:
                values[value].append(source_doc)
        if len(values) > 1:
            rendered = "; ".join(f"{value!r} (from {', '.join(docs)})"
                                 for value, docs in values.items())
            flags.add("§5", "info",
                      f"BGE documents disagree on {field}: {rendered}. Both values are "
                      f"recorded; the Proposal Detail value is used as the working "
                      f"value.")


def check_revenue(flags) -> None:
    """Section 5: leave revenue null, always, with no exceptions."""
    flags.add("§5", "warning",
              "revenue was deliberately NOT auto-filled. The Detailed Cost Report's "
              "Work Order Totals is BGE's modeled system cost, not KCE's revenue from "
              "the customer -- treating one as the other would corrupt every "
              "downstream ROI calculation. Enter revenue manually.")


# --------------------------------------------------------------------------
# 8.6 sensor size-class validation and tier disagreement
# --------------------------------------------------------------------------

def check_sensor_size_classes(doc_rows: list[dict], vocab, settings, flags) -> None:
    """Validate every sensor row's quantity against its size class, per document.

    Section 8.6: a sensor row's quantity is "the sum of every fixture row in that
    same document sharing the same base size class" -- summed by the coarse
    sizeClass, never by canonical fixtureType, so 4' Strips and 2x4 Volumetric
    Kits both count toward one "4ft sensors" row.
    """
    policy = settings.get("sensorSizeClassUnknownPolicy", "skip_with_info")

    by_doc: dict = defaultdict(list)
    for row in doc_rows:
        by_doc[row["sourceDoc"]].append(row)

    # A size class stated on any document, for the 'borrow_from_sibling' policy.
    sibling_classes = {
        row["sizeClass"] for row in doc_rows
        if vocab.is_sensor(row["fixtureType"]) and row["sizeClass"]
    }

    for source_doc, rows in by_doc.items():
        sensor_rows = [r for r in rows if vocab.is_sensor(r["fixtureType"])]
        if not sensor_rows:
            continue

        fixture_rows = [r for r in rows
                        if not vocab.is_sensor(r["fixtureType"])
                        and not vocab.is_component(r["fixtureType"])]

        unknown = [r for r in sensor_rows if not r["sizeClass"]]
        known = [r for r in sensor_rows if r["sizeClass"]]

        # -- rows that DO state a size class: the check section 8.6 specifies --
        for row in known:
            expected = sum(r["qty"] or 0 for r in fixture_rows
                           if r["sizeClass"] == row["sizeClass"])
            actual = row["qty"] or 0
            contributors = [f"{r['location']} {r['fixtureType']} {r['qty']}"
                            for r in fixture_rows if r["sizeClass"] == row["sizeClass"]]
            if actual != expected:
                flags.add("§8.6", "critical",
                          f"Sensor row on {source_doc} ({row['location']!r}, size class "
                          f"{row['sizeClass']}) has qty {actual}, but the "
                          f"{row['sizeClass']}-class fixture rows on that same document "
                          f"sum to {expected} ({'; '.join(contributors) or 'none'}). "
                          f"Either the extraction is wrong or the source document is "
                          f"internally inconsistent.",
                          row["fixtureType"])

        if not unknown:
            continue

        # -- rows that state NO size class: not covered by section 8.6 ---------
        if policy == "skip_with_info":
            for row in unknown:
                flags.add("§8.6", "info",
                          f"Sensor row on {source_doc} ({row['location']!r}, "
                          f"{row['fixtureType']}, qty {row['qty']}) states no size "
                          f"class in its Location or description, so the size-class "
                          f"quantity validation was SKIPPED for it rather than "
                          f"guessed. (Pipeline policy "
                          f"sensorSizeClassUnknownPolicy=skip_with_info.)",
                          row["fixtureType"])

        elif policy == "document_totals":
            sensor_total = sum(r["qty"] or 0 for r in sensor_rows)
            classes = {r["sizeClass"] for r in fixture_rows if r["sizeClass"]}
            fixture_total = sum(r["qty"] or 0 for r in fixture_rows if r["sizeClass"])
            severity = "info" if sensor_total == fixture_total else "critical"
            flags.add("§8.6", severity,
                      f"{source_doc} has {len(unknown)} sensor row(s) with no stated "
                      f"size class. Under policy document_totals, all sensor rows "
                      f"({sensor_total}) were compared against all size-class-bearing "
                      f"fixture rows ({fixture_total}, classes "
                      f"{sorted(classes) or 'none'}): "
                      f"{'match' if sensor_total == fixture_total else 'MISMATCH'}.")

        elif policy == "borrow_from_sibling":
            candidates = sorted(sibling_classes)
            if len(candidates) == 1:
                borrowed = candidates[0]
                sensor_total = sum(r["qty"] or 0 for r in sensor_rows)
                expected = sum(r["qty"] or 0 for r in fixture_rows
                               if r["sizeClass"] == borrowed)
                severity = "info" if sensor_total == expected else "critical"
                flags.add("§8.6", severity,
                          f"{source_doc}'s sensor rows state no size class; class "
                          f"{borrowed!r} was borrowed from another document in the "
                          f"batch. Combined sensor qty {sensor_total} vs "
                          f"{borrowed}-class fixtures {expected}: "
                          f"{'match' if sensor_total == expected else 'MISMATCH'}.")
            else:
                flags.add("§8.6", "warning",
                          f"{source_doc}'s sensor rows state no size class and the "
                          f"batch offers {len(candidates)} candidate classes "
                          f"({candidates}), so none could be borrowed unambiguously. "
                          f"Size-class validation skipped.")


def check_sensor_tier_disagreement(project: dict, vocab, flags) -> None:
    """Compare how each document splits its sensor total across tiers (8.6).

    Equal totals with a different Basic/Advance split is a real, common
    disagreement -- cite both breakdowns rather than picking one.
    """
    breakdowns: dict = defaultdict(lambda: defaultdict(int))

    for row in project.get("workOrderLines", []):
        if vocab.is_sensor(row["fixtureType"]):
            breakdowns[row["sourceDoc"]][row["fixtureType"]] += row.get("qtyApproved") or 0
    for row in project.get("modeledCosts", []):
        if vocab.is_sensor(row["fixtureType"]):
            breakdowns[row["sourceDoc"]][row["fixtureType"]] += row.get("qty") or 0
    for row in project.get("supplierLines", []):
        if vocab.is_sensor(row["fixtureType"]) and row.get("source") == "actual_invoice":
            breakdowns[row["sourceDoc"]][row["fixtureType"]] += row.get("qtyOrdered") or 0

    if len(breakdowns) < 2:
        return

    def render(split: dict) -> str:
        return " + ".join(f"{qty} {tier.replace('Sensor - ', '')}"
                          for tier, qty in sorted(split.items()))

    splits = {doc: dict(split) for doc, split in breakdowns.items()}
    distinct = {tuple(sorted(split.items())) for split in splits.values()}
    if len(distinct) < 2:
        return

    totals = {doc: sum(split.values()) for doc, split in splits.items()}
    rendered = "; ".join(f"{doc} says {render(split)} (total {totals[doc]})"
                         for doc, split in splits.items())

    # Same total, different split = a tier disagreement. Different totals is a
    # quantity problem too, so escalate.
    severity = "warning" if len(set(totals.values())) == 1 else "critical"
    flags.add("§8.6", severity,
              f"Documents disagree on the sensor tier breakdown: {rendered}. "
              f"{'Totals agree, so this is a tier-split disagreement only. ' if severity == 'warning' else 'The totals also disagree. '}"
              f"Both breakdowns are recorded; a human must decide which is authoritative.")


# --------------------------------------------------------------------------
# 8.2 modeled cost vs actual cost
# --------------------------------------------------------------------------

def check_modeled_vs_actual(project: dict, flags) -> None:
    """Flag every fixture type carrying both a modeled and an actual cost basis.

    Section 8.2: never sum them, prefer actual as the cost of record, keep
    modeled as a clearly tagged fallback, and warn whenever both exist.
    """
    actual: dict = defaultdict(list)
    modeled: dict = defaultdict(list)

    for row in project.get("supplierLines", []):
        bucket = actual if row.get("source") == "actual_invoice" else modeled
        bucket[row["fixtureType"]].append(row)

    for fixture_type in sorted(set(actual) & set(modeled)):
        actual_qty = sum(r.get("qtyOrdered") or 0 for r in actual[fixture_type])
        modeled_qty = sum(r.get("qtyOrdered") or 0 for r in modeled[fixture_type])
        actual_price = next((r.get("unitPrice") for r in actual[fixture_type]
                             if r.get("unitPrice") is not None), None)
        modeled_price = next((r.get("unitPrice") for r in modeled[fixture_type]
                              if r.get("unitPrice") is not None), None)
        flags.add("§8.2", "warning",
                  f"{fixture_type} has BOTH an actual_invoice material cost "
                  f"({actual_qty} @ "
                  f"{'$%.2f' % actual_price if actual_price is not None else 'n/a'}/unit) "
                  f"and a modeled_cost figure ({modeled_qty} @ "
                  f"{'$%.2f' % modeled_price if modeled_price is not None else 'n/a'}/unit). "
                  f"These are different cost bases for the same physical fixture and "
                  f"are NOT additive -- combined quantity is not "
                  f"{actual_qty + modeled_qty}. The actual invoice is the cost of "
                  f"record; confirm that is what you want.",
                  fixture_type)


def check_missing_actual_material(project: dict, vocab, flags) -> None:
    """Warn where a fixture was installed/approved but no real invoice covers it."""
    actual_types = {row["fixtureType"] for row in project.get("supplierLines", [])
                    if row.get("source") == "actual_invoice"}
    modeled_types = {row["fixtureType"] for row in project.get("supplierLines", [])
                     if row.get("source") == "modeled_cost"}

    involved: set = set()
    for row in project.get("contractorLines", []):
        involved.add(row["fixtureType"])
    for row in project.get("workOrderLines", []):
        involved.add(row["fixtureType"])

    for fixture_type in sorted(involved - actual_types):
        if not vocab.is_reconcilable(fixture_type) or vocab.is_sensor(fixture_type):
            continue
        fallback = (" A modeled_cost fallback from the Detailed Cost Report is "
                    "available and tagged as such." if fixture_type in modeled_types
                    else " No modeled fallback is available either.")
        flags.add("§8.2", "warning",
                  f"{fixture_type} appears on the work order and/or the contractor "
                  f"invoice, but no actual_invoice material record exists for it "
                  f"anywhere in this batch, so its true material cost is unknown."
                  + fallback,
                  fixture_type)


# --------------------------------------------------------------------------
# 8.3 blended rates
# --------------------------------------------------------------------------

def check_blended_rates(project: dict, flags) -> None:
    """Segregate blended material+labor lines from any credit-due math (8.3)."""
    for row in project.get("contractorLines", []):
        if not row.get("blended"):
            continue
        note = row.get("blendedNote") or row.get("description")
        flags.add("§8.3", "warning",
                  f"{row['fixtureType']} was billed at "
                  f"${row.get('billedRate') or 0:.2f}/unit as a BLENDED rate bundling "
                  f"material with install labor (invoice text: {note!r}). It is "
                  f"excluded from contracted-rate comparison and from any credit-due "
                  f"total, because comparing a blended rate against a pure-labor "
                  f"contracted rate compares different bases. Splitting it is a "
                  f"business decision -- do it manually.",
                  row["fixtureType"])


# --------------------------------------------------------------------------
# 8.7 wattage-dependent rate tiers
# --------------------------------------------------------------------------

def check_wattage_tiers(project: dict, vocab, flags) -> None:
    """Flag contractor lines whose contracted tier cannot be determined.

    Section 8.7: do not guess a tier. Cross-reference the BGE documents' wattage
    for that fixture and note it as a SUGGESTED, non-authoritative tier.
    """
    # Wattage evidence from the BGE documents, by fixture type.
    evidence: dict = defaultdict(list)
    for row in project.get("workOrderLines", []):
        if row.get("watts"):
            evidence[row["fixtureType"]].append((row["watts"], row.get("location"),
                                                 row.get("sourceDoc")))

    rates_by_type: dict = defaultdict(list)
    for rate in project.get("pieceRates", []):
        rates_by_type[rate["fixtureType"]].append(rate)

    for row in project.get("contractorLines", []):
        fixture_type = row["fixtureType"]
        if not vocab.is_tiered(fixture_type):
            continue
        if row.get("watts"):
            continue  # the invoice stated a wattage -- nothing to resolve

        tiers = vocab.tiers_for(fixture_type)
        tier_text = " / ".join(
            f"{t['tier']}"
            + (f" ${next((r['contractedRate'] for r in rates_by_type.get(fixture_type, []) if r['wattageTier'] == t['tier']), 0):.2f}"
               if rates_by_type.get(fixture_type) else "")
            for t in tiers)

        hints = evidence.get(fixture_type, [])
        if hints:
            watts, location, source_doc = hints[0]
            suggested = vocab.tier_for_watts(fixture_type, watts)
            suggestion = (f" The BGE documents show {watts:.0f}W for this fixture at "
                          f"{location!r} ({source_doc}), which SUGGESTS tier "
                          f"{suggested} -- treat that as a hint, not as authority.")
        else:
            suggestion = (" No wattage for this fixture could be found on any BGE "
                          "document in this batch either.")

        flags.add("§8.7", "warning",
                  f"{fixture_type} was billed at ${row.get('billedRate') or 0:.2f}/unit "
                  f"on {row.get('sourceDoc')}, but the invoice line states no wattage "
                  f"and the piece rate schedule tiers this category by wattage "
                  f"({tier_text}). The applicable contracted rate cannot be determined "
                  f"with certainty." + suggestion,
                  fixture_type)


# --------------------------------------------------------------------------
# 8.8 ordered vs approved vs installed
# --------------------------------------------------------------------------

def check_quantities(project: dict, vocab, settings, flags) -> list[dict]:
    """Compare ordered / approved / installed per canonical fixture type.

    Only quantities that actually exist are compared ("compute all three
    quantities where available"), so a type with a single known quantity is not
    reported as a mismatch against two absent ones. Components are excluded
    (8.5); sensors are included (8.6). modeled_cost never feeds this math (6.1).
    """
    tolerance = settings.get("quantityTolerance", 0)
    roll_up_sensors = settings.get("rollUpSensorTiersForReconciliation", True)

    def bucket(fixture_type: str) -> str:
        """Sensor tiers reconcile as one pool.

        Basic vs Advance is a BGE cost-model distinction; the installing
        contractor charges the same rate either way and routinely bills sensors
        without naming a tier. Comparing "419 Advance approved" against "419
        untiered installed" per-tier would manufacture a mismatch that does not
        exist. Tier disagreements between BGE documents are still checked
        separately by check_sensor_tier_disagreement (8.6).
        """
        if roll_up_sensors and vocab.is_sensor(fixture_type):
            return SENSOR_POOL
        return fixture_type

    ordered: dict = defaultdict(int)
    approved: dict = defaultdict(int)
    installed: dict = defaultdict(int)
    seen_ordered, seen_approved, seen_installed = set(), set(), set()
    tiers_seen: dict = defaultdict(set)

    for row in project.get("supplierLines", []):
        # 8.2 / 6.1: modeled_cost lines are a benchmark dataset, never an "order".
        if row.get("source") != "actual_invoice":
            continue
        key = bucket(row["fixtureType"])
        ordered[key] += row.get("qtyOrdered") or 0
        seen_ordered.add(key)
        tiers_seen[key].add(row["fixtureType"])

    for row in project.get("workOrderLines", []):
        key = bucket(row["fixtureType"])
        approved[key] += row.get("qtyApproved") or 0
        seen_approved.add(key)
        tiers_seen[key].add(row["fixtureType"])

    for row in project.get("contractorLines", []):
        key = bucket(row["fixtureType"])
        installed[key] += row.get("qty") or 0
        seen_installed.add(key)
        tiers_seen[key].add(row["fixtureType"])

    summary: list[dict] = []
    all_types = sorted(seen_ordered | seen_approved | seen_installed)

    for fixture_type in all_types:
        if not vocab.is_reconcilable(fixture_type):
            continue  # 8.5: accessories inherit their parent's status

        values = {}
        if fixture_type in seen_ordered:
            values["ordered"] = ordered[fixture_type]
        if fixture_type in seen_approved:
            values["approved"] = approved[fixture_type]
        if fixture_type in seen_installed:
            values["installed"] = installed[fixture_type]

        row = {
            "fixtureType": fixture_type,
            "rolledUpFrom": (sorted(tiers_seen[fixture_type])
                             if fixture_type == SENSOR_POOL else None),
            "ordered": values.get("ordered"),
            "approved": values.get("approved"),
            "installed": values.get("installed"),
            "remaining": None,
            "status": "ok",
        }

        if values.get("ordered") is not None and values.get("installed") is not None:
            # Handle a negative remaining gracefully -- never clamp it to zero.
            row["remaining"] = values["ordered"] - values["installed"]

        if len(values) < 2:
            row["status"] = "insufficient_data"
            summary.append(row)
            continue

        spread = max(values.values()) - min(values.values())
        if spread > tolerance:
            row["status"] = "mismatch"
            rendered = ", ".join(f"{label} {qty}" for label, qty in values.items())
            extra = ""
            if row["remaining"] is not None and row["remaining"] < 0:
                extra = (f" Installed exceeds ordered by "
                         f"{abs(row['remaining'])} unit(s) -- remaining is negative.")
            elif row["remaining"] is not None and row["remaining"] > 0:
                extra = (f" {row['remaining']} unit(s) ordered beyond what was "
                         f"installed.")
            flags.add("§8.8", "critical",
                      f"{fixture_type} quantities do not reconcile: {rendered}."
                      + extra +
                      f" This mismatch is the signal -- it is reported, not resolved.",
                      fixture_type)
        summary.append(row)

    return summary


# --------------------------------------------------------------------------
# 4.4 batch self-check
# --------------------------------------------------------------------------

def check_modeled_subtotals(project: dict, reported: float | None, settings, flags) -> dict:
    """Sum modeledCosts[] and compare against the report's own SubTotals figure."""
    computed = round(sum(row.get("totalCost") or 0.0
                         for row in project.get("modeledCosts", [])), 2)
    result = {"computed": computed, "reported": reported, "matches": None}

    if reported is None:
        flags.add("§4.4", "warning",
                  f"modeledCosts[] sums to ${computed:,.2f}, but no totals figure "
                  f"could be read from the Detailed Cost Report, so the batch-level "
                  f"self-check could not run.")
        return result

    result["matches"] = abs(computed - reported) <= settings.get("centsTolerance", 0.005)
    if not result["matches"]:
        flags.add("§4.4", "critical",
                  f"modeledCosts[] sums to ${computed:,.2f} but the Detailed Cost "
                  f"Report's own Lighting Totals says ${reported:,.2f} (difference "
                  f"${computed - reported:,.2f}). Either a row was missed in "
                  f"extraction, or the material+labor summation or accessory "
                  f"grouping is wrong. Do not trust the cost figures until this "
                  f"reconciles.")
    return result


def check_inventory(project: dict, reconciliation: list[dict], vocab, flags) -> None:
    """Reconcile physical stock against what the paperwork says was installed.

    Excess inventory is a real, costed outcome -- material KCE paid for that is
    still on a shelf. It is reported per fixture type, and where the numbers
    disagree with the installed count the discrepancy is flagged rather than
    explained away, since a note like "Justn -14" (units moved to another crew)
    is exactly the kind of thing only a human can confirm.
    """
    inventory = project.get("inventory") or []
    if not inventory:
        return

    installed = {row["fixtureType"]: row["installed"] for row in reconciliation
                 if row.get("installed") is not None}

    leftover_types = []
    for row in inventory:
        fixture_type = row.get("fixtureType")
        remaining = row.get("remaining") or 0
        if remaining > 0:
            leftover_types.append((fixture_type or row.get("sourceDescription"),
                                   remaining, row.get("note")))

        consumed = row.get("consumed")
        if consumed is None or not fixture_type:
            continue

        expected = installed.get(fixture_type)
        if expected is None:
            continue
        if consumed != expected:
            note = f" Inventory note: {row['note']!r}." if row.get("note") else ""
            flags.add("§8.8", "warning",
                      f"{fixture_type}: inventory says {row['delivered']} delivered "
                      f"minus {row['remaining']} remaining = {consumed} consumed, but "
                      f"the contractor invoices show {expected} installed "
                      f"(difference {consumed - expected}).{note} Stock moved to "
                      f"another job, breakage, or a miscount would all explain this "
                      f"-- a human must say which.",
                      fixture_type)

    if leftover_types:
        summary = "; ".join(
            f"{qty} x {name}" + (f" (note: {note})" if note else "")
            for name, qty, note in leftover_types)
        flags.add("§8.8", "warning",
                  f"Excess inventory remains on this job: {summary}. This is material "
                  f"KCE has already paid for that was not installed here. Decide "
                  f"whether it is returned, restocked, or transferred to another "
                  f"project before closing the job out.")


def check_credits(project: dict, flags) -> None:
    """Surface any credit already computed against a contractor invoice (8.3)."""
    credits = project.get("credits") or []
    if not credits:
        return

    total = round(sum(c.get("creditDue") or 0.0 for c in credits), 2)
    detail = "; ".join(
        f"invoice {c.get('invoiceNum')} ${c.get('creditDue') or 0:,.2f}"
        for c in credits)
    contractor = next((c.get("contractor") for c in credits if c.get("contractor")),
                      "the contractor")
    flags.add("§8.3", "warning",
              f"A piece-rate credit of ${total:,.2f} has been calculated against "
              f"{contractor} ({detail}). It is recorded as stated, not recomputed. "
              f"Confirm it has actually been applied before closing the job -- and "
              f"check it is not double-counted against any credit line already "
              f"appearing on the invoices themselves.")


def check_unit_cost_consistency(project: dict, flags) -> None:
    """Info-level: same fixture type, same loaded unit cost across locations.

    Section 9 calls this out for Vapor Tight 4' ("Confirm this per-unit figure is
    identical across all three locations -- it's a useful internal consistency
    check"). Generalized to every type.
    """
    by_type: dict = defaultdict(list)
    for row in project.get("modeledCosts", []):
        if row.get("unitCostLoaded") is not None:
            by_type[row["fixtureType"]].append(row)

    for fixture_type, rows in sorted(by_type.items()):
        if len(rows) < 2:
            continue
        distinct = {r["unitCostLoaded"] for r in rows}
        if len(distinct) > 1:
            rendered = "; ".join(f"{r['location']} qty {r['qty']} @ "
                                 f"${r['unitCostLoaded']:.2f}/unit" for r in rows)
            flags.add("§9", "info",
                      f"{fixture_type} has different modeled loaded unit costs across "
                      f"locations: {rendered}. Not necessarily wrong, but worth a look.",
                      fixture_type)
