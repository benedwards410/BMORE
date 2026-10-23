"""Pre-fill BGE's 'Terms and Conditions & Customer Acknowledgement' (fillable 202510 edition).

Signature and date stay blank: the BGE customer of record signs. BGE's form
defines 'Rebate Assignee Company/Entity Name' as a signature field, so that one
value is stamped onto the page instead of filled.
"""

import io

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.pdfgen import canvas

from .workbook import street

PAYEE_BOX = {"customer": "Customer", "contractor": "Service Provider", "third_party": "ThirdParty"}
ASSIGNEE_FIELD = "Rebate Assignee CompanyEntity Name"


def values(project, config):
    p = project["project"]
    cc = project.get("customer_contact") or {}
    co = config["company"]
    v = {
        "Project Name": p.get("name") or p.get("customer_of_record"),
        "BGE Electric Account Number": p.get("bge_account"),
        "Street Address where the work is taking place": street(project),
        "City": p.get("city"),
        "State": p.get("state", "MD"),
        "Zip": str(p.get("zip") or ""),
        "Authorized Representative please print": cc.get("name"),
        "Title": cc.get("title"),
        "Email": cc.get("email"),
        "Phone": cc.get("phone"),
    }
    payee = project.get("payee", "contractor")
    kce = payee != "customer"
    v.update({"Street Address": co["street"] if kce else None, "City_2": co["city"] if kce else None,
              "State_2": co["state"] if kce else None, "Zip_2": co["zip"] if kce else None})
    return {k: ("" if x is None else str(x)) for k, x in v.items()}, payee


def fill(template_pdf, out_pdf, project, config):
    text, payee = values(project, config)
    reader = PdfReader(template_pdf)
    writer = PdfWriter()
    writer.append(reader)
    assignee_rect, assignee_page = None, None
    for pi, page in enumerate(writer.pages):
        names = []
        for a in page.get("/Annots") or []:
            a = a.get_object()
            t = a.get("/T")
            if t is None and a.get("/Parent"):
                t = a["/Parent"].get_object().get("/T")
            names.append(t)
            if t in PAYEE_BOX.values():
                on = t == PAYEE_BOX[payee]
                state = NameObject("/On" if on else "/Off")
                a[NameObject("/AS")] = state
                (a["/Parent"].get_object() if a.get("/Parent") else a)[NameObject("/V")] = state
            if t == "Same as above":
                a[NameObject("/AS")] = NameObject("/Off")
                a[NameObject("/V")] = NameObject("/Off")
            if t == ASSIGNEE_FIELD:
                assignee_rect, assignee_page = [float(x) for x in a["/Rect"]], pi
        if any(n in text for n in names):
            writer.update_page_form_field_values(page, text, auto_regenerate=False)
    writer.set_need_appearances_writer(True)

    if payee != "customer" and assignee_rect:
        x0, y0, x1, y1 = assignee_rect
        buf = io.BytesIO()
        pg = writer.pages[assignee_page]
        c = canvas.Canvas(buf, pagesize=(float(pg.mediabox.width), float(pg.mediabox.height)))
        c.setFont("Helvetica", 9)
        c.drawString(x0 + 2, y0 + (y1 - y0 - 9) / 2 + 2, config["company"]["name"])
        c.save()
        buf.seek(0)
        pg.merge_page(PdfReader(buf).pages[0])

    with open(out_pdf, "wb") as f:
        writer.write(f)
    return out_pdf


def read_back(pdf_path):
    """Field values from a filled T&C, plus which payee box is checked (for checks/tests)."""
    r = PdfReader(pdf_path)
    f = r.get_fields() or {}
    vals = {k: (v.get("/V") if not str(v.get("/V", "")).startswith("/") else str(v.get("/V"))) for k, v in f.items()}
    payee = next((k for k, box in PAYEE_BOX.items() if str(f.get(box, {}).get("/V")) == "/On"), None)
    return vals, payee
