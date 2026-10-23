"""Run the whole package: resolve -> estimate -> QA -> (if not blocked) every output."""

import glob
import json
import os

from . import TEMPLATES_DIR, attachments, estimate, portal_sheet, proposal, qa, reports, terms_pdf, workbook
from .project import load, load_catalog, load_config, load_existing, load_measure_rules, resolve, slug
from .template_map import load_tables

TNC_TEMPLATE = os.path.join(TEMPLATES_DIR, "bge_terms_and_conditions_202510.pdf")
EXT_FORM_TEMPLATE = os.path.join(TEMPLATES_DIR, "bge_exterior_circuit_verification_202307.pdf")


def find_template(path=None):
    cand = path or os.environ.get("BGE_TEMPLATE")
    if not cand:
        hits = sorted(glob.glob(os.path.join(TEMPLATES_DIR, "bge", "*.xlsm")))
        cand = hits[0] if hits else None
    if not cand or not os.path.exists(cand):
        raise FileNotFoundError(
            "No blank BGE workbook. Put it in kce-prescriptive/templates/bge/ (not committed), "
            "set BGE_TEMPLATE, or pass --template.")
    return cand


def prepare(project_src, catalog=None):
    cfg = load_config()
    tables = load_tables()
    catalog = catalog or load_catalog()
    rules = load_measure_rules()
    project = load(project_src, cfg)
    resolved, models = resolve(project, tables, catalog, load_existing(), rules, cfg.get("prices", {}))
    est = estimate.project(resolved, tables)
    findings = qa.check(project, resolved, est, tables, rules, catalog, cfg)
    return {"config": cfg, "tables": tables, "catalog": catalog, "rules": rules, "project": project,
            "resolved": resolved, "models": models, "estimate": est, "findings": findings,
            "status": qa.status(findings)}


def run(project_src, out_dir, template=None, force=False, readback_xlsm=None, catalog=None):
    ctx = prepare(project_src, catalog)
    project, resolved, models, est = ctx["project"], ctx["resolved"], ctx["models"], ctx["estimate"]
    cfg, tables, cat = ctx["config"], ctx["tables"], ctx["catalog"]
    name = slug(project["project"].get("name") or project["project"].get("customer_of_record") or project["project"].get("site_address"))
    out = os.path.join(out_dir, name)
    os.makedirs(out, exist_ok=True)
    f = lambda suffix: os.path.join(out, f"{name}_{suffix}")

    rb = None
    if readback_xlsm:
        rb = reports.readback(readback_xlsm, resolved, est)
        ctx["findings"].append(qa._f(qa.INFO if rb["ok"] else qa.BLOCKER, 11, rb["message"]))
        for d in rb.get("diffs", []):
            ctx["findings"].append(qa._f(qa.BLOCKER, 11, f"Excel {d['excel_lighting']}+{d['excel_control']} vs bot {d['bot_lighting']}+{d['bot_control']}", line=d["line"]))
        ctx["status"] = qa.status(ctx["findings"])

    status = ctx["status"]
    files = {"qa_report": f("QA_INTERNAL.xlsx")}
    reports.qa_workbook(files["qa_report"], project, resolved, est, ctx["findings"], status, rb)
    summary = {"status": status, "out_dir": out, "files": files, "estimate": {k: est[k] for k in ("lighting", "controls", "total")},
               "counts": {lvl: sum(1 for x in ctx["findings"] if x["level"] == lvl) for lvl in ("BLOCKER", "ASK", "WARN", "INFO")}}
    if status == "BLOCKED" and not force:
        summary["note"] = "BLOCKED: only the QA report was written. Fix the blockers, or rerun with --force for review drafts."
        _write_summary(out, name, summary, ctx)
        return summary

    tmpl = find_template(template)
    files["workbook"] = workbook.build(tmpl, f("BGE_Worksheet.xlsm"), project, resolved, models, cat)
    files["terms"] = terms_pdf.fill(TNC_TEMPLATE, f("Terms_Acknowledgement.pdf"), project, cfg)
    cut, missing = attachments.cutsheet_bundle(f("Cut_Sheets.pdf"), resolved, models, cat)
    files["cutsheets"] = cut
    summary["cutsheets_missing"] = missing
    if attachments.needs_exterior_form(models, cat):
        files["exterior_form"] = attachments.exterior_circuit_form(EXT_FORM_TEMPLATE, f("Exterior_Circuit_Verification.pdf"), project)
    official = bool(rb and rb.get("ok"))
    incentive = rb["totals"]["incentive"] if official else None
    docx_path, nums = proposal.build(f("Proposal_DRAFT.docx"), project, resolved, est, tables, cfg, incentive, official)
    files["proposal_docx"] = docx_path
    try:
        files["proposal_pdf"] = proposal.to_pdf(docx_path, out)
    except Exception as e:  # LibreOffice missing or failed: the .docx is still the deliverable
        summary["proposal_pdf_error"] = str(e)
    summary["proposal"] = {k: round(v, 2) if isinstance(v, float) else v for k, v in nums.items()}
    names = {k: os.path.basename(v) for k, v in files.items() if v}
    files["portal_sheet"] = portal_sheet.build(f("Portal_Cheat_Sheet.html"), project, cfg, est, names, status, rb)
    if rb:
        summary["readback"] = {k: rb[k] for k in ("ok", "message", "totals")}
    _write_summary(out, name, summary, ctx)
    return summary


def _write_summary(out, name, summary, ctx):
    data = dict(summary)
    data["findings"] = ctx["findings"]
    data["models"] = ctx["models"]
    with open(os.path.join(out, f"{name}_package.json"), "w") as fh:
        json.dump(data, fh, indent=1, default=str)
