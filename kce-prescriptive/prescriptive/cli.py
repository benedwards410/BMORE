"""Command line for the prescriptive package bot.

  python3 -m prescriptive.cli extract-template --template BLANK.xlsm
  python3 -m prescriptive.cli audit-template --out audit.xlsx
  python3 -m prescriptive.cli audit-to-project AUDIT.xlsx --out project.json
  python3 -m prescriptive.cli import-workbook FILLED.xlsm --out project.json [--model-map map.json]
  python3 -m prescriptive.cli check project.json [--against OLD.xlsm|TC.pdf ...]
  python3 -m prescriptive.cli build project.json --out ./out [--template BLANK.xlsm] [--force]
  python3 -m prescriptive.cli readback project.json SAVED_IN_EXCEL.xlsm --out ./out

Run from the kce-prescriptive folder (or put it on PYTHONPATH).
"""

import argparse
import json
import sys

from . import audit, build, importer, qa, template_map, terms_pdf


def _print_findings(findings, levels=("BLOCKER", "ASK", "WARN")):
    for lvl in levels:
        for f in [x for x in findings if x["level"] == lvl]:
            where = f" [{f['line']}]" if f["line"] else ""
            print(f"  {lvl:<7} r{f['rule']}{where} {f['message']}")
            if f.get("fix"):
                print(f"          -> {f['fix']}")


def _against(project, path):
    if path.lower().endswith(".pdf"):
        vals, payee = terms_pdf.read_back(path)
        other = {"customer_of_record": vals.get("Project Name"), "site_address": vals.get("Street Address where the work is taking place"),
                 "city": vals.get("City"), "zip": vals.get("Zip"), "bge_account": vals.get("BGE Electric Account Number") or None,
                 "payee": payee}
        return qa.compare_identity(project, other, f"T&C {path}")
    pj, _ = importer.from_bge_workbook(path)
    pp = pj["project"]
    other = {"site_address": pp.get("site_address"), "city": pp.get("city"), "zip": pp.get("zip")}
    return qa.compare_identity(project, other, f"workbook {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="prescriptive")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("extract-template", help="refresh references/template_tables.json from a blank BGE workbook")
    s.add_argument("--template", required=True)

    s = sub.add_parser("audit-template", help="write the standard KCE audit sheet")
    s.add_argument("--out", required=True)

    s = sub.add_parser("audit-to-project", help="standard audit sheet -> project.json")
    s.add_argument("audit")
    s.add_argument("--out", required=True)

    s = sub.add_parser("import-workbook", help="existing BGE workbook -> project.json")
    s.add_argument("workbook")
    s.add_argument("--out", required=True)
    s.add_argument("--model-map", help="JSON {workbook model string: catalog product id}")

    s = sub.add_parser("check", help="QA only")
    s.add_argument("project")
    s.add_argument("--against", nargs="*", default=[], help="older workbook(s) or T&C PDF(s) to compare identity/payee with")

    s = sub.add_parser("build", help="QA, then every output")
    s.add_argument("project")
    s.add_argument("--out", required=True)
    s.add_argument("--template")
    s.add_argument("--force", action="store_true", help="write review drafts even when QA is BLOCKED")

    s = sub.add_parser("readback", help="compare an Excel-saved workbook with the estimate and finalize outputs")
    s.add_argument("project")
    s.add_argument("saved")
    s.add_argument("--out", required=True)
    s.add_argument("--template")
    s.add_argument("--force", action="store_true")

    a = ap.parse_args(argv)

    if a.cmd == "extract-template":
        print(template_map.write_tables(template_map.extract(a.template)))
        return 0
    if a.cmd == "audit-template":
        print(audit.write_template(a.out))
        return 0
    if a.cmd == "audit-to-project":
        project, notes = audit.to_project(a.audit)
        with open(a.out, "w") as f:
            json.dump(project, f, indent=1)
        print(a.out)
        for n in notes:
            print("  note:", n)
        return 0
    if a.cmd == "import-workbook":
        mm = json.load(open(a.model_map)) if a.model_map else None
        project, notes = importer.from_bge_workbook(a.workbook, model_map=mm)
        with open(a.out, "w") as f:
            json.dump(project, f, indent=1)
        print(a.out)
        for n in notes:
            print("  note:", n)
        return 0
    if a.cmd == "check":
        ctx = build.prepare(a.project)
        findings = ctx["findings"]
        for path in a.against:
            findings += _against(ctx["project"], path)
        st = qa.status(findings)
        est = ctx["estimate"]
        print(f"QA: {st}   estimate ${est['total']:,.0f} (lighting ${est['lighting']:,.0f} + controls ${est['controls']:,.0f})")
        _print_findings(findings)
        return 0 if st == "READY" else 2
    if a.cmd in ("build", "readback"):
        summary = build.run(a.project, a.out, template=a.template, force=a.force,
                            readback_xlsm=getattr(a, "saved", None))
        print(f"QA: {summary['status']}   estimate ${summary['estimate']['total']:,.0f}   -> {summary['out_dir']}")
        if summary.get("readback"):
            print("  readback:", summary["readback"]["message"])
        for k, v in summary["files"].items():
            if v:
                print(f"  {k:<14} {v}")
        if summary.get("note"):
            print(" ", summary["note"])
        return 0 if summary["status"] == "READY" else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
