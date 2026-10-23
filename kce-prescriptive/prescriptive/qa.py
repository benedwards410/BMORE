"""QA gate. Every rule traces to a real miss (see references/qa-rules.md).

check() returns findings: {"level", "rule", "line", "message", "fix"}.
BLOCKER = the package must not be submitted as-is. WARN = a person should look.
INFO = recorded for the file. ASK = only the user can answer.
"""

import os
import re

from . import CATALOG_DIR

BLOCKER, WARN, ASK, INFO = "BLOCKER", "WARN", "ASK", "INFO"

AMBIGUOUS_AREA = re.compile(r"\b(dock|canopy|garage|parking|carport|exterior|outside|outdoor|patio|porch|breezeway)\b", re.I)
HIGH_BAY = re.compile(r"^RL 14[1-5]$")


def _f(level, rule, message, fix=None, line=None):
    return {"level": level, "rule": rule, "line": line, "message": message, "fix": fix}


def check(project, resolved, est, tables, rules, catalog, config):
    out = []
    p = project["project"]
    kce_domain = (config["company"].get("email_domain") or "").lower()

    # ---- Rule 7: one project identity, customer-of-record facts ---------------
    for key, label in [("customer_of_record", "Customer of record (BGE account holder)"),
                       ("site_address", "Site street address"), ("city", "City"), ("zip", "ZIP")]:
        if not p.get(key):
            out.append(_f(BLOCKER, 7, f"{label} is blank.", "Fill project.%s in project.json." % key))
    if p.get("zip") and not re.fullmatch(r"\d{5}", str(p["zip"])):
        out.append(_f(BLOCKER, 7, f"ZIP {p['zip']!r} isn't 5 digits."))
    if not p.get("bge_account"):
        out.append(_f(BLOCKER, 7, "BGE electric account number is blank. It's item 1 on BGE's application checklist and goes on the T&C.",
                      "Get it from page 1 of the customer's BGE bill."))
    if p.get("building_type") not in tables["building_types"]:
        out.append(_f(BLOCKER, 7, f"Building type {p.get('building_type')!r} isn't one of BGE's: {', '.join(tables['building_types'])}."))
    if p.get("heating_fuel") not in tables["heating_fuels"]:
        out.append(_f(BLOCKER, 7, f"Heating fuel {p.get('heating_fuel')!r} isn't one of BGE's: {', '.join(tables['heating_fuels'])}.",
                      "The workbook needs it on Project Information F12."))
    cc = project.get("customer_contact") or {}
    if not cc.get("name"):
        out.append(_f(BLOCKER, 7, "Customer's authorized representative (name/title/email/phone) is blank. The T&C must be signed by the BGE customer of record."))
    email = (cc.get("email") or "").lower()
    if kce_domain and email.endswith("@" + kce_domain):
        out.append(_f(BLOCKER, 7, f"The customer's authorized representative email is a KCE address ({email}). BGE needs the customer of record to sign the T&C, not KCE.",
                      "Put the customer's own contact in customer_contact."))
    sub = project.get("submitter") or {}
    missing_sub = [k for k in ("company", "contact", "phone", "email") if not sub.get(k)]
    if missing_sub:
        out.append(_f(BLOCKER, 7, f"Workbook submitter {', '.join(missing_sub)} not set (Project Information D15-D18).",
                      "Set workbook_submitter in config/kce.local.json."))
    if project.get("payee") not in ("contractor", "customer", "third_party"):
        out.append(_f(BLOCKER, 7, f"payee must be 'contractor', 'third_party' or 'customer', not {project.get('payee')!r}."))
    if project.get("utility") != "BGE":
        out.append(_f(WARN, 7, f"Utility is set to {project.get('utility')!r}. This bot is built for BGE."))
    out.append(_f(INFO, 7, "Workbook Utility cell (Lighting Inventory BG20) is set to BGE. The blank template ships set to 'Pepco'."))

    # ---- Per line ---------------------------------------------------------------
    used_products, used_controls = {}, {}
    all_daylight = []
    for r, e in zip(resolved, est["lines"]):
        lid = r["id"]
        for prob in r["problems"]:
            out.append(_f(BLOCKER, 6, prob, line=lid))
        fx = r.get("fixture")
        if fx:
            used_products[r["product"]] = fx
        if r.get("control_product"):
            used_controls[r["control"]] = r["control_product"]

        # Rule 1: counts
        q, xq = r.get("qty"), r.get("existing_qty")
        if not q:
            out.append(_f(BLOCKER, 1, "Proposed quantity is 0 or blank.", line=lid))
        if not xq:
            out.append(_f(BLOCKER, 1, "Existing quantity is 0 or blank.", line=lid))
        if q and xq and q > xq:
            out.append(_f(BLOCKER, 1, f"{q} new fixtures for {xq} existing: over one-for-one. BGE needs written authorization first.", line=lid))
        if q and xq and q < xq:
            out.append(_f(WARN, 1, f"{q} new for {xq} existing: check that the removed fixtures are accounted for.", line=lid))

        # Rule 5: existing code
        code = r.get("existing_code")
        cat = r.get("existing_category")
        if not code or code not in tables["wattage"]:
            out.append(_f(BLOCKER, 5, f"Existing device code {code!r} isn't on the template's Wattage Table.", line=lid))
        elif cat not in tables["device_categories"] or code not in tables["device_categories"][cat]:
            out.append(_f(BLOCKER, 5, f"Existing code {code} isn't in the {cat!r} dropdown list.", line=lid))

        # Space / int-ext
        if r.get("int_ext") not in tables["int_ext"]:
            out.append(_f(BLOCKER, 9, f"Interior/Exterior {r.get('int_ext')!r} must be one of {tables['int_ext']}.", line=lid))
        allowed = tables["ext_space_types"] if r.get("int_ext") == "Exterior" else tables["space_types"]
        if r.get("space_type") not in allowed:
            out.append(_f(BLOCKER, 9, f"Space type {r.get('space_type')!r} isn't in BGE's {'exterior' if r.get('int_ext') == 'Exterior' else 'interior'} list.", line=lid))
        if r.get("int_ext") == "Exterior" and r.get("ext_zone") not in tables["ext_zones"]:
            out.append(_f(WARN, 9, "Exterior line has no lighting zone (workbook column E). BGE's form asks for it; it doesn't change the incentive.", line=lid))
        if r.get("int_ext") != "Exterior" and r.get("over_300") not in ("Yes", "No"):
            out.append(_f(BLOCKER, 9, "Say whether the space is over 300 sq ft (Yes/No). It decides whether an occupancy sensor is required.", line=lid))
        area = r.get("area") or ""
        if AMBIGUOUS_AREA.search(area) and not (r["src"].get("int_ext_confirmed")):
            out.append(_f(ASK, 9, f"'{area}' could be interior or exterior; it's entered as {r.get('int_ext')!r}. That changes the measure code and the control rules.",
                          "Confirm, then set int_ext_confirmed: true on the line.", line=lid))

        # Rules 2-4: measure vs product
        meas = r.get("measure")
        mr = rules["measures"].get(meas or "")
        if fx and mr:
            if mr["qpl"] == "DLC":
                if fx.get("primary_use") is None:
                    out.append(_f(WARN, 2, f"{fx['model']}: DLC primary use not in catalog, so the measure fit can't be checked.", line=lid))
                elif mr["primary_use"] and fx["primary_use"] not in mr["primary_use"]:
                    out.append(_f(BLOCKER, 2, f"{fx['model']} is DLC '{fx['primary_use']}', which doesn't qualify for {meas} (needs one of: {'; '.join(mr['primary_use'])}).",
                                  "Use the measure that matches the product, or the product that matches the work.", line=lid))
                if fx.get("dlc_category") and mr["dlc_category"] and fx["dlc_category"] not in mr["dlc_category"]:
                    out.append(_f(BLOCKER, 2, f"{fx['model']} is DLC category '{fx['dlc_category']}'; {meas} needs {mr['dlc_category']}.", line=lid))
            if mr["qpl"] == "ENERGY STAR" and fx.get("dlc_category") not in (None, "ENERGY STAR"):
                out.append(_f(BLOCKER, 2, f"{meas} is an ENERGY STAR measure but {fx['model']} is listed as {fx['dlc_category']}.", line=lid))
            band = mr.get("lumens")
            if band and fx.get("lumens") is not None:
                lo, hi = band
                if (lo is not None and fx["lumens"] < lo) or (hi is not None and fx["lumens"] > hi):
                    out.append(_f(BLOCKER, 3, f"{fx['model']} reports {fx['lumens']:,} lm, outside {meas}'s band ({lo or 0:,}-{hi or 'up':} lm).", line=lid))
            if HIGH_BAY.match(meas or ""):
                h = r.get("mount_height_ft")
                if h is None:
                    out.append(_f(ASK, 3, f"{meas} needs fixtures mounted at least 15 ft above the floor. Mounting height isn't recorded.", line=lid))
                elif h < 15:
                    out.append(_f(BLOCKER, 3, f"{meas} needs 15 ft or higher; this line is {h} ft.", line=lid))
            if r.get("int_ext") == "Exterior" and fx.get("dlc_category") and not fx["dlc_category"].startswith("Outdoor") and fx["dlc_category"] != "ENERGY STAR":
                out.append(_f(WARN, 2, f"Indoor-listed product ({fx['dlc_category']}) on an exterior line.", line=lid))
            if r["src"].get("measure") and fx.get("measure") and r["src"]["measure"] != fx["measure"]:
                out.append(_f(WARN, 2, f"Line overrides the product's usual measure {fx['measure']} with {meas}.", line=lid))
        for reason in e["reasons"]:
            if reason.startswith("watts reduced") or reason.startswith("efficacy"):
                out.append(_f(BLOCKER, 4, reason + f" for {meas}.", line=lid))
            elif reason.startswith("space needs an occupancy"):
                out.append(_f(BLOCKER, 10, reason, "Add an occupancy-capable sensor, or confirm the space type.", line=lid))
            elif reason.startswith("exterior line has no"):
                out.append(_f(BLOCKER, 10, "Exterior fixtures need a working time clock or photocell to qualify (add one as the line's control).", line=lid))
            elif reason.startswith("control: NLC Details incomplete"):
                out.append(_f(BLOCKER, 10, reason[len("control: "):], "Set nlc.occupancy and nlc.secondary on the control in catalog/products.json.", line=lid))
            elif reason.startswith("control: DLC watts unknown"):
                pass    # the missing-DLC-data blocker already covers it
            elif reason.startswith("control:"):
                out.append(_f(WARN, 10, reason[len("control: "):], line=lid))

        # Rule 10: controls
        cq = r.get("control_qty") or 0
        if r.get("control_product") and q and cq > q:
            out.append(_f(WARN, 10, f"{cq} controls for {q} fixtures.", line=lid))
        if r.get("control_code") in {"LC 111", "LC 112", "LC 121", "LC 122"}:
            dq = r.get("daylight_qty") or 0
            if dq > (q or 0):
                out.append(_f(BLOCKER, 10, f"Daylight-zone fixtures ({dq}) exceed fixtures on the line ({q}).", line=lid))
            elif q and dq == q:
                all_daylight.append((lid, r["control_code"], q, e["control"]))
        if r.get("control_switched_low_watt"):
            out.append(_f(INFO, 10, f"Fixture is under the control's 20 W minimum, so the lower-wattage control code ({r['control_code']}) is used.", line=lid))
        if r.get("existing_controls") and r.get("control_code"):
            out.append(_f(WARN, 10, "Space already has controls: BGE pays no control incentive here.", line=lid))

        # Price
        if r.get("unit_price") is None:
            out.append(_f(BLOCKER, 12, f"No unit price for {r.get('product')} (installed, incl. sensor). The proposal can't be priced.", line=lid))

    if all_daylight:
        ids = [x[0] for x in all_daylight]
        codes = sorted({x[1] for x in all_daylight})
        at_stake = sum(x[3] for x in all_daylight)
        span = ids[0] if len(ids) == 1 else f"{ids[0]}-{ids[-1]}" if len(ids) == len(resolved) else ", ".join(ids)
        out.append(_f(ASK, 10, f"{'/'.join(codes)} pays only on fixtures inside the daylight zone, and {span} put every fixture "
                               f"({sum(x[2] for x in all_daylight)}) there. ${at_stake:,.0f} of the estimate rides on that.",
                      "Confirm which fixtures are near windows and set daylight_qty per line."))

    # ---- Rule 6: product data and cut sheets ---------------------------------------
    for pid, fx in used_products.items():
        missing = [k for k in ("dlc_id", "lumens", "watts", "efficacy") if fx.get(k) is None]
        if missing:
            out.append(_f(BLOCKER, 6, f"{fx['model']}: DLC {', '.join(missing)} not in the catalog. BGE needs the reported values exactly as listed.",
                          "Look the model up on the DLC QPL and fill catalog/products.json."))
        if not fx.get("manufacturer"):
            out.append(_f(WARN, 6, f"{fx['model']}: manufacturer blank (workbook column T)."))
        if not fx.get("cutsheet") or not os.path.exists(os.path.join(CATALOG_DIR, "cutsheets", fx["cutsheet"])):
            out.append(_f(BLOCKER, 6, f"No cut sheet on file for {fx['model']}. BGE requires cut sheets for every luminaire, kit and control.",
                          "Add the PDF to catalog/cutsheets/ and set 'cutsheet'."))
        if fx.get("field_watts") and fx.get("watts") and fx["field_watts"] != fx["watts"]:
            out.append(_f(INFO, 6, f"{fx['model']}: proposal savings use the {fx['field_watts']} W field setting; the BGE workbook uses the DLC-listed {fx['watts']} W."))
    for cid, cp in used_controls.items():
        if cp.get("control_type") == "Other Non-Incentivized Option":
            continue
        if not cp.get("cutsheet") or not os.path.exists(os.path.join(CATALOG_DIR, "cutsheets", cp["cutsheet"])):
            out.append(_f(BLOCKER, 6, f"No cut sheet on file for control {cp.get('manufacturer')} {cp.get('model')}."))
        if cp.get("control_type") == "Advanced Networked Controls" and not cp.get("dlc_id"):
            out.append(_f(WARN, 6, f"{cp.get('manufacturer')} {cp.get('model')}: LC 101/102 need a DLC NLC listing; none recorded."))

    # Exterior pole/flood -> extra BGE form
    for pid, fx in used_products.items():
        pu = fx.get("primary_use") or ""
        if "Pole/Arm" in pu or "Flood" in pu:
            out.append(_f(INFO, 13, f"{fx['model']} is pole/flood lighting: BGE needs the Exterior Circuit Verification Form. It's included in the package."))
            break

    # Rule 1: totals
    total_existing = sum(r.get("existing_qty") or 0 for r in resolved)
    total_new = sum(r.get("qty") or 0 for r in resolved)
    audit_total = project.get("audit_totals", {}).get("existing_qty")
    if audit_total is not None and audit_total != total_existing:
        out.append(_f(BLOCKER, 1, f"Audit lists {audit_total} existing fixtures; the project has {total_existing}. A room was dropped or doubled."))
    out.append(_f(INFO, 1, f"{len(resolved)} lines, {total_existing} existing fixtures, {total_new} new."))
    return out


def compare_identity(project, other, source_label):
    """Compare this project's identity/payee with another document's (an old workbook, a T&C)."""
    out = []
    p = project["project"]
    pairs = [("customer_of_record", "Customer / project name"), ("site_address", "Street address"),
             ("city", "City"), ("zip", "ZIP"), ("bge_account", "BGE account number")]
    for key, label in pairs:
        a, b = p.get(key), other.get(key)
        if b is None or a is None:
            continue
        if str(a).strip().lower() != str(b).strip().lower():
            out.append(_f(BLOCKER, 7, f"{label}: project says {a!r}, {source_label} says {b!r}."))
    if other.get("payee") and other["payee"] != project.get("payee"):
        out.append(_f(BLOCKER, 7, f"Payee: project says {project.get('payee')!r} (proposal wording follows this), {source_label} has {other['payee']!r} checked."))
    return out


def status(findings):
    if any(f["level"] == BLOCKER for f in findings):
        return "BLOCKED"
    if any(f["level"] == ASK for f in findings):
        return "NEEDS ANSWERS"
    return "READY"
