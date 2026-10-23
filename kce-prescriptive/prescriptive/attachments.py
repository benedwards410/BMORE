"""PDF attachments: the cut-sheet bundle and BGE's Exterior Circuit Verification Form."""

import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from . import CATALOG_DIR
from .workbook import street

CUTSHEET_DIR = os.path.join(CATALOG_DIR, "cutsheets")


def cutsheet_bundle(out_pdf, resolved, models, catalog):
    """Merge every product's and control's cut sheet, in workbook model order, one copy each.
    Returns (path or None, [missing descriptions])."""
    order, missing = [], []
    for pid in models:
        fx = catalog["fixtures"][pid]
        order.append((f"{fx['model']}", fx.get("cutsheet")))
    seen_ctrl = []
    for r in resolved:
        cp = r.get("control_product")
        if cp and r["control"] not in seen_ctrl and cp.get("control_type") != "Other Non-Incentivized Option":
            seen_ctrl.append(r["control"])
            order.append((f"{cp.get('manufacturer')} {cp.get('model')}", cp.get("cutsheet")))
    w = PdfWriter()
    used = set()
    for title, fname in order:
        path = os.path.join(CUTSHEET_DIR, fname) if fname else None
        if not path or not os.path.exists(path):
            missing.append(title)
            continue
        if fname in used:
            continue
        used.add(fname)
        start = len(w.pages)
        w.append(PdfReader(path))
        w.add_outline_item(title, start)
    if not used:
        return None, missing
    with open(out_pdf, "wb") as f:
        w.write(f)
    return out_pdf, missing


# Blank-line positions on BGE-C&I-202307 "Exterior Circuit Verification Form" (points from the top).
EXT_FORM_FIELDS = {
    "premise_name": (127, 227), "premise_address": (136, 249),
    "city": (78, 271), "state": (389, 271), "zip": (484, 271),
    "name": (88, 366), "company": (104, 388),
}


def needs_exterior_form(models, catalog):
    for pid in models:
        pu = catalog["fixtures"][pid].get("primary_use") or ""
        if "Pole/Arm" in pu or "Flood" in pu:
            return True
    return False


def exterior_circuit_form(template_pdf, out_pdf, project):
    p = project["project"]
    sub = project["submitter"]
    vals = {
        "premise_name": p.get("customer_of_record"), "premise_address": street(project),
        "city": p.get("city"), "state": p.get("state", "MD"), "zip": p.get("zip"),
        "name": sub.get("contact"), "company": sub.get("company"),
    }
    base = PdfReader(template_pdf)
    page = base.pages[0]
    h = float(page.mediabox.height)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(float(page.mediabox.width), h))
    c.setFont("Helvetica", 10)
    for key, (x, y_top) in EXT_FORM_FIELDS.items():
        if vals.get(key):
            c.drawString(x, h - y_top + 2.5, str(vals[key]))
    c.save()
    buf.seek(0)
    page.merge_page(PdfReader(buf).pages[0])
    w = PdfWriter()
    w.add_page(page)
    with open(out_pdf, "wb") as f:
        w.write(f)
    return out_pdf
