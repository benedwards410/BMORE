"""Human-readable Markdown reconciliation report (section 2, item 2).

Lists every discrepancy, ambiguity, and item needing a human's judgment call.
The report is written even on partial failures.
"""

from __future__ import annotations

from collections import defaultdict

from .diff import render as render_diff


SEVERITY_ICON = {"critical": "🔴", "warning": "🟡", "info": "🔵"}


def _money(value) -> str:
    return "—" if value is None else f"${value:,.2f}"


def _qty(value) -> str:
    return "—" if value is None else str(value)


def build_report(result: dict) -> str:
    project = result["project"]
    meta = project["project"]
    vocab = result["vocab"]
    lines: list[str] = []
    add = lines.append

    add(f"# Reconciliation Report — {meta.get('name') or 'Unnamed project'}")
    add("")
    add(f"**MTX / PO:** {meta.get('poNumber') or '—'}  ")
    add(f"**Customer:** {meta.get('customer') or '—'}  ")
    add(f"**Address:** {meta.get('address') or '—'}  ")
    add(f"**Contact:** {meta.get('contactName') or '—'} "
        f"({meta.get('contactPhone') or '—'})  ")
    add(f"**Revenue:** {'NOT SET — requires manual entry' if meta.get('revenue') is None else _money(meta['revenue'])}  ")
    add(f"**Extraction backend:** `{result['backend']}`")
    add("")

    # -- flag summary -------------------------------------------------------
    counts = defaultdict(int)
    for flag in project["flags"]:
        counts[flag["severity"]] += 1
    add(f"**Flags:** {counts['critical']} critical · {counts['warning']} warning "
        f"· {counts['info']} info")
    add("")
    add("---")
    add("")

    # -- what moved since last time (renders nothing on a first run) --------
    # render_diff supplies its own trailing rule, so only add one when it is
    # silent.
    diff_lines = render_diff(result.get("diff"))
    if diff_lines:
        lines.extend(diff_lines)
    else:
        add("---")
    add("")

    # -- documents ----------------------------------------------------------
    add("## 1. Documents in this batch")
    add("")
    add("| File | Classified as | MTX | Status |")
    add("|---|---|---|---|")
    for doc in result["documents"]:
        if doc.error:
            status = f"skipped — {doc.error}"
        elif doc.excluded:
            status = "**EXCLUDED — MTX mismatch**"
        elif doc.doc_type == "unknown":
            status = "skipped — unclassified"
        else:
            status = "merged"
        add(f"| `{doc.name}` | {doc.doc_type} | {doc.mtx or '—'} | {status} |")
    add("")

    # -- quantity reconciliation -------------------------------------------
    add("## 2. Quantity reconciliation — ordered vs approved vs installed")
    add("")
    add("Per §8.8. `—` means that quantity does not exist anywhere in this batch, "
        "not that it is zero. Modeled costs never feed this table (§6.1).")
    add("")
    add("| Fixture type | Ordered | Approved | Installed | Remaining | Status |")
    add("|---|---|---|---|---|---|")
    for row in result["reconciliation"]:
        status = {"ok": "✅ reconciles",
                  "mismatch": "🔴 **MISMATCH**",
                  "insufficient_data": "— insufficient data"}[row["status"]]
        add(f"| {row['fixtureType']} | {_qty(row['ordered'])} | "
            f"{_qty(row['approved'])} | {_qty(row['installed'])} | "
            f"{_qty(row['remaining'])} | {status} |")
    add("")

    # -- modeled costs ------------------------------------------------------
    if project["modeledCosts"]:
        add("## 3. Modeled cost benchmark (BGE Detailed Cost Report)")
        add("")
        add("⚠️ These are BGE's cost-allocation model figures, **not** what KCE paid "
            "(§8.2). Never add them to actual invoice amounts.")
        add("")
        add("| Line | Location | Fixture | Qty | Material | Labor | Total | "
            "Loaded $/unit | Components |")
        add("|---|---|---|---|---|---|---|---|---|")
        for row in project["modeledCosts"]:
            components = ", ".join(
                f"{c['type']} {_money(c.get('materialCost'))}"
                + (f" ({c['groupingConfidence']})" if c.get("groupingConfidence") else "")
                for c in row.get("components", []))
            add(f"| {row['line']} | {row['location']} | {row['fixtureType']} | "
                f"{_qty(row['qty'])} | {_money(row['materialCost'])} | "
                f"{_money(row['laborCost'])} | {_money(row['totalCost'])} | "
                f"{_money(row['unitCostLoaded'])} | {components} |")

        subtotals = result["subtotals"]
        verdict = ("✅ matches" if subtotals["matches"]
                   else "🔴 **DOES NOT MATCH**" if subtotals["matches"] is False
                   else "⚠️ not checked")
        add(f"| | | | | | | **{_money(subtotals['computed'])}** | | "
            f"vs reported SubTotals {_money(subtotals['reported'])} — {verdict} |")
        add("")

    # -- cost bases ---------------------------------------------------------
    add("## 4. Material cost bases")
    add("")
    add("| Fixture type | Actual invoice | Modeled (fallback) | Cost of record |")
    add("|---|---|---|---|")
    actual, modeled = defaultdict(list), defaultdict(list)
    for row in project["supplierLines"]:
        (actual if row.get("source") == "actual_invoice" else modeled)[
            row["fixtureType"]].append(row)
    for fixture_type in sorted(set(actual) | set(modeled)):
        actual_rows, modeled_rows = actual.get(fixture_type, []), modeled.get(fixture_type, [])
        actual_text = (" + ".join(f"{r['qtyOrdered']} @ {_money(r['unitPrice'])}"
                                  for r in actual_rows) or "—")
        modeled_text = (" + ".join(f"{r['qtyOrdered']} @ {_money(r['unitPrice'])}"
                                   for r in modeled_rows) or "—")
        record = "actual invoice" if actual_rows else ("modeled — no actual invoice yet"
                                                       if modeled_rows else "—")
        add(f"| {fixture_type} | {actual_text} | {modeled_text} | {record} |")
    add("")

    # -- contractor billing -------------------------------------------------
    if project["contractorLines"]:
        add("## 5. Contractor billing vs contracted piece rates")
        add("")
        rates = defaultdict(list)
        for rate in project["pieceRates"]:
            rates[rate["fixtureType"]].append(rate)

        add("| Fixture | Qty | Billed $/unit | Contracted rate(s) | Blended? | Note |")
        add("|---|---|---|---|---|---|")
        for row in project["contractorLines"]:
            applicable = rates.get(row["fixtureType"], [])
            rate_text = " / ".join(
                f"{r['wattageTier'] + ' ' if r['wattageTier'] else ''}"
                f"{_money(r['contractedRate'])}" for r in applicable) or "—"
            if row.get("blended"):
                note = "excluded from credit-due math (§8.3)"
            elif len(applicable) > 1 and not row.get("watts"):
                note = "tier undetermined (§8.7)"
            else:
                note = ""
            add(f"| {row['fixtureType']} | {_qty(row['qty'])} | "
                f"{_money(row['billedRate'])} | {rate_text} | "
                f"{'**yes**' if row.get('blended') else 'no'} | {note} |")
        add("")

    # -- other expenses -----------------------------------------------------
    if project["otherExpenses"]:
        add("## 6. Other expenses")
        add("")
        add("| Category | Description | Amount | Source |")
        add("|---|---|---|---|")
        for row in project["otherExpenses"]:
            add(f"| {row['category']} | {row['description']} | "
                f"{_money(row['amount'])} | {row.get('sourceDoc') or '—'} |")
        total = sum(r["amount"] or 0 for r in project["otherExpenses"])
        add(f"| | **Total** | **{_money(total)}** | |")
        add("")

    # -- inventory ----------------------------------------------------------
    if project.get("inventory"):
        add("## 6b. Inventory — delivered vs remaining")
        add("")
        add("Material KCE paid for that is still on the shelf. `Consumed` is "
            "delivered − remaining and should agree with the installed count.")
        add("")
        add("| Fixture type | SKU | Delivered | Remaining | Consumed | Note |")
        add("|---|---|---|---|---|---|")
        for row in project["inventory"]:
            name = row["fixtureType"] or f"_{row.get('sourceDescription')}_"
            leftover = row.get("remaining") or 0
            add(f"| {name} | `{row.get('sku') or '—'}` | {_qty(row.get('delivered'))} | "
                f"{'**' + str(leftover) + '**' if leftover else '0'} | "
                f"{_qty(row.get('consumed'))} | {row.get('note') or ''} |")
        total_left = sum(r.get("remaining") or 0 for r in project["inventory"])
        add(f"| | | | **{total_left} units left over** | | |")
        add("")

    # -- credits ------------------------------------------------------------
    if project.get("credits"):
        add("## 6c. Piece-rate credits")
        add("")
        add("| Invoice | Date | Billed | Corrected | Credit due |")
        add("|---|---|---|---|---|")
        for row in project["credits"]:
            add(f"| {row.get('invoiceNum') or '—'} | {row.get('date') or '—'} | "
                f"{_money(row.get('billedTotal'))} | {_money(row.get('correctedTotal'))} | "
                f"**{_money(row.get('creditDue'))}** |")
        total = sum(r.get("creditDue") or 0 for r in project["credits"])
        add(f"| | | | **Total** | **{_money(total)}** |")
        add("")

    # -- piece rates --------------------------------------------------------
    if project["pieceRates"]:
        add("## 7. Contracted piece rates")
        add("")
        add("| Fixture type | Wattage tier | Rate |")
        add("|---|---|---|")
        for row in project["pieceRates"]:
            add(f"| {row['fixtureType']} | {row['wattageTier'] or '—'} | "
                f"{_money(row['contractedRate'])} |")
        add("")

    # -- the flags ----------------------------------------------------------
    add("## 8. Flags — every item needing a human decision")
    add("")
    if not project["flags"]:
        add("_No flags raised._")
    for severity in ("critical", "warning", "info"):
        group = [f for f in project["flags"] if f["severity"] == severity]
        if not group:
            continue
        add(f"### {SEVERITY_ICON[severity]} {severity.upper()} ({len(group)})")
        add("")
        for flag in group:
            fixture = (f" _(–{flag['relatedFixtureType']})_"
                       if flag.get("relatedFixtureType") else "")
            add(f"- {flag['message']}{fixture}")
        add("")

    add("---")
    add("")
    add("_Generated by the KCE document intake pipeline. Every disagreement above is "
        "reported, not resolved — per the flag-don't-overwrite principle (§7)._")
    add("")

    return "\n".join(lines)
