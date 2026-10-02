"""Command-line interface.

    dealfinder compare "Sony WH-1000XM6"                   # search every configured source
    dealfinder compare --url https://www.bestbuy.com/site/...  --url https://www.target.com/p/...
    dealfinder compare --upc 027242927896 --prefer bestbuy   # can Best Buy match a lower price?
    dealfinder pricematch --at bestbuy --price 399.99 --on 2026-09-28 --upc 027242927896
    dealfinder track add "XM6 headphones" --upc 027242927896 --target 329
    dealfinder track check                                  # run from cron / a scheduler
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from . import notify
from .compare import compare
from .finder import Finder
from .pricematch import Purchase, after_purchase, before_purchase, load_policies
from .report import render
from .tracker import Tracker


def _add_product_args(p: argparse.ArgumentParser):
    p.add_argument("--url", action="append", default=[], help="product page URL (repeatable)")
    p.add_argument("--upc", help="UPC / EAN / GTIN barcode number")
    p.add_argument("--model", help="manufacturer model number, e.g. MXP93LL/A")
    p.add_argument("--no-ebay", action="store_true", help="skip eBay marketplace listings")


def _gather(args, query=None):
    finder = Finder(include_ebay=not args.no_ebay)
    g = finder.gather(query=query, urls=args.url, gtin=args.upc, model=args.model)
    for w in g.warnings:
        print(f"note: {w}", file=sys.stderr)
    return g


def cmd_sources(args) -> int:
    for name, ok in Finder().sources_status().items():
        print(f"{'✓' if ok else '✗'} {name}")
    print("\nSet BESTBUY_API_KEY, KEEPA_API_KEY, EBAY_CLIENT_ID/EBAY_CLIENT_SECRET to enable more sources.")
    return 0


def cmd_compare(args) -> int:
    query = " ".join(args.query) or None
    if not (query or args.url or args.upc or args.model):
        print("give a search query, --url, --upc or --model", file=sys.stderr)
        return 2
    g = _gather(args, query)
    if not g.offers:
        return 1
    c = compare(g.offers, reference=g.reference, history=g.history)
    if args.json:
        print(json.dumps({
            "reference": c.reference.to_dict(),
            "best_new": c.best_new.offer.to_dict() if c.best_new else None,
            "best_alternative": c.best_alternative.offer.to_dict() if c.best_alternative else None,
            "offers": [{**r.offer.to_dict(), "flags": r.flags} for r in c.ranked],
            "excluded": [{"title": o.title, "retailer": o.retailer, "reason": m.reason} for o, m in c.rejected],
        }, indent=2))
        return 0
    print(render(c))
    if args.prefer:
        op = before_purchase(args.prefer, [r.offer for r in c.ranked], load_policies())
        if op:
            print(f"\n**Price match:** {op.describe()}")
        else:
            print(f"\n**Price match:** nothing for {args.prefer} to match (or it doesn't match competitors).")
    return 0


def cmd_pricematch(args) -> int:
    g = _gather(args)
    if not g.offers:
        return 1
    c = compare(g.offers, reference=g.reference)
    purchase = Purchase(args.at, args.price, date.fromisoformat(args.on) if args.on else date.today())
    ops = after_purchase(purchase, [r.offer for r in c.ranked], load_policies())
    if not ops:
        print(f"Nothing to claim: no eligible lower price than ${args.price:,.2f} found right now.")
        return 0
    for op in ops:
        print(op.describe())
    return 0


def cmd_track(args) -> int:
    t = Tracker(args.db)
    try:
        if args.track_cmd == "add":
            if not (args.url or args.upc or args.model):
                print("track add needs --url, --upc or --model", file=sys.stderr)
                return 2
            item_id = t.add(args.label, args.url, gtin=args.upc, model=args.model, target_price=args.target)
            print(f"tracking #{item_id}: {args.label}")
        elif args.track_cmd == "list":
            for i in t.items():
                bits = [f"target ${i.target_price:,.2f}" if i.target_price else "",
                        f"bought {i.purchased_retailer} ${i.purchased_price:,.2f} on {i.purchased_on}" if i.purchased_price else ""]
                print(f"#{i.id} {i.label}  {'  '.join(b for b in bits if b)}")
                for u in i.urls:
                    print(f"     {u}")
        elif args.track_cmd == "remove":
            t.remove(args.id)
        elif args.track_cmd == "bought":
            t.record_purchase(args.id, args.at, args.price, date.fromisoformat(args.on) if args.on else date.today())
            print(f"#{args.id}: will watch for price drops you can claim back")
        elif args.track_cmd == "check":
            return _check(t, args)
        return 0
    finally:
        t.close()


def _check(t: Tracker, args) -> int:
    finder = Finder(include_ebay=False)  # marketplace noise isn't worth an alert
    policies = load_policies()
    items = [i for i in t.items() if args.id is None or i.id == args.id]
    for item in items:
        g = finder.gather(urls=item.urls, gtin=item.gtin, model=item.model, query=item.label)
        for w in g.warnings:
            print(f"note [{item.label}]: {w}", file=sys.stderr)
        if not g.offers:
            continue
        c = compare(g.offers, reference=g.reference)
        for r in c.ranked:
            if not r.trusted:
                continue
            for alert in t.evaluate(item, r.offer):
                notify.send(alert.message())
            t.record(item.id, r.offer)
        if item.purchased_price and item.purchased_on:
            purchase = Purchase(item.purchased_retailer, item.purchased_price, item.purchased_on, item.label)
            for op in after_purchase(purchase, [r.offer for r in c.ranked], policies):
                notify.send(f"{item.label}: {op.describe()}")
        if not args.quiet and c.best_new:
            print(f"#{item.id} {item.label}: best {c.best_new.offer.retailer} ${c.best_new.offer.total:,.2f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dealfinder", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sources", help="show which price sources are configured").set_defaults(fn=cmd_sources)

    p = sub.add_parser("compare", help="compare prices for one product")
    p.add_argument("query", nargs="*", help="product name or search terms")
    _add_product_args(p)
    p.add_argument("--prefer", metavar="RETAILER", help="retailer you'd rather buy from; checks whether it will price-match")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("pricematch", help="already bought it? find money you can claim back")
    _add_product_args(p)
    p.add_argument("--at", required=True, help="retailer you bought from (bestbuy, target, costco, ...)")
    p.add_argument("--price", required=True, type=float, help="price you paid, before tax")
    p.add_argument("--on", help="purchase date YYYY-MM-DD (default today)")
    p.set_defaults(fn=cmd_pricematch)

    p = sub.add_parser("track", help="watch prices over time")
    p.add_argument("--db", help="SQLite path (default ~/.dealfinder/prices.db or $DEALFINDER_DB)")
    tsub = p.add_subparsers(dest="track_cmd", required=True)
    a = tsub.add_parser("add", help="start tracking a product")
    a.add_argument("label")
    a.add_argument("--url", action="append", default=[])
    a.add_argument("--upc")
    a.add_argument("--model")
    a.add_argument("--target", type=float, help="alert when the price reaches this")
    tsub.add_parser("list")
    r = tsub.add_parser("remove")
    r.add_argument("id", type=int)
    b = tsub.add_parser("bought", help="record a purchase to watch for price-adjustment refunds")
    b.add_argument("id", type=int)
    b.add_argument("--at", required=True)
    b.add_argument("--price", required=True, type=float)
    b.add_argument("--on")
    ch = tsub.add_parser("check", help="refresh prices and send alerts (schedule this)")
    ch.add_argument("--id", type=int)
    ch.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_track)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
