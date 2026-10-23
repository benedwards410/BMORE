"""CLI entry point.

    python -m kce_pipeline <folder> [--out DIR] [--backend auto|api|cache]

Takes a folder of 2-10 documents belonging to ONE project and writes:
  <out>/<slug>.project.json          the section 6.1 schema, drop-in for the ROI tracker
  <out>/<slug>.reconciliation.md     the human-readable report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import diff
from .report import build_report
from .run import run_batch


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "project").lower()).strip("_")
    return slug or "project"


def _json_ready(project: dict) -> dict:
    """The project dict is already plain JSON types; this is just a guard rail."""
    return json.loads(json.dumps(project, default=str))


def check_api(base_dir: Path) -> int:
    """Verify live extraction is usable. Never prints the key itself."""
    import os

    from .run import load_config

    # Config sanity first -- a malformed config fails every run confusingly.
    try:
        settings, vocabulary = load_config(base_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] could not read config/: {type(exc).__name__}: {exc}")
        print("       Check config/settings.json and config/canonical_fixtures.json "
              "are valid JSON.")
        return 1
    print(f"[ok]   config loaded ({len(vocabulary.get('canonicalTypes', []))} "
          f"fixture types, {len(vocabulary.get('skuMap') or {})} known SKUs)")

    standard = base_dir / "config" / "standard_piece_rates.json"
    if standard.exists():
        with open(standard, "r", encoding="utf-8") as handle:
            count = len(json.load(handle).get("rates", []))
        print(f"[ok]   standard piece rate card present ({count} rates)")
    else:
        print("[warn] no config/standard_piece_rates.json -- projects without their "
              "own rate schedule will have no contracted rates to compare against.")

    cache_dir = base_dir / settings.get("extraction", {}).get(
        "cacheDir", "extraction_cache")
    cached = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
    print(f"[ok]   {cached} document(s) cached for offline replay")

    model = settings.get("extraction", {}).get("model")
    ok = True

    try:
        import anthropic
        print(f"[ok]   anthropic package installed (v{anthropic.__version__})")
    except ImportError:
        print("[FAIL] anthropic package not installed -- run: pip install anthropic")
        return 1

    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        # Show only enough to tell two keys apart. Never the whole value.
        print(f"[ok]   ANTHROPIC_API_KEY is set (length {len(key)}, "
              f"ends ...{key[-4:]})")
    else:
        print("[FAIL] ANTHROPIC_API_KEY is not set in this terminal.")
        print("       Set it with:  setx ANTHROPIC_API_KEY \"sk-ant-...\"")
        print("       then open a NEW terminal -- setx only affects future sessions.")
        return 1

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model, max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the word: ready"}])
        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        print(f"[ok]   API call succeeded using model {model!r} -> {reply!r}")
        print(f"[ok]   tokens billed: {response.usage.input_tokens} in / "
              f"{response.usage.output_tokens} out")
    except Exception as exc:  # noqa: BLE001 - surface whatever the SDK reports
        print(f"[FAIL] API call failed: {type(exc).__name__}: {exc}")
        print("       Common causes: key revoked, no billing/credits on the "
              "Console account, or the model name in config/settings.json is wrong.")
        return 1

    print()
    print("Live extraction is ready. New projects will now be read via the API,")
    print("and every read backfills extraction_cache/ for offline replay.")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="kce_pipeline",
        description="Multi-document intake pipeline for LED retrofit project "
                    "reconciliation.")
    parser.add_argument("folder", type=Path, nargs="?",
                        help="folder of documents for ONE project")
    parser.add_argument("--check-api", action="store_true",
                        help="verify the Anthropic API is usable, then exit "
                             "(never prints the key)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory (default: <pipeline>/out)")
    parser.add_argument("--backend", choices=["auto", "api", "cache"], default=None,
                        help="override the configured extraction backend")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the console summary")
    args = parser.parse_args(argv)

    base_dir = Path(__file__).resolve().parent.parent

    if args.check_api:
        return check_api(base_dir)

    if args.folder is None:
        parser.error("a project folder is required (or pass --check-api)")

    out_dir = args.out or (base_dir / "out")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.folder.is_dir():
        parser.error(f"{args.folder} is not a directory")

    result = run_batch(args.folder, base_dir, backend_override=args.backend)
    project = result["project"]

    slug = slugify(project["project"].get("name") or args.folder.name)

    # What moved since the last run of this same project (None on a first run).
    current = diff.snapshot(result)
    result["diff"] = diff.compare(diff.load_previous(base_dir, slug), current)
    diff.save(base_dir, slug, current)
    json_path = out_dir / f"{slug}.project.json"
    report_path = out_dir / f"{slug}.reconciliation.md"

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(_json_ready(project), handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(build_report(result))

    counts = {"critical": 0, "warning": 0, "info": 0}
    for flag in project["flags"]:
        counts[flag["severity"]] += 1

    if not args.quiet:
        meta = project["project"]
        skipped = [d for d in result["documents"]
                   if d.error or d.doc_type == "unknown" or d.excluded]

        print()
        print("=" * 70)
        print(f"  {meta.get('name') or 'Unnamed project'}   "
              f"({meta.get('poNumber') or 'no MTX number found'})")
        if meta.get("customer"):
            print(f"  {meta['customer']}")
        print("=" * 70)

        print(f"  Documents read    : {len(result['documents']) - len(skipped)} of "
              f"{len(result['documents'])}"
              + (f"   ({len(skipped)} skipped)" if skipped else ""))
        for doc in skipped:
            # Order matters: a file rejected as incomplete also has the default
            # doc_type of "unknown", and reporting that would hide the real
            # reason -- which is the one the user can actually act on.
            why = ("different MTX number" if doc.excluded
                   else doc.error if doc.error
                   else "not a recognised document type")
            print(f"                      - {doc.name}  ({why})")

        print(f"  Extraction        : {result['backend']}"
              + ("   (replayed from cache, no API calls)"
                 if result["backend"] == "cache" else "   (live API)"))

        changes = result.get("diff")
        if changes is None:
            print("  Since last run    : first run of this project")
        elif changes["unchanged"]:
            print(f"  Since last run    : nothing changed "
                  f"(last run {changes['since']})")
        else:
            moved = (len(changes["documentsAdded"]) + len(changes["documentsRemoved"])
                     + len(changes["quantityMoves"]) + len(changes["totalMoves"])
                     + len(changes["flagsRaised"]) + len(changes["flagsCleared"]))
            print(f"  Since last run    : {moved} change(s) -- see the top of the "
                  f"report")

        subtotals = result["subtotals"]
        if subtotals["reported"] is not None:
            verdict = ("agrees with the report"
                       if subtotals["matches"] else "*** DOES NOT AGREE ***")
            print(f"  Cost cross-check  : ${subtotals['computed']:,.2f} {verdict}")

        print()
        if counts["critical"]:
            print(f"  NOT READY TO CLOSE OUT - {counts['critical']} critical "
                  f"item(s) need a decision:")
            for flag in project["flags"]:
                if flag["severity"] == "critical":
                    text = flag["message"].split("] ", 1)[-1]
                    print(f"     * {text[:160]}")
        else:
            print("  No blocking issues found.")
        print(f"  Also to review    : {counts['warning']} warning, "
              f"{counts['info']} minor")

        print()
        print(f"  READ THIS   ->  {report_path}")
        print(f"  For tracker ->  {json_path}")
        print()
        print("  Nothing is auto-corrected. Every disagreement between documents")
        print("  is reported for a person to decide.")
        print()

    # Non-zero when a critical flag is outstanding, so this can gate automation.
    return 1 if counts["critical"] else 0


if __name__ == "__main__":
    sys.exit(main())
