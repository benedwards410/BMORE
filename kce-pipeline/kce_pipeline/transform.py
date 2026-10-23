"""Turn one document's raw extraction into the schema arrays of section 6.1.

One function per document type (4.1 - 4.5). These do all the structural work --
normalization, size-range expansion, accessory grouping, Material/Labor summing --
so the extraction prompts can stay dumb transcribers.
"""

from __future__ import annotations

import re

from .normalize import (
    Vocabulary,
    clean_text,
    expand_size_range,
    parse_money,
    parse_qty,
    parse_watts,
)


class FlagList:
    """Collector for the output flags[] array (section 7).

    Entries carry exactly the three keys the outline specifies. The governing
    rule is cited inline in the message so a reader of the JSON alone can trace
    any flag back to the spec.
    """

    SEVERITIES = ("info", "warning", "critical")

    def __init__(self):
        self.entries: list[dict] = []

    def add(self, rule: str, severity: str, message: str, fixture_type=None) -> dict:
        if severity not in self.SEVERITIES:
            raise ValueError(f"bad severity {severity!r}")
        entry = {
            "severity": severity,
            "message": f"[{rule}] {message}",
            "relatedFixtureType": fixture_type,
        }
        self.entries.append(entry)
        return entry

    def sorted(self) -> list[dict]:
        order = {"critical": 0, "warning": 1, "info": 2}
        return sorted(self.entries, key=lambda f: (order[f["severity"]], f["message"]))


# --------------------------------------------------------------------------
# shared metadata handling (section 5)
# --------------------------------------------------------------------------

def project_metadata(meta: dict) -> dict:
    """Auto-fill the safe project fields. `revenue` is deliberately absent.

    Section 5: name and poNumber both come out of the single "Audit / Proposal"
    field, split on the slash.
    """
    audit_proposal = (meta.get("auditProposal") or "").strip()
    po_number, name = None, None
    if "/" in audit_proposal:
        left, _, right = audit_proposal.partition("/")
        po_number, name = left.strip() or None, right.strip() or None
    elif audit_proposal:
        po_number = audit_proposal

    return {
        "name": name,
        "poNumber": po_number,
        "customer": (meta.get("customer") or "").strip() or None,
        "address": (meta.get("address") or "").strip() or None,
        "contactName": (meta.get("contactName") or "").strip() or None,
        "contactPhone": (meta.get("contactPhone") or "").strip() or None,
        "auditorName": (meta.get("auditorName") or "").strip() or None,
    }


# --------------------------------------------------------------------------
# 4.1 piece rate schedule
# --------------------------------------------------------------------------

def transform_piece_rates(raw: dict, vocab: Vocabulary, flags: FlagList,
                          source_doc: str) -> list[dict]:
    """Rate card -> pieceRates[].

    Skips "Included" add-on rows (4.1), expands size ranges into one row per
    size, keeps wattage tiers as their own field, and parses defensively so a
    cell rendered "$30..00" still yields 30.00.
    """
    rows_out: list[dict] = []
    seen: dict[tuple, dict] = {}

    for row in raw.get("rows", []):
        description = (row.get("description") or "").strip()
        rate_text = row.get("rateText")
        if not description:
            continue

        # 4.1: rows priced "Included" are not separate rate entries.
        if rate_text and "included" in str(rate_text).lower():
            continue

        rate = parse_money(rate_text)
        if rate is None:
            continue  # section header or empty rate cell

        install_unit = row.get("installUnit")

        for variant in expand_size_range(description):
            match = vocab.match_type(variant)
            if not match.canonical:
                flags.add("§6.2", "warning",
                          f"Rate schedule row {variant!r} could not be normalized to a "
                          f"canonical fixture type (best fuzzy score "
                          f"{match.score:.2f}); it was left out of pieceRates[]. "
                          f"Add a rule for it in config/canonical_fixtures.json.")
                continue

            tier = vocab.tier_from_text(variant)
            key = (match.canonical, tier)

            entry = {
                "fixtureType": match.canonical,
                "wattageTier": tier,
                "contractedRate": round(rate, 2),
                "source": "piece_rate_schedule",
                "sourceDoc": source_doc,
                "sourceDescription": variant,
            }

            if key in seen:
                # Two rate-card rows collapse to the same canonical type+tier.
                previous = seen[key]
                if abs(previous["contractedRate"] - entry["contractedRate"]) > 0.005:
                    # Flag, don't overwrite (section 7): both values stay visible.
                    flags.add("§4.1", "warning",
                              f"Rate schedule gives two different rates for "
                              f"{match.canonical}"
                              f"{' tier ' + tier if tier else ''}: "
                              f"${previous['contractedRate']:.2f} "
                              f"({previous['sourceDescription']!r}) vs "
                              f"${entry['contractedRate']:.2f} ({variant!r}). "
                              f"Kept the first; a human must decide which applies.",
                              match.canonical)
                continue  # identical rate -> silent dedupe, nothing lost

            # Real-world defect check: a per-fixture category billed "per sensor".
            if (install_unit and "per sensor" in clean_text(install_unit)
                    and not vocab.is_sensor(match.canonical)
                    and not vocab.is_component(match.canonical)):
                flags.add("§4.1", "info",
                          f"Rate schedule row {variant!r} has Install Unit "
                          f"{install_unit!r}, but {match.canonical} is a per-fixture "
                          f"category. Looks like a typo in the source PDF; the rate "
                          f"was read as a per-fixture rate.",
                          match.canonical)

            seen[key] = entry
            rows_out.append(entry)

    return rows_out


# --------------------------------------------------------------------------
# 4.2 supplier / distributor invoice
# --------------------------------------------------------------------------

_SENSOR_HINT = re.compile(r"sensor|photocell|photo\s*cell", re.IGNORECASE)


def transform_supplier_invoice(raw: dict, vocab: Vocabulary, flags: FlagList,
                               source_doc: str) -> list[dict]:
    """Distributor invoice -> supplierLines[] tagged `actual_invoice` (4.2, 8.2)."""
    lines_out: list[dict] = []

    for line in raw.get("lines", []):
        description = line.get("description") or ""
        sku = line.get("sku")
        # The SKU map is authoritative; fall back to the description only when
        # the part number is unknown.
        match = vocab.match_sku(sku) or vocab.match_type(description, sku)

        if not match.canonical:
            flags.add("§6.2", "warning",
                      f"Supplier invoice line {description!r} (SKU {sku!r}) could not "
                      f"be normalized to a canonical fixture type; it is excluded from "
                      f"quantity reconciliation. Add a rule in "
                      f"config/canonical_fixtures.json.")
            continue

        qty = parse_qty(line.get("qty"))
        unit_price = parse_money(line.get("unitPrice"))
        amount = parse_money(line.get("amount"))

        # Derive a unit price when only a line total is printed.
        if unit_price is None and amount is not None and qty:
            unit_price = round(amount / qty, 2)

        lines_out.append({
            "fixtureType": match.canonical,
            "sku": sku,
            "qtyOrdered": qty,
            "unitPrice": unit_price,
            "hasSensor": bool(_SENSOR_HINT.search(description or ""))
                          or vocab.is_sensor(match.canonical),
            "source": "actual_invoice",
            "sourceDoc": source_doc,
            "sourceDescription": description,
        })

    return lines_out


# --------------------------------------------------------------------------
# 4.3 BGE proposal detail report
# --------------------------------------------------------------------------

def transform_proposal_detail(raw: dict, vocab: Vocabulary, flags: FlagList,
                              source_doc: str) -> tuple[dict, list[dict]]:
    """Proposal Detail -> (project metadata, workOrderLines[]).

    This is the ONLY document type allowed to populate workOrderLines (8.4).
    """
    meta = project_metadata(raw.get("meta", {}))
    lines_out: list[dict] = []

    for line in raw.get("lines", []):
        proposed = line.get("proposedDescription") or ""
        existing = line.get("existingDescription") or ""
        location = line.get("location") or ""

        # Match the PROPOSED equipment -- never the existing/old fixture.
        match = vocab.match_type(proposed)
        if not match.canonical:
            flags.add("§6.2", "warning",
                      f"Proposal Detail line {line.get('line')} ({location!r}) "
                      f"proposed description {proposed!r} could not be normalized "
                      f"to a canonical fixture type; it is excluded from the work "
                      f"order.")
            continue

        # 8.6: a sensor row's size class describes the fixtures it serves, so it
        # comes from the sensor row's own Location text ("4ft sensors") or, when
        # the Location is just "Sensors", from the Existing/Proposed Description
        # naming the fixture size. A normal fixture row takes its size class from
        # its own proposed description -- never from the old fixture it replaces.
        if vocab.is_sensor(match.canonical):
            size_class = vocab.size_class(location) or vocab.size_class(existing)
        else:
            size_class = vocab.size_class(proposed)

        if size_class is None:
            flags.add("§4.3", "info",
                      f"Could not derive a sizeClass for Proposal Detail line "
                      f"{line.get('line')} ({location!r}, {proposed!r}). "
                      f"Sensor size-class validation cannot use this row.",
                      match.canonical)

        lines_out.append({
            "location": location,
            "fixtureType": match.canonical,
            "sizeClass": size_class,
            "qtyApproved": parse_qty(line.get("qty")),
            "watts": parse_watts(line.get("watts")) or parse_watts(proposed),
            "source": "proposal_detail",
            "sourceDoc": source_doc,
            "sourceLine": line.get("line"),
            "sourceDescription": proposed,
        })

    return meta, lines_out


# --------------------------------------------------------------------------
# 4.4 BGE detailed cost report
# --------------------------------------------------------------------------

def transform_detailed_cost(raw: dict, vocab: Vocabulary, flags: FlagList,
                            source_doc: str, cents_tolerance: float) -> dict:
    """Detailed Cost Report -> modeledCosts[] + supplierLines[] + otherExpenses[].

    Grouping rules (4.4, 8.5):
      * every Material row sharing a Line number folds into that line's
        materialCost, with the split preserved in components[];
      * an accessory (Photocell, EM Battery Backup) is rolled INTO its parent
        fixture's line and never becomes its own modeledCosts entry;
      * the parent's qty is never inflated by the accessory;
      * Labor rows for the line sum into laborCost;
      * sensors are exempt from accessory grouping and get their own row (8.6).
    """
    meta = project_metadata(raw.get("meta", {}))

    # -- bucket rows by Line number, preserving document order ---------------
    by_line: dict = {}
    for row in raw.get("rows", []):
        key = row.get("line")
        if key is None:
            key = f"loc:{clean_text(row.get('location'))}"  # 8.5 fallback linkage
        by_line.setdefault(key, []).append(row)

    modeled_costs: list[dict] = []
    supplier_lines: list[dict] = []

    for line_key, rows in by_line.items():
        material_rows = [r for r in rows if clean_text(r.get("type")) == "material"]
        labor_rows = [r for r in rows if clean_text(r.get("type")) == "labor"]
        location = next((r.get("location") for r in rows if r.get("location")), None)
        equipment = next((r.get("proposedEquipment") for r in rows
                          if r.get("proposedEquipment")), None)

        # Classify each Material row from its OWN Component text. Matching on the
        # line's Proposed Equipment as well would let "Exterior LED 70W Flood"
        # outrank "Photocell w/ knuckle" and hide the accessory entirely.
        classified = []
        for row in material_rows:
            match = vocab.match_type(row.get("component"))
            if not match.canonical:
                match = vocab.match_type(row.get("component"), equipment)
            classified.append((row, match.canonical))

        primaries = [(r, t) for r, t in classified if t and not vocab.is_component(t)]
        accessories = [(r, t) for r, t in classified if t and vocab.is_component(t)]
        unmatched = [r for r, t in classified if not t]

        for row in unmatched:
            flags.add("§6.2", "warning",
                      f"Detailed Cost line {line_key} component "
                      f"{row.get('component')!r} could not be normalized to a "
                      f"canonical fixture type; its ${parse_money(row.get('price')) or 0:.2f} "
                      f"was still summed into the line's materialCost so the "
                      f"SubTotals check stays honest, but it has no component label.")

        if not primaries and unmatched:
            # Nothing on this line resolved to a canonical fixture type. Keep the
            # WHOLE line -- dropping it would silently understate project cost and
            # quietly break the SubTotals self-check, which is precisely the
            # failure mode section 7 exists to prevent. Emit it with a null
            # fixtureType and flag it loudly instead.
            anchor = max(material_rows,
                         key=lambda r: parse_money(r.get("price")) or 0.0)
            line_total = sum(parse_money(r.get("price")) or 0.0
                             for r in material_rows + labor_rows)
            flags.add("§6.2", "critical",
                      f"Detailed Cost line {line_key} ({location!r}, equipment "
                      f"{equipment!r}) has no row that maps to a canonical fixture "
                      f"type. Its full ${line_total:,.2f} is retained in "
                      f"modeledCosts[] with fixtureType null so the cost is not "
                      f"lost, but it cannot participate in fixture-level "
                      f"reconciliation until a rule is added to "
                      f"config/canonical_fixtures.json.")
            modeled_costs.append(_modeled_row(
                line_key, location, None, anchor, material_rows, labor_rows, [],
                source_doc, vocab, flags, cents_tolerance,
                vocab.size_class(equipment)))
            continue

        if not primaries:
            # 8.5: an accessory with no clear parent on the same Line/Location.
            # No default -- do not guess; surface it and leave it ungrouped.
            for row, accessory_type in accessories:
                flags.add("§8.5", "warning",
                          f"{accessory_type} on Detailed Cost line {line_key} "
                          f"({location!r}) has no parent fixture row on that line, so "
                          f"it could not be grouped. It was left as its own line. "
                          f"Confirm how it should be grouped.",
                          accessory_type)
                modeled_costs.append(_modeled_row(
                    line_key, location, accessory_type, row, [row], labor_rows,
                    [], source_doc, vocab, flags, cents_tolerance,
                    vocab.size_class(equipment, accessory_type),
                    grouping_confidence="needs_confirmation"))
            continue

        if len(primaries) > 1:
            flags.add("§4.4", "warning",
                      f"Detailed Cost line {line_key} ({location!r}) carries more than "
                      f"one primary fixture Material row "
                      f"({', '.join(t for _, t in primaries)}). The first was treated "
                      f"as the line's fixture; a human should confirm.",
                      primaries[0][1])

        primary_row, primary_type = primaries[0]

        # Sensors are first-class types, never accessory-grouped (8.5 / 8.6).
        components: list[dict] = []
        grouped_material_rows = [primary_row]

        for row, accessory_type in accessories:
            rule = vocab.accessory_rule(accessory_type)
            parent_size = vocab.size_class(equipment, primary_type)
            allowed = rule.get("parentSizeClasses") or []
            confidence = rule.get("confidence", "needs_confirmation")
            should_flag = bool(rule.get("flag"))

            if allowed and parent_size not in allowed:
                # The rule table's expected pairing does not hold here.
                confidence = "needs_confirmation"
                should_flag = True

            if should_flag:
                flags.add("§8.5", "warning",
                          f"{accessory_type} (${parse_money(row.get('price')) or 0:.2f}, "
                          f"qty {parse_qty(row.get('qty'))}) on Detailed Cost line "
                          f"{line_key} was tentatively grouped into the "
                          f"{primary_type} at {location!r}. "
                          f"{rule.get('note', '')} Confirm this grouping.",
                          primary_type)

            components.append({
                "type": accessory_type,
                "materialCost": round(parse_money(row.get("price")) or 0.0, 2),
                "groupingConfidence": confidence,
            })
            grouped_material_rows.append(row)

        # Unmatched material rows still count toward the line's cost.
        grouped_material_rows.extend(unmatched)

        # 8.6: sensor rows take their size class from their own Location text or
        # the description naming the fixture size they serve -- which a Detailed
        # Cost Report often does not state at all. Fixture rows take it from the
        # line's proposed equipment.
        if vocab.is_sensor(primary_type):
            line_size_class = (vocab.size_class(location)
                               or vocab.size_class(primary_row.get("component")))
        else:
            line_size_class = vocab.size_class(equipment, primary_type)

        modeled = _modeled_row(line_key, location, primary_type, primary_row,
                               grouped_material_rows, labor_rows, components,
                               source_doc, vocab, flags, cents_tolerance,
                               line_size_class)
        modeled_costs.append(modeled)

        # 4.4(b): the same grouped material figure as a per-unit fallback price.
        qty = modeled["qty"]
        supplier_lines.append({
            "fixtureType": primary_type,
            "sku": None,
            "qtyOrdered": qty,
            "unitPrice": round(modeled["materialCost"] / qty, 2) if qty else None,
            "hasSensor": vocab.is_sensor(primary_type),
            "source": "modeled_cost",
            "sourceDoc": source_doc,
            "sourceLine": line_key,
            "components": [
                {"type": "fixture",
                 "unitPrice": round((parse_money(primary_row.get("price")) or 0) / qty, 2)
                 if qty else None},
                *[{"type": c["type"],
                   "unitPrice": round(c["materialCost"] / qty, 2) if qty else None,
                   "groupingConfidence": c["groupingConfidence"]} for c in components],
            ],
        })

    # -- 4.4(c): fees, tax, and any Miscellaneous table ----------------------
    other_expenses = []
    for fee in raw.get("feeRows", []):
        label = (fee.get("label") or "").strip()
        amount = parse_money(fee.get("price"))  # the Price column, never a share
        if not label or amount is None:
            continue
        other_expenses.append({
            "category": label,
            "description": label,
            "amount": round(amount, 2),
            "source": "modeled_cost",
            "sourceDoc": source_doc,
        })

    # A Detailed Cost Report may carry a second "Miscellaneous" table of
    # non-fixture costs (lift fees, other labor, permits). These are not
    # per-fixture material or labor, so they belong in otherExpenses -- and their
    # Line numbers restart at 1, colliding with the Lighting table's, which is why
    # they are never merged into `rows`.
    for row in raw.get("miscRows") or []:
        amount = parse_money(row.get("price"))
        if amount is None:
            continue
        label = (row.get("component") or row.get("proposedEquipment")
                 or "Miscellaneous").strip()
        location = (row.get("location") or "").strip()
        other_expenses.append({
            "category": _other_category(label),
            "description": f"{label} ({location})" if location else label,
            "amount": round(amount, 2),
            "source": "modeled_cost",
            "sourceDoc": f"{source_doc} - Miscellaneous",
        })

    summary = raw.get("summary") or {}
    lighting_totals = parse_money(summary.get("lightingTotals"))
    sub_totals = parse_money(summary.get("subTotals"))

    return {
        "meta": meta,
        "modeledCosts": modeled_costs,
        "supplierLines": supplier_lines,
        "otherExpenses": other_expenses,
        # modeledCosts[] covers the Lighting table only, so it is self-checked
        # against the Lighting Totals. On a report with no Miscellaneous table
        # (the Steve's Pools shape) the two figures are the same number.
        "reportedLightingTotals": lighting_totals if lighting_totals is not None
                                   else sub_totals,
        "reportedSubTotals": sub_totals,
        "reportedMiscTotals": parse_money(summary.get("miscTotals")),
    }


def _modeled_row(line_key, location, fixture_type, primary_row, material_rows,
                 labor_rows, components, source_doc, vocab, flags, cents_tolerance,
                 size_class=None, grouping_confidence=None) -> dict:
    """Build one modeledCosts[] entry: material + labor summed for the line."""
    material_cost = sum(parse_money(r.get("price")) or 0.0 for r in material_rows)
    labor_cost = sum(parse_money(r.get("price")) or 0.0 for r in labor_rows)
    total_cost = material_cost + labor_cost

    all_rows = list(material_rows) + list(labor_rows)
    program_share = sum(parse_money(r.get("programShare")) or 0.0 for r in all_rows)
    customer_share = sum(parse_money(r.get("customerShare")) or 0.0 for r in all_rows)

    # 4.4(a): "must equal programShare + customerShare for that line -- use this
    # identity as a self-check on every line you extract."
    if abs(total_cost - (program_share + customer_share)) > cents_tolerance:
        flags.add("§4.4", "critical",
                  f"Detailed Cost line {line_key} ({location!r}) fails its own cost "
                  f"identity: material ${material_cost:,.2f} + labor ${labor_cost:,.2f} "
                  f"= ${total_cost:,.2f}, but program ${program_share:,.2f} + customer "
                  f"${customer_share:,.2f} = ${program_share + customer_share:,.2f}. "
                  f"The extraction for this line is unreliable.",
                  fixture_type)

    qty = parse_qty(primary_row.get("qty"))

    fixture_component = {"type": "fixture",
                         "materialCost": round(parse_money(primary_row.get("price")) or 0.0, 2)}
    if grouping_confidence:
        fixture_component["groupingConfidence"] = grouping_confidence

    return {
        "line": line_key,
        "location": location,
        "fixtureType": fixture_type,
        "sizeClass": size_class,
        "qty": qty,
        "materialCost": round(material_cost, 2),
        "laborCost": round(labor_cost, 2),
        "totalCost": round(total_cost, 2),
        "programShare": round(program_share, 2),
        "customerShare": round(customer_share, 2),
        "unitCostLoaded": round(total_cost / qty, 2) if qty else None,
        "source": "modeled_cost",
        "sourceDoc": source_doc,
        "components": [fixture_component, *components],
    }


# --------------------------------------------------------------------------
# 4.5 contractor / installer invoice
# --------------------------------------------------------------------------

# 4.5 / 8.3: `blended` may be set ONLY from explicit text saying the rate bundles
# a fixture/material cost together with the install cost. Never from price alone.
_BLENDED_INSTALL = re.compile(r"\$?\s*[\d,]+(?:\.\d+)?\s*(?:for\s+)?install", re.IGNORECASE)
_BLENDED_MATERIAL = re.compile(r"\$?\s*[\d,]+(?:\.\d+)?\s*(?:for\s+)?(?:fixture|material)",
                               re.IGNORECASE)

_OTHER_CATEGORIES = [
    (re.compile(r"scrap|trash|disposal|dispose|removal|haul|pick\s*up|pickup", re.I), "Disposal"),
    (re.compile(r"trip\s*charge|travel|mileage", re.I), "Trip Charge"),
    (re.compile(r"mobiliz", re.I), "Mobilization"),
    (re.compile(r"permit", re.I), "Permit"),
    (re.compile(r"rental|lift|boom|scissor", re.I), "Equipment Rental"),
]


def transform_inventory(raw: dict, vocab: Vocabulary, flags: FlagList,
                        source_doc: str) -> list[dict]:
    """Inventory reconciliation sheet -> inventory[].

    Delivered-vs-remaining is the missing third quantity in an over-ordering
    story: a supplier invoice says what was billed, the work order says what was
    approved, the contractor says what was installed, and this says what is
    physically left on the shelf.
    """
    rows_out: list[dict] = []

    for row in raw.get("rows", []):
        description = (row.get("description") or "").strip()
        sku = row.get("sku")
        if not description and not sku:
            continue

        match = vocab.match_sku(sku) or vocab.match_type(description)
        if not match.canonical:
            flags.add("§6.2", "warning",
                      f"Inventory row {description!r} (SKU {sku!r}) could not be "
                      f"normalized to a canonical fixture type, so its remaining "
                      f"stock is not tied to a fixture. Add a rule or a skuMap entry "
                      f"in config/canonical_fixtures.json.")

        delivered = parse_qty(row.get("delivered"))
        remaining = parse_qty(row.get("remaining"))
        note = (row.get("note") or "").strip() or None

        rows_out.append({
            "fixtureType": match.canonical,
            "sku": sku,
            "delivered": delivered,
            "remaining": remaining,
            "consumed": (delivered - remaining)
                        if delivered is not None and remaining is not None else None,
            "note": note,
            "source": "inventory_reconciliation",
            "sourceDoc": source_doc,
            "sourceDescription": description,
        })

    return rows_out


def transform_credit_calculation(raw: dict, vocab: Vocabulary, flags: FlagList,
                                 source_doc: str) -> list[dict]:
    """Credit calculation memo -> credits[].

    Section 8.3 says a credit-due figure must never quietly absorb a blended or
    otherwise non-comparable line. Here the credit has already been worked out by
    a human on a rate-by-rate basis, so it is recorded as stated -- attributed,
    never recomputed.
    """
    credits_out: list[dict] = []

    for invoice in raw.get("invoices", []) or []:
        rows = []
        for row in invoice.get("rows", []) or []:
            description = (row.get("description") or "").strip()
            match = vocab.match_type(description)
            rows.append({
                "fixtureType": match.canonical,
                "description": description,
                "qty": parse_qty(row.get("qty")),
                "billedRate": parse_money(row.get("billedRate")),
                "correctRate": parse_money(row.get("correctRate")),
                "overcharge": parse_money(row.get("overcharge")),
            })

        credits_out.append({
            "invoiceNum": invoice.get("invoiceNumber"),
            "date": invoice.get("date"),
            "contractor": raw.get("contractor"),
            "billedTotal": parse_money(invoice.get("billedTotal")),
            "correctedTotal": parse_money(invoice.get("correctedTotal")),
            "creditDue": parse_money(invoice.get("creditDue")),
            "lines": rows,
            "source": "credit_calculation",
            "sourceDoc": source_doc,
        })

    stated_total = parse_money(raw.get("totalCreditDue"))
    computed = round(sum(c["creditDue"] or 0.0 for c in credits_out), 2)
    if stated_total is not None and abs(computed - stated_total) > 0.005:
        flags.add("§8.3", "critical",
                  f"{source_doc}: the per-invoice credits sum to ${computed:,.2f} but "
                  f"the memo states a total credit due of ${stated_total:,.2f}. "
                  f"The memo does not add up -- do not act on either figure until "
                  f"this is resolved.")

    return credits_out


def _parse_bundled_fixtures(text: str, vocab: Vocabulary) -> list[tuple]:
    """Pull fixture quantities out of an area-billed contractor line.

    Some subcontractors bill by area rather than by fixture, putting several
    fixture types under one lump sum:

        "Service Bay 2- 57 8' Strips, 28 4' Strips, 31 High Bays"  -> $7,430.00

    The quantities are stated explicitly and are worth capturing. The dollar
    figure is NOT split across them -- apportioning one lump sum across three
    fixture types is a business decision the pipeline must not invent (the same
    reasoning as 8.3's blended rates), so each extracted line carries
    billedRate = None and the money stays in otherExpenses[].

    Returns [(canonicalType, qty, rawLabel), ...].
    """
    if not text:
        return []

    # Strip a leading "Area name- " prefix when one is present.
    head, sep, tail = text.partition("-")
    body = tail if sep and len(head) <= 60 else text

    found: list[tuple] = []
    for segment in re.split(r"[,;]|\band\b", body):
        match = re.match(r"\s*(\d+)\s+(.{2,})", segment)
        if not match:
            continue
        qty, label = int(match.group(1)), match.group(2).strip()
        resolved = vocab.match_type(label)
        # Only exact/rule matches count here. A fuzzy match on free text like
        # "1900 Boxes" would invent fixtures out of a materials list.
        if resolved.canonical and resolved.method in ("exact", "rule") \
                and not vocab.is_component(resolved.canonical):
            found.append((resolved.canonical, qty, label))
    return found


def _blended_evidence(text: str) -> bool:
    if not text:
        return False
    return bool(_BLENDED_INSTALL.search(text) and _BLENDED_MATERIAL.search(text))


def _other_category(text: str) -> str:
    for pattern, label in _OTHER_CATEGORIES:
        if pattern.search(text or ""):
            return label
    return "Other"


def transform_contractor_invoice(raw: dict, vocab: Vocabulary, flags: FlagList,
                                 source_doc: str) -> tuple[list[dict], list[dict]]:
    """Installer invoice -> (contractorLines[], otherExpenses[]).

    Both arrays come from a SINGLE read of the document (4.5) -- a per-fixture
    line and a flat disposal line on the same invoice are routed here, not by
    asking the user to upload the file twice.
    """
    # 4.5 safety net: refuse to extract fixtures from a cost allocation even if
    # the classifier mis-routed it here.
    if raw.get("isCostAllocation"):
        flags.add("§4.5", "warning",
                  f"{source_doc} carries Program Share / Customer Share columns, so it "
                  f"is a utility cost allocation, not a contractor invoice. No "
                  f"contractor lines were extracted from it.")
        return [], []

    invoice_number = raw.get("invoiceNumber")
    invoice_date = raw.get("date")

    fixtures: list[dict] = []
    others: list[dict] = []

    for line in raw.get("lines", []):
        description = (line.get("description") or "").strip()
        note = (line.get("note") or "").strip()
        qty = parse_qty(line.get("qty"))
        unit_price = parse_money(line.get("unitPrice"))
        line_total = parse_money(line.get("lineTotal"))

        match = vocab.match_type(description)

        # A fixture line needs a resolvable type AND a quantity. Anything else
        # is a flat service charge.
        if match.canonical and qty:
            rate = unit_price
            if rate is None and line_total is not None and qty:
                rate = round(line_total / qty, 2)

            fixtures.append({
                "invoiceNum": invoice_number,
                "date": invoice_date,
                "description": description,
                "fixtureType": match.canonical,
                "qty": qty,
                "billedRate": rate,
                "blended": _blended_evidence(f"{description} {note}"),
                "blendedNote": note or None,
                "watts": parse_watts(description) or parse_watts(note),
                "source": "actual_invoice",
                "sourceDoc": source_doc,
            })
            continue

        amount = line_total if line_total is not None else unit_price

        # An area-billed line naming several fixtures under one lump sum.
        bundled = _parse_bundled_fixtures(description, vocab)
        if bundled:
            for fixture_type, bundled_qty, raw_label in bundled:
                fixtures.append({
                    "invoiceNum": invoice_number,
                    "date": invoice_date,
                    "description": raw_label,
                    "fixtureType": fixture_type,
                    "qty": bundled_qty,
                    "billedRate": None,
                    "blended": False,
                    "blendedNote": None,
                    "watts": None,
                    "rateBasis": "bundled_lump_sum",
                    "bundledFrom": description,
                    "bundledLineTotal": round(amount, 2) if amount is not None else None,
                    "source": "actual_invoice",
                    "sourceDoc": source_doc,
                })
            flags.add("§8.8", "warning",
                      f"{source_doc} bills {description!r} as one lump sum of "
                      f"{f'${amount:,.2f}' if amount is not None else 'an unstated amount'} "
                      f"covering "
                      f"{', '.join(f'{q} x {t}' for t, q, _ in bundled)}. The "
                      f"quantities were extracted so installed counts reconcile, but "
                      f"billedRate is left null -- apportioning one lump sum across "
                      f"several fixture types is a business decision the pipeline "
                      f"will not make. The dollars stay in otherExpenses[] and are "
                      f"NOT double-counted against these lines.")
            if amount is not None:
                others.append({
                    "category": "Install (bundled)",
                    "description": description,
                    "amount": round(amount, 2),
                    "source": "actual_invoice",
                    "sourceDoc": source_doc,
                })
            continue

        if amount is None:
            continue
        label = description or note or "Unlabelled line"
        others.append({
            "category": _other_category(f"{description} {note}"),
            "description": label,
            "amount": round(amount, 2),
            "source": "actual_invoice",
            "sourceDoc": source_doc,
        })

    return fixtures, others
