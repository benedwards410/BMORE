"""Read an existing BGE Retrofit Lighting Worksheet back into a project dict.

Used to (a) pick up a job someone started by hand, and (b) golden-test the bot
against workbooks that were already submitted. Products are matched to the
catalog by exact DLC model string; unmatched models are listed, never guessed.
"""

from ._xlsx import grid, load
from .project import load_catalog, load_existing
from .template_map import (LI, LINE_COLS, LINE_FIRST_ROW, LINE_LAST_ROW, MODEL_COLS,
                           MODEL_FIRST_ROW, MODEL_LAST_ROW, PI, PROJECT_CELLS, verify)


def _s(v):
    return v.strip() if isinstance(v, str) else v


def from_bge_workbook(path, model_map=None, control_map=None, catalog=None):
    """Returns (project dict, notes list)."""
    verify(path)
    catalog = catalog or load_catalog()
    existing = load_existing()
    model_map = model_map or {}
    control_map = control_map or {}
    notes = []

    wb = load(path, values=True)
    pi = grid(wb[PI], 9, MODEL_LAST_ROW, 12)
    li = grid(wb[LI], LINE_FIRST_ROW, LINE_LAST_ROW, 50)
    wb.close()

    proj = {k: pi.get(c) for k, c in PROJECT_CELLS.items()}
    models = {}
    for r in range(MODEL_FIRST_ROW, MODEL_LAST_ROW + 1):
        row = {k: pi.get(f"{c}{r}") for k, c in MODEL_COLS.items()}
        if row["model"]:
            models[f"M-{r - MODEL_FIRST_ROW + 1:02d}"] = row

    by_model = {fx["model"].strip(): pid for pid, fx in catalog["fixtures"].items()}
    by_code = {}
    for eid, ex in existing["fixtures"].items():
        by_code.setdefault(ex["code"], eid)
    by_ctrl = {((c.get("manufacturer") or "").lower(), (c.get("model") or "").lower()): cid
               for cid, c in catalog["controls"].items()}

    lines = []
    for r in range(LINE_FIRST_ROW, LINE_LAST_ROW + 1):
        g = {k: li.get(f"{c}{r}") for k, c in LINE_COLS.items()}
        if not g["area"] and not g["qty"]:
            continue
        sel = g["model_select"] or ""
        mid = sel.strip()[:4] if sel.strip().startswith("M-") else None
        model = models.get(mid, {}).get("model") if mid else None
        model = _s(model)
        pid = model_map.get(model) or by_model.get(model)
        if model and not pid:
            notes.append(f"line {li.get(f'B{r}')}: model {model!r} not in catalog")
        mfr, cmodel = _s(g["control_mfr"]) or "", _s(g["control_model"]) or ""
        cid = control_map.get((mfr, cmodel)) or by_ctrl.get((mfr.lower(), cmodel.lower()))
        if (mfr or cmodel) and not cid:
            notes.append(f"line {li.get(f'B{r}')}: control {mfr} {cmodel} not in catalog")
        code = _s(g["existing_code"])
        ln = {
            "id": li.get(f"B{r}"),
            "area": g["area"],
            "int_ext": g["int_ext"],
            "space_type": g["space_type"],
            "over_300": g["over_300"],
            "space_dim": g["space_dim"],
            "ext_zone": g["ext_zone"],
            "daylight_qty": g["daylight_qty"] or 0,
            "existing": by_code.get(code),
            "existing_qty": g["existing_qty"],
            "product": pid,
            "qty": g["qty"],
        }
        if not by_code.get(code):
            ln["existing_code"] = code
        if g["units_per"]:
            ln["ft_per_fixture"] = g["units_per"]
        if cid:
            ln["control"] = cid
            ln["control_qty"] = g["control_qty"]
            ln["control_mounting"] = g["control_mounting"]
        lines.append({k: v for k, v in ln.items() if v is not None})

    project = {
        "project": {
            "name": proj["name"], "site_address": proj["address"], "city": proj["city"],
            "zip": str(proj["zip"]) if proj["zip"] is not None else None,
            "building_type": proj["building_type"], "heating_fuel": proj["heating_fuel"],
        },
        "submitter": {"company": proj["company"], "contact": proj["contact"],
                      "phone": str(proj["phone"]) if proj["phone"] is not None else None,
                      "email": proj["email"]},
        "lines": lines,
    }
    return project, notes
