"""What changed since the last run of this project.

Jobs get reconciled repeatedly as invoices arrive. On the second and later runs
the useful question is not "what does the whole report say" but "what moved" --
across a report with twenty-plus flags, spotting that by eye will not happen
reliably.

Comparison is done on a stable SHAPE, never on rendered text. Flag messages embed
dollar amounts and quantities, so diffing raw strings would report a change every
time a figure moved by a cent. A flag is identified by
(severity, rule tag, related fixture type) instead.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

_RULE = re.compile(r"^\[(§[^\]]+)\]")


def _rule_of(message: str) -> str:
    match = _RULE.match(message or "")
    return match.group(1) if match else "§?"


def snapshot(result: dict) -> dict:
    """Reduce a run to the stable facts worth comparing."""
    project = result["project"]

    flags = sorted({
        (flag["severity"], _rule_of(flag["message"]),
         flag.get("relatedFixtureType") or "")
        for flag in project.get("flags", [])
    })

    quantities = {
        row["fixtureType"]: {
            "ordered": row.get("ordered"),
            "approved": row.get("approved"),
            "installed": row.get("installed"),
        }
        for row in result.get("reconciliation", [])
    }

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "project": project["project"].get("name"),
        "poNumber": project["project"].get("poNumber"),
        "documents": sorted(doc.name for doc in result.get("documents", [])),
        "flags": [list(f) for f in flags],
        "quantities": quantities,
        "totals": {
            "modeledCosts": result.get("subtotals", {}).get("computed"),
            "otherExpenses": round(
                sum(r.get("amount") or 0 for r in project.get("otherExpenses", [])), 2),
            "credits": round(
                sum(r.get("creditDue") or 0 for r in project.get("credits", [])), 2),
            "inventoryRemaining": sum(
                r.get("remaining") or 0 for r in project.get("inventory", [])),
        },
    }


def history_dir(out_dir: Path, slug: str) -> Path:
    """Snapshots live beside the run's outputs (backlog item 1), one folder per
    project slug so a shared --out directory still keeps projects apart."""
    return out_dir / "history" / slug


def load_previous(out_dir: Path, slug: str, legacy_dir: Path | None = None) -> dict | None:
    """Most recent prior snapshot for this project, or None on a first run.

    `legacy_dir` is where history was kept before it moved beside the outputs
    (<pipeline>/out/history/<slug>/). It is read only while the new location
    holds nothing, so the first run after the move does not look like the first
    run ever.
    """
    folder = history_dir(out_dir, slug)
    entries = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not entries and legacy_dir is not None and legacy_dir.is_dir():
        entries = sorted(legacy_dir.glob("*.json"))
    if not entries:
        return None
    try:
        with open(entries[-1], "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def save(out_dir: Path, slug: str, snap: dict, keep: int = 20) -> Path:
    """Append this run to the project's history, pruning the oldest."""
    folder = history_dir(out_dir, slug)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = snap["timestamp"].replace(":", "-")
    path = folder / f"{stamp}.json"
    # Two runs inside one second must both be kept (and sort in run order).
    counter = 1
    while path.exists():
        counter += 1
        path = folder / f"{stamp}_{counter}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snap, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    entries = sorted(folder.glob("*.json"))
    for stale in entries[:-keep]:
        try:
            stale.unlink()
        except OSError:
            pass
    return path


def compare(previous: dict | None, current: dict) -> dict | None:
    """Diff two snapshots. None means there is no earlier run to compare to."""
    if not previous:
        return None

    old_flags = {tuple(f) for f in previous.get("flags", [])}
    new_flags = {tuple(f) for f in current.get("flags", [])}

    old_docs = set(previous.get("documents", []))
    new_docs = set(current.get("documents", []))

    quantity_moves = []
    old_quantities = previous.get("quantities", {})
    new_quantities = current.get("quantities", {})
    for fixture_type in sorted(set(old_quantities) | set(new_quantities)):
        before = old_quantities.get(fixture_type, {})
        after = new_quantities.get(fixture_type, {})
        for field in ("ordered", "approved", "installed"):
            if before.get(field) != after.get(field):
                quantity_moves.append({
                    "fixtureType": fixture_type, "field": field,
                    "from": before.get(field), "to": after.get(field),
                })

    total_moves = []
    old_totals = previous.get("totals", {})
    new_totals = current.get("totals", {})
    for key in sorted(set(old_totals) | set(new_totals)):
        if old_totals.get(key) != new_totals.get(key):
            total_moves.append({"name": key, "from": old_totals.get(key),
                                "to": new_totals.get(key)})

    diff = {
        "since": previous.get("timestamp"),
        "documentsAdded": sorted(new_docs - old_docs),
        "documentsRemoved": sorted(old_docs - new_docs),
        "flagsRaised": sorted(new_flags - old_flags),
        "flagsCleared": sorted(old_flags - new_flags),
        "quantityMoves": quantity_moves,
        "totalMoves": total_moves,
    }
    diff["unchanged"] = not any(
        diff[key] for key in ("documentsAdded", "documentsRemoved", "flagsRaised",
                              "flagsCleared", "quantityMoves", "totalMoves"))
    return diff


_TOTAL_LABELS = {
    "modeledCosts": "Modelled cost total",
    "otherExpenses": "Other expenses total",
    "credits": "Credits total",
    "inventoryRemaining": "Units left in inventory",
}


def _money(value) -> str:
    return "—" if value is None else f"${value:,.2f}"


def render(diff: dict | None) -> list[str]:
    """Markdown lines for the top of the report. Deliberately short."""
    if diff is None:
        return []

    lines = ["## Changes since the last run", ""]
    lines.append(f"_Compared against the run of {diff['since']}._")
    lines.append("")

    if diff["unchanged"]:
        lines.append("**Nothing changed.** Same documents, same quantities, same "
                     "flags, same totals as last time.")
        lines.append("")
        lines.append("---")
        lines.append("")
        return lines

    for name in diff["documentsAdded"]:
        lines.append(f"- 📄 **Document added:** `{name}`")
    for name in diff["documentsRemoved"]:
        lines.append(f"- 🗑️ **Document removed:** `{name}`")

    for move in diff["quantityMoves"]:
        fixture = move["fixtureType"]
        lines.append(f"- 🔢 **{fixture}** — {move['field']} "
                     f"{move['from'] if move['from'] is not None else '—'} → "
                     f"**{move['to'] if move['to'] is not None else '—'}**")

    for move in diff["totalMoves"]:
        label = _TOTAL_LABELS.get(move["name"], move["name"])
        if move["name"] == "inventoryRemaining":
            lines.append(f"- 📦 **{label}** {move['from']} → **{move['to']}**")
        else:
            lines.append(f"- 💵 **{label}** {_money(move['from'])} → "
                         f"**{_money(move['to'])}**")

    for severity, rule, fixture in diff["flagsRaised"]:
        target = f" on {fixture}" if fixture else ""
        lines.append(f"- ⚠️ **New {severity} flag** [{rule}]{target}")
    for severity, rule, fixture in diff["flagsCleared"]:
        target = f" on {fixture}" if fixture else ""
        lines.append(f"- ✅ **Cleared {severity} flag** [{rule}]{target}")

    lines.append("")
    lines.append("---")
    lines.append("")
    return lines
