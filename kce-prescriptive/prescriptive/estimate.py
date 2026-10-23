"""Incentive estimate per line, following the BGE workbook's own formulas.

Mirrors Lighting Inventory columns AA (installed units), AB (incentivized units),
AY (lighting $), AX/AZ (control units / $) for tool version 07212025, BGE utility.
Excel stays the calculator of record: readback compares this estimate with what
Excel computed and lists any line that differs.

kWh is NOT estimated here; it depends on the workbook's TRM hours-of-use tables.
"""

# Measures whose minimum watts reduced is per foot, and whose savings are per fixture.
FOOT_MEASURES = {"RL 111", "RL 111A", "RL 111B", "RL 121", "RL 167"}
# Control codes paid only on fixtures inside the daylight zone (Lighting Inventory col F).
DAYLIGHT_ZONE_CODES = {"LC 111", "LC 112", "LC 121", "LC 122"}
DAYLIGHT_TYPES = {"Daylight Controls", "Dual Daylight / Occupancy Controls"}
# Controls that satisfy the occupancy/vacancy requirement (workbook column AW).
OCCUPANCY_CODES = {"LC 101", "LC 102", "LC 103", "LC 104", "LC 111", "LC 112",
                   "LC 131", "LC 132", "LC 133", "LC 134"}


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _nlc_ok(r):
    """NLC Details column N: occupancy/vacancy Yes, a secondary strategy, and daylight
    harvesting only where the line has fixtures in the daylight zone."""
    info = (r.get("control_product") or {}).get("nlc") or {}
    if info.get("occupancy") != "Yes" or not info.get("secondary"):
        return False
    if info["secondary"] == "Daylight Harvesting" and (r.get("daylight_qty") or 0) < 1:
        return False
    return True


def line(r, tables):
    """Estimate for one resolved line. Returns a dict; 'reasons' explains any $0."""
    est = {"id": r["id"], "measure": r["measure"], "reasons": [], "lighting": 0, "control": 0}
    fx = r.get("fixture") or {}
    m = tables["measures"].get(r["measure"] or "")
    V = _num(r.get("qty")) or 0
    W = _num(r.get("units_per")) or 0
    Y = _num(fx.get("watts"))
    eff = _num(fx.get("efficacy"))
    ex_w = _num(r.get("existing_watts"))
    ex_q = _num(r.get("existing_qty")) or 0

    installed = V * W if r.get("multi") else V
    est["installed_units"] = installed
    est["existing_watts_total"] = ex_w * ex_q if ex_w is not None else None
    est["proposed_watts_total"] = (V * Y if r.get("multi") else installed * Y) if Y is not None else None
    est["rate"] = (m or {}).get("rate")
    est["unit"] = (m or {}).get("unit")

    ok = True
    if not m:
        est["reasons"].append("no measure code")
        ok = False
    if not r.get("space_type"):
        est["reasons"].append("space type is blank (workbook pays $0 without it)")
        ok = False
    if Y is None or eff is None:
        est["reasons"].append("DLC watts/efficacy not known")
        ok = False
    if ok:
        per = V if r["measure"] in FOOT_MEASURES else installed
        reduced = round((est["existing_watts_total"] - est["proposed_watts_total"]) / per) if per and est["existing_watts_total"] is not None else None
        need = (m["min_watts_reduced"] or 0) * (W if r["measure"] in FOOT_MEASURES else 1)
        est["watts_reduced_per_unit"] = reduced
        est["min_watts_reduced"] = need
        if reduced is None or reduced < need:
            est["reasons"].append(f"watts reduced {reduced} < required {need}")
            ok = False
        if m.get("min_efficacy") and round(eff) < m["min_efficacy"]:
            est["reasons"].append(f"efficacy {eff} < {m['min_efficacy']} lm/W")
            ok = False

    # AV: exterior fixtures need a time clock / photocell / control on the line
    exterior = r.get("int_ext") == "Exterior"
    if exterior and not (r.get("control_qty") or 0) > 0:
        est["reasons"].append("exterior line has no time clock/photocell/control (column AR)")
        ok = False
    # AW: occupancy/vacancy requirement
    space = r.get("space_type")
    exempt_spaces = set(tables.get("no_control_required_spaces") or [])
    if not exterior and space not in exempt_spaces:
        occ_spaces = {s.lower() for s in tables["occupancy_required_spaces"]}
        needs_occ = (space or "").lower() in occ_spaces or (
            r.get("int_ext") == "Interior - Enclosed" and r.get("over_300") != "Yes")
        if needs_occ:
            has = (r.get("control_code") in OCCUPANCY_CODES or r.get("other_control") == "Pre-existing control") and (r.get("control_qty") or 0) > 0
            est["occupancy_required"] = True
            if not has:
                est["reasons"].append("space needs an occupancy/vacancy control; none on this line, so BGE pays $0 for the fixtures")
                ok = False

    est["incentivized_units"] = installed if ok else 0
    est["lighting"] = (est["rate"] or 0) * est["incentivized_units"]

    # Controls (AX, AZ)
    code = r.get("control_code")
    c = tables["controls"].get(code) if code else None
    est["control_code"] = code
    est["control_units"] = 0
    if c and (r.get("control_qty") or 0) > 0:
        watts_per_fixture = (est["proposed_watts_total"] / V) if (est["proposed_watts_total"] is not None and V) else None
        if watts_per_fixture is None:
            est["reasons"].append("control: DLC watts unknown, so the control can't be checked")
        elif watts_per_fixture < (c["min_watts"] or 0):
            est["reasons"].append(f"control: fixture watts {watts_per_fixture} below {code} minimum {c['min_watts']}")
        elif exterior and r.get("control_type") in DAYLIGHT_TYPES:
            est["reasons"].append("control: exterior fixtures aren't eligible for daylight-control incentives")
        elif r.get("control_type") == "Advanced Networked Controls" and not _nlc_ok(r):
            est["reasons"].append("control: NLC Details incomplete (occupancy/vacancy = Yes plus a secondary strategy), so the workbook pays $0 for this control")
        elif r.get("existing_controls"):
            est["reasons"].append("control: space already has controls, so no control incentive (tech sheet)")
        else:
            units = (r.get("daylight_qty") or 0) if code in DAYLIGHT_ZONE_CODES else V
            est["control_units"] = units
            amount = units * (c["rate"] or 0)
            mount = r.get("control_mounting")
            ar = r.get("control_qty") or 0
            if mount in ("Wall Switch", "Wall/Surface-Mounted"):
                amount = min(c["cap_wall"] * ar, amount)
            elif mount == "Ceiling or Corner Mount":
                amount = min(c["cap_ceiling"] * ar, amount)
            est["control"] = amount
            if code in DAYLIGHT_ZONE_CODES and units == 0:
                est["reasons"].append(f"control: {code} pays only on fixtures in the daylight zone, and daylight_qty is 0")
    est["control_rate"] = (c or {}).get("rate")
    est["total"] = est["lighting"] + est["control"]
    return est


def project(resolved, tables):
    lines = [line(r, tables) for r in resolved]
    by_measure = {}
    for e in lines:
        if e["incentivized_units"]:
            b = by_measure.setdefault(e["measure"], {"units": 0, "amount": 0, "rate": e["rate"], "unit": e["unit"]})
            b["units"] += e["incentivized_units"]
            b["amount"] += e["lighting"]
        if e["control"]:
            b = by_measure.setdefault(e["control_code"], {"units": 0, "amount": 0, "rate": e["control_rate"], "unit": "fixture"})
            b["units"] += e["control_units"]
            b["amount"] += e["control"]
    lighting = sum(e["lighting"] for e in lines)
    controls = sum(e["control"] for e in lines)
    return {"lines": lines, "by_measure": by_measure, "lighting": lighting,
            "controls": controls, "total": lighting + controls}
