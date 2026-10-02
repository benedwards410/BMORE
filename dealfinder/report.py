"""Render a Comparison as: bottom line first, then a table with only the rows that differ."""

from __future__ import annotations

from .compare import Comparison, Ranked
from .models import Condition

MAX_COLUMNS = 5


def _money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.2f}"


def _shipping(r: Ranked) -> str:
    s = r.offer.shipping
    return "unknown" if s is None else ("free" if s == 0 else _money(s))


def _stock(r: Ranked) -> str:
    return {True: "in stock", False: "out of stock", None: "unknown"}[r.offer.in_stock]


def _was(r: Ranked) -> str:
    rp = r.offer.regular_price
    if rp and rp > r.offer.price:
        return f"{_money(rp)} (−{(rp - r.offer.price) / rp:.0%})"
    return "—"


def _history(r: Ranked) -> str:
    return r.history.verdict(r.offer.price) if r.history else "—"


ROWS = [
    ("Price", lambda r: _money(r.offer.price)),
    ("Shipping", _shipping),
    ("Total", lambda r: _money(r.offer.total)),
    ("Retailer's 'was' price", _was),
    ("Price history", _history),
    ("Condition", lambda r: r.offer.condition.value),
    ("Sold by", lambda r: r.offer.retailer if r.offer.sold_by_retailer else (r.offer.seller or "third party")),
    ("Availability", _stock),
    ("Flags", lambda r: "; ".join(r.flags) or "—"),
]


def bottom_line(c: Comparison) -> str:
    if not c.best_new and not c.best_alternative:
        return ("No trusted, in-stock offer found. Every listing was third-party, out of stock "
                "or suspiciously cheap — see flags below.")
    parts = []
    if c.best_new:
        o = c.best_new.offer
        line = f"Buy new at {o.retailer} for {_money(o.total)}"
        others = [r.offer.total for r in c.ranked
                  if r is not c.best_new and r.trusted and r.offer.condition == Condition.NEW]
        if others:
            line += f" ({_money(min(others) - o.total)} less than the next trusted seller)"
        if c.best_new.history:
            line += f"; that's {c.best_new.history.verdict(o.price)}"
        parts.append(line + ".")
    if c.best_alternative:
        o = c.best_alternative.offer
        saving = f", saving {_money(c.best_new.offer.total - o.total)}" if c.best_new else ""
        parts.append(f"Or {o.condition.value} at {o.retailer} for {_money(o.total)}{saving} — check the warranty.")
    return " ".join(parts)


def columns(c: Comparison) -> list[Ranked]:
    """Cheapest listing per (retailer, condition): picks first, then trusted new, alternatives, the rest."""
    cheapest: dict[tuple[str, str], Ranked] = {}
    for r in c.ranked:  # already sorted trusted-first, then by price
        cheapest.setdefault((r.offer.retailer, r.offer.condition.value), r)
    picks = [r for r in (c.best_new, c.best_alternative) if r]
    rest = sorted((r for r in cheapest.values() if r not in picks),
                  key=lambda r: (not r.trusted, r.offer.condition != Condition.NEW, r.offer.total))
    return (picks + rest)[:MAX_COLUMNS]


def _header(r: Ranked, c: Comparison) -> str:
    h = r.offer.retailer
    if r.offer.condition != Condition.NEW:
        h += f" ({r.offer.condition.value})"
    return h + (" ★" if r is c.best_new else "")


def render_table(c: Comparison) -> str:
    cols = columns(c)
    if not cols:
        return ""
    header = ["", *[_header(r, c) for r in cols]]
    rows = []
    for label, fn in ROWS:
        values = [fn(r) for r in cols]
        if len(cols) > 1 and len(set(values)) == 1:
            continue  # identical across every option — not useful
        if label == "Total" and rows and rows[0][1:] == values:
            continue  # no shipping anywhere: total just repeats price
        rows.append([label, *values])
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(v.replace("|", "/") for v in row) + " |" for row in rows]
    return "\n".join(lines)


def render(c: Comparison, show_rejected: bool = True) -> str:
    out = [f"**Product:** {c.reference.title}", "", f"**Bottom line:** {bottom_line(c)}", "", render_table(c)]
    links = list(dict.fromkeys(f"- {_header(r, c).rstrip(' ★')}: {r.offer.url}" for r in columns(c)))
    if links:
        out += ["", "**Links** (tracking parameters removed):", *links]
    if show_rejected and c.rejected:
        out += ["", "**Excluded as a different product:**"]
        out += [f"- {o.retailer}: {o.title[:70]} — {m.reason}" for o, m in c.rejected]
    return "\n".join(out)
