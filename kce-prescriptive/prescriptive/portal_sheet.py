"""Portal cheat sheet (HTML): every BGE Application Center field, in screen order, with the value to enter.

Screens and field labels follow the portal screenshots (hpwescontractor.customerapplication.com,
Lighting Application). Values marked ASK or ESTIMATE must be settled before submitting.
"""

import datetime as dt
import html

from .proposal import money

# BGE workbook building types -> portal radio buttons
PORTAL_BUILDING = {
    "Office": "Office", "Retail": "Retail", "School": "School", "University": "University",
    "Religious Facility": "Religious Facility", "Grocery": "Grocery", "Lodging": "Lodging",
    "Industrial": "Industrial", "Warehouse": "Warehouse", "Health Facilities": "Health Facility",
    "Multifamily": "Multifamily", "Restaurant": "Restaurant", "Other": "Other",
}
PAYABLE = {"customer": "Customer", "contractor": "Contractor", "third_party": "Third Party"}


def rows(project, config, est, files, readback=None):
    p = project["project"]
    cc = project.get("customer_contact") or {}
    co = config["company"]
    kce = project.get("payee", "contractor") != "customer"
    if readback and readback.get("ok"):
        inc = (money(readback["totals"]["incentive"]), "Excel: Measure Codes Summary Table L99")
        kwh = (f"{readback['totals']['kwh']:,.0f}", "Excel: Measure Codes Summary Table L100")
    else:
        inc = ("ESTIMATE " + money(est["total"]), "Bot estimate. Open the workbook in Excel, save, run readback, then use L99")
        kwh = ("ASK", "Only Excel computes this: open the workbook, save, run readback (L100)")

    def v(x, src, ask_if_blank=True):
        return (x if x not in (None, "") else ("ASK" if ask_if_blank else ""), src)

    bt = p.get("business_type") or []
    return [
        ("Savings and Incentive Information", [
            ("Total Requested Incentive", *inc),
            ("Total Estimated kWh Savings", *kwh),
        ]),
        ("Project Information", [
            ("Title of Utility Customer", *v(cc.get("title"), "customer_contact.title")),
            ("Application is being completed by", "Service Provider" if kce else "Customer", "KCE prepares and submits the application"),
            ("Application Date", dt.date.today().strftime("%m/%d/%Y"), "Today"),
            ("Is the premise company a National Account?", "Yes" if p.get("national_account") else "No", "project.national_account"),
            ("Installation Contractor - Retrofit Lighting", co.get("legal_name") or co["name"], "Pick KCE's service-provider listing"),
            ("Self-install: name of lead installer/electrician", "N/A", "An installation contractor is selected"),
            ("Installation Contractor - Sign Lighting", "N/A (no sign lighting)", "No sign lighting on this application"),
            ("Self-install (sign): name of lead installer/electrician", "N/A", ""),
            ("Business Type", ", ".join(bt) if bt else "None checked", "project.business_type (Minority-/Woman-/Veteran-owned)"),
            ("Business Sector", *v(p.get("business_sector"), "project.business_sector")),
            ("Building Type", PORTAL_BUILDING.get(p.get("building_type"), "ASK"), f"Workbook building type: {p.get('building_type')}"),
            ("If other, please specify", p.get("building_type_other") or "", ""),
            ("Square Footage By Application", *v(p.get("square_feet"), "project.square_feet")),
        ]),
        ("Payee Information", [
            ("Check Payable To", PAYABLE.get(project.get("payee", "contractor")), "Matches the T&C payment box"),
            ("Check Payable Name", co["name"] if kce else p.get("customer_of_record"), ""),
            ("Payee Contact Name", project["submitter"].get("contact") if kce else cc.get("name"), ""),
            ("Payee Address", co["street"] if kce else p.get("site_address"), ""),
            ("Address Continued", "" if kce else (p.get("suite") or ""), ""),
            ("Payee City", co["city"] if kce else p.get("city"), ""),
            ("Payee State", co["state"] if kce else p.get("state", "MD"), ""),
            ("Payee Zip Code", co["zip"] if kce else p.get("zip"), ""),
        ]),
        ("Document Upload", [
            ("Manufacturer's Cut Sheets", files.get("cutsheets") or "MISSING", "Cut-sheet bundle"),
            ("Retrofit Lighting Worksheet", files.get("workbook"), "Upload the copy you opened and saved in Excel"),
            ("Customer-signed Terms and Conditions", files.get("terms"), "BGE checklist item; email to Business@BGESmartEnergy.com if the portal has no slot"),
        ] + ([("Exterior Circuit Verification Form", files["exterior_form"], "Pole/flood lighting on this job")] if files.get("exterior_form") else [])),
    ]


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e3e3e0;--ask:#b42318;--askbg:#fef3f2;--est:#93370d;--estbg:#fffaeb;--accent:#1f3864}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121214;--card:#1c1c1f;--ink:#ececee;--mute:#9a9aa1;--line:#2c2c31;--ask:#f97066;--askbg:#2a1513;--est:#fdb022;--estbg:#2a2112;--accent:#9db4e8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;padding:24px 16px}
main{max-width:860px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--mute);margin:0 0 20px}
.status{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:600;font-size:13px;margin-bottom:16px}
.s-READY{background:#ecfdf3;color:#067647}.s-BLOCKED{background:var(--askbg);color:var(--ask)}.s-NEEDS{background:var(--estbg);color:var(--est)}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:16px;overflow:hidden}
section h2{font-size:14px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);margin:0;padding:12px 16px;border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.3fr) 64px;gap:12px;align-items:start;padding:10px 16px;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}.f{font-weight:500}.src{color:var(--mute);font-size:12.5px;grid-column:1/-1;margin-top:-6px}
.v{word-break:break-word;font-family:ui-monospace,Menlo,monospace;font-size:14px}.v.ask{color:var(--ask);font-weight:700}.v.est{color:var(--est);font-weight:700}
button{font:inherit;font-size:12.5px;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:6px;padding:3px 10px;cursor:pointer}
button:active{transform:translateY(1px)}
@media (max-width:560px){.row{grid-template-columns:1fr 64px}.f{grid-column:1/-1}}
"""


def build(out_html, project, config, est, files, status, readback=None):
    secs = rows(project, config, est, files, readback)
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>BGE Portal Sheet</title><style>{CSS}</style></head><body><main>",
             f"<h1>BGE portal: {html.escape(str(project['project'].get('name') or project['project'].get('customer_of_record') or ''))}</h1>",
             f"<p class='sub'>Lighting Application, field by field, in screen order. Built {dt.date.today():%b %d, %Y}. Values in red must be settled first.</p>",
             f"<span class='status s-{status.split()[0]}'>QA: {html.escape(status)}</span>"]
    for title, items in secs:
        parts.append(f"<section><h2>{html.escape(title)}</h2>")
        for field, value, src in items:
            sval = "" if value is None else str(value)
            cls = "ask" if sval.startswith("ASK") or sval == "MISSING" else "est" if sval.startswith("ESTIMATE") else ""
            copy = "" if cls == "ask" or not sval else f"<button onclick=\"navigator.clipboard.writeText(this.dataset.v)\" data-v=\"{html.escape(sval.replace('ESTIMATE ', ''))}\">Copy</button>"
            parts.append(f"<div class='row'><div class='f'>{html.escape(field)}</div><div class='v {cls}'>{html.escape(sval)}</div><div>{copy}</div>"
                         + (f"<div class='src'>{html.escape(src)}</div>" if src else "") + "</div>")
        parts.append("</section>")
    parts.append("</main></body></html>")
    with open(out_html, "w") as f:
        f.write("".join(parts))
    return out_html
