"""Turn a resolved project into BGE workbook cell edits, and write the .xlsm."""

from . import template_map as tm
from .xlsm_writer import IfNotFormula, write


def display_name(project):
    p = project["project"]
    return p.get("name") or " - ".join(x for x in (p.get("customer_of_record"), street(project)) if x)


def street(project):
    p = project["project"]
    return ", ".join(x for x in (p.get("site_address"), p.get("suite")) if x)


def _zip(z):
    z = str(z or "").strip()
    return int(z) if z.isdigit() and not z.startswith("0") else (z or None)


ATRIUMS = ("Atrium- (Less than 40 ft height)", "Atrium- (Greater than 40 ft height)")


def _unit(r):
    """Column J, for the template rows (26-28) that lost BGE's own formula; same logic as that formula."""
    if r.get("space_type") in ATRIUMS:
        return "Height in Feet"
    if r.get("int_ext") in ("Interior - Enclosed", "Interior - Open"):
        return "Square Feet"
    return None


def edits(project, resolved, models, catalog):
    p = project["project"]
    sub = project["submitter"]
    pi = {
        tm.PROJECT_CELLS["name"]: display_name(project),
        tm.PROJECT_CELLS["address"]: street(project),
        tm.PROJECT_CELLS["city"]: p.get("city"),
        tm.PROJECT_CELLS["zip"]: _zip(p.get("zip")),
        tm.PROJECT_CELLS["building_type"]: p.get("building_type"),
        tm.PROJECT_CELLS["heating_fuel"]: p.get("heating_fuel"),
        tm.PROJECT_CELLS["company"]: sub.get("company"),
        tm.PROJECT_CELLS["contact"]: sub.get("contact"),
        tm.PROJECT_CELLS["phone"]: sub.get("phone"),
        tm.PROJECT_CELLS["email"]: sub.get("email"),
    }
    if len(models) > tm.MODEL_LAST_ROW - tm.MODEL_FIRST_ROW + 1:
        raise ValueError("more than 99 distinct products")
    for i, pid in enumerate(models):
        fx = catalog["fixtures"][pid]
        row = tm.MODEL_FIRST_ROW + i
        cat = fx.get("dlc_category")
        vals = {
            "dlc_id": fx.get("dlc_id"), "model": fx["model"], "lumens": fx.get("lumens"),
            "watts": fx.get("watts"), "efficacy": fx.get("efficacy"),
            "primary_use": fx.get("primary_use"),
            "category": None if cat == "ENERGY STAR" else cat,
            "manufacturer": fx.get("manufacturer"),
        }
        for k, col in tm.MODEL_COLS.items():
            pi[f"{col}{row}"] = vals[k]

    li = {tm.UTILITY_CELL: project.get("utility", "BGE")}
    if len(resolved) > tm.LINE_LAST_ROW - tm.LINE_FIRST_ROW + 1:
        raise ValueError("more than 1000 lines")
    for i, r in enumerate(resolved):
        row = tm.LINE_FIRST_ROW + i
        fx = r.get("fixture") or {}
        cp = r.get("control_product") or {}
        vals = {
            "area": r.get("area"),
            "int_ext": r.get("int_ext"),
            "ext_zone": r.get("ext_zone") if r.get("int_ext") == "Exterior" else None,
            "daylight_qty": r.get("daylight_qty") or 0,
            "space_type": r.get("space_type"),
            "space_dim": r.get("space_dim"),
            "over_300": r.get("over_300"),
            "unit": IfNotFormula(_unit(r)),
            "existing_category": r.get("existing_category"),
            "existing_code": r.get("existing_code"),
            "existing_qty": r.get("existing_qty"),
            "measure_type": r.get("measure_type"),
            "measure_desc": r.get("measure_desc"),
            "model_select": f"  {r['model_id']}  {fx['model']}" if r.get("model_id") else None,
            "qty": r.get("qty"),
            "units_per": r.get("units_per"),
            "control_type": r.get("control_type"),
            "control_select": r.get("control_select"),
            "other_control": r.get("other_control"),
            "control_qty": r.get("control_qty") if r.get("control_product") else None,
            "control_mounting": r.get("control_mounting") if r.get("control_product") else None,
            "control_mfr": cp.get("manufacturer"),
            "control_model": cp.get("model"),
        }
        for k, col in tm.LINE_COLS.items():
            if k == "incentive_structure":
                continue        # template already says "Prescriptive"
            li[f"{col}{row}"] = vals[k]
    nlc = {}
    k = 0
    for r in resolved:
        if r.get("control_type") != "Advanced Networked Controls":
            continue
        info = (r.get("control_product") or {}).get("nlc") or {}
        row = tm.NLC_FIRST_ROW + k
        k += 1
        nlc[f"{tm.NLC_COLS['occupancy']}{row}"] = info.get("occupancy")
        nlc[f"{tm.NLC_COLS['secondary']}{row}"] = info.get("secondary")
        nlc[f"{tm.NLC_COLS['description']}{row}"] = info.get("description")
    out = {tm.PI: pi, tm.LI: li}
    if nlc:
        out[tm.NLC] = nlc
    return out


def build(template_path, out_path, project, resolved, models, catalog):
    tm.verify(template_path)
    write(template_path, out_path, edits(project, resolved, models, catalog),
          strip_sheets=(tm.PI, tm.LI, tm.MCST))
    return out_path
