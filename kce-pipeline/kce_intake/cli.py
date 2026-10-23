"""py -m kce_intake {login | sync | run-changed | status}"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from logging.handlers import RotatingFileHandler

from . import __version__
from .config import Config, load_config
from .filer import Candidate, Filer
from .projects import ProjectIndex
from .runner import run_changed
from .state import HashCache, Lock, State, parse_iso, read_json

log = logging.getLogger("kce_intake")


def setup_logging(cfg: Config, verbose: bool) -> None:
    root = logging.getLogger("kce_intake")
    for handler in list(root.handlers):  # main() may run more than once per process (tests)
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)
    try:
        fh = RotatingFileHandler(cfg.log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass


def _open(cfg: Config):
    state = State(cfg.state_path)
    cache = HashCache(cfg.hash_cache_path)
    index = ProjectIndex(cfg.projects_root, cfg.out_subfolder).rebuild()
    return state, cache, index


# ---- commands --------------------------------------------------------------

def cmd_login(cfg: Config, args) -> int:
    from .graph import GraphClient

    account = GraphClient(cfg).login()
    print(f"Signed in as {account}. Token cache: {cfg.token_cache_path}")
    return 0


def cmd_sync(cfg: Config, args) -> int:
    from .sources import dropfolder, outlook, quickbooks

    state, cache, index = _open(cfg)
    cfg.projects_root.mkdir(parents=True, exist_ok=True)
    filer = Filer(cfg, index, cache)
    tally: Counter = Counter()

    def handle(cand: Candidate) -> None:
        outcome = filer.file(cand)
        tally[outcome.action] += 1
        where = outcome.path.parent.name if outcome.path else ""
        detail = f"{outcome.mtx} ({outcome.match}: {outcome.matched_on})" if outcome.mtx else outcome.reason
        log.info("%-9s %s → %s %s", outcome.action, outcome.name, where, detail)

    if not args.no_drop:
        for cand in dropfolder.find_candidates(cfg):
            handle(cand)

    if not args.no_mail:
        from .graph import GraphClient, NotLoggedIn

        client = GraphClient(cfg)
        since = parse_iso(args.since) if args.since else outlook.default_since(cfg, state)
        log.info("mail: scanning messages received since %s", since.strftime("%Y-%m-%d %H:%M UTC"))

        def on_link(req: outlook.LinkRequest) -> None:
            msg = req.message
            data, how = quickbooks.fetch_invoice_pdf(req.link)
            if data:
                name = f"Beacon Invoice {req.invoice_number}.pdf"
                handle(Candidate(name=name, data=data, source="quickbooks", context={
                    "messageId": msg["id"], "internetMessageId": msg.get("internetMessageId"),
                    "subject": msg.get("subject"), "sender": msg.get("sender"),
                    "received": msg.get("received"), "bodyText": msg.get("bodyText", ""),
                    "link": req.link, "how": how}))
            else:
                path = quickbooks.record_needs_manual(cfg, msg.get("subject", ""), msg.get("sender", ""),
                                                     req.link, how, req.invoice_number)
                tally["needs_manual"] += 1
                log.info("%-9s %s → %s (%s)", "manual", msg.get("subject", ""), path.name, how)

        try:
            for cand in outlook.find_candidates(cfg, client, state, since, on_link=on_link):
                handle(cand)
        except NotLoggedIn as exc:
            log.error("mail: %s", exc)
            state.save(); cache.save()
            return 2

    state.save()
    cache.save()
    index.rebuild()
    summary = ", ".join(f"{k} {v}" for k, v in sorted(tally.items())) or "nothing new"
    log.info("sync done: %s", summary)
    return 0


def cmd_run_changed(cfg: Config, args) -> int:
    state, cache, index = _open(cfg)
    worst, results = run_changed(cfg, index, cache, state, force=args.all, dry_run=args.dry_run, only_mtx=args.mtx)
    state.save()
    cache.save()
    if not results:
        log.info("run-changed: no project changed since its last run")
    for r in results:
        if r.skipped:
            log.info("%s: %s", r.mtx, r.skipped)
        else:
            c = r.counts
            log.info("%s: exit %s — %s critical / %s warning / %s info%s", r.mtx, r.exit_code,
                     c.get("critical", 0), c.get("warning", 0), c.get("info", 0),
                     f" → {r.report.name}" if r.report else "")
    return worst


def cmd_status(cfg: Config, args) -> int:
    state, cache, index = _open(cfg)
    rows = []
    for mtx, rec in sorted(index.records.items()):
        last = read_json(rec.folder / cfg.out_subfolder / "last_run.json", {})
        c = last.get("counts", {})
        inferred = sum(1 for f in read_json(rec.intake_dir / "manifest.json", {"files": []})["files"] if f.get("match") == "inferred")
        rows.append((rec.folder.name, last.get("ranAt", "never")[:16], str(c.get("critical", "-")), str(c.get("warning", "-")), str(inferred)))
    width = max([len(r[0]) for r in rows] + [10])
    print(f"{'project'.ljust(width)}  {'last run':16}  crit  warn  inferred")
    for name, ran, crit, warn, inf in rows:
        print(f"{name.ljust(width)}  {ran:16}  {crit:>4}  {warn:>4}  {inf:>8}")
    held = sum(1 for p in cfg.unmatched_dir.rglob("*") if p.is_file() and p.suffix.lower() in cfg.input_extensions) if cfg.unmatched_dir.exists() else 0
    manual = len(list(cfg.needs_manual_dir.glob("*.md"))) if cfg.needs_manual_dir.exists() else 0
    print(f"\nheld in _unmatched: {held}   needs manual download: {manual}")
    if state.mail_watermark:
        print(f"mail watermark: {state.mail_watermark:%Y-%m-%d %H:%M} UTC")
    return 0


# ---- entry -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kce_intake", description=__doc__)
    p.add_argument("--config", help="path to intake.json (default: config/intake.json)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="one-time device-code sign-in to Microsoft 365")

    s = sub.add_parser("sync", help="pull new documents and file them per MTX")
    s.add_argument("--since", help="ISO date/time; default = last watermark (first run: lookback window)")
    s.add_argument("--no-mail", action="store_true", help="skip Outlook, only sweep the drop folders")
    s.add_argument("--no-drop", action="store_true", help="skip the drop folders")

    r = sub.add_parser("run-changed", help="run the pipeline where inputs changed")
    r.add_argument("--all", action="store_true", help="run every project, changed or not")
    r.add_argument("--mtx", help="only this MTX")
    r.add_argument("--dry-run", action="store_true")

    sub.add_parser("status", help="one table: project, last run, flag counts, held items")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    setup_logging(cfg, args.verbose)
    handlers = {"login": cmd_login, "sync": cmd_sync, "run-changed": cmd_run_changed, "status": cmd_status}
    if args.command == "status" or args.command == "login":
        return handlers[args.command](cfg, args)
    lock = Lock(cfg.lock_path)
    if not lock.acquire():
        log.error("another intake run is in progress (%s)", cfg.lock_path)
        return 3
    try:
        return handlers[args.command](cfg, args)
    except Exception:  # noqa: BLE001 - a scheduled task needs the trace in the log, not a silent exit
        log.exception("%s failed", args.command)
        return 2
    finally:
        lock.release()
