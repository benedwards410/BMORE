"""Stand-in for `python -m kce_pipeline <folder> --out <dir>`.

Writes <slug>.project.json and <slug>.reconciliation.md like the real tool and
uses its exit-code convention: 1 when a critical flag exists, else 0. A file
named CRITICAL.pdf in the folder produces a critical flag; BOOM.pdf makes the
tool crash (exit 7) so runner tests can see a tool failure."""
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else folder / "out"
out.mkdir(parents=True, exist_ok=True)
names = sorted(p.name for p in folder.iterdir() if p.is_file())
if "BOOM.pdf" in names:
    print("fake pipeline exploding", file=sys.stderr)
    sys.exit(7)
flags = [{"severity": "info", "message": f"{n} read", "relatedFixtureType": None} for n in names]
flags.append({"severity": "warning", "message": "revenue not auto-filled", "relatedFixtureType": None})
if "CRITICAL.pdf" in names:
    flags.append({"severity": "critical", "message": "Wall Pack quantities do not reconcile", "relatedFixtureType": "Wall Pack"})
slug = "fake_project"
(out / f"{slug}.project.json").write_text(json.dumps({
    "project": {"name": "Fake Project", "poNumber": "MTX11111111",
                "address": "3320 GREAT VALLEY Drive, West Friendship MD 21794", "revenue": None},
    "flags": flags,
}, indent=2), encoding="utf-8")
(out / f"{slug}.reconciliation.md").write_text("# Reconciliation Report — Fake Project\n\ninputs: " + ", ".join(names) + "\n", encoding="utf-8")
print(f"fake pipeline: {len(names)} documents, {sum(1 for f in flags if f['severity']=='critical')} critical")
sys.exit(1 if any(f["severity"] == "critical" for f in flags) else 0)
