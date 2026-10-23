"""project.json: the one record every output is built from.

load() reads it and fills KCE defaults; resolve() turns each audit line into the
exact strings and numbers the BGE workbook needs (category/code, measure type and
description, model slot, control select), using the template tables and catalog.
Resolution never guesses: anything it can't determine is recorded on the line as
a problem for QA to report.
"""

import copy
import json
import os
import re

from . import CATALOG_DIR, CONFIG_DIR, REFERENCES_DIR
from .template_map import load_tables

SCHEMA = "kce-prescriptive/project@1"

LOWER_WATTAGE_SELECT = {
    "Networked lighting control": "Networked lighting control - lower wattage fixtures/downlights",
    "Dual daylight & occupancy sensor (DOS)  ": "Dual daylight & occupancy sensor (DOS) - lower wattage fixtures/downlights",
    "Daylight continuous dimming control ": "Daylight continuous dimming control - lower wattage fixtures/downlights",
    "Vacancy control ": "Vacancy control - lower wattage fixtures/downlights",
    "Occupancy control ": "Occupancy control - lower wattage fixtures/downlights",
}


def _read(path):
    with open(path) as f:
        return json.load(f)


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def load_config():
    """config/kce.json (committed defaults) overlaid with config/kce.local.json (gitignored:
    submitter contact, prices, anything KCE-internal)."""
    cfg = _read(os.path.join(CONFIG_DIR, "kce.json"))
    local = os.path.join(CONFIG_DIR, "kce.local.json")
    if os.path.exists(local):
        _merge(cfg, _read(local))
    return cfg


def load_catalog(path=None):
    return _read(path or os.path.join(CATALOG_DIR, "products.json"))


def load_existing():
    return _read(os.path.join(REFERENCES_DIR, "existing_fixtures.json"))


def load_measure_rules():
    return _read(os.path.join(REFERENCES_DIR, "measure_rules.json"))


def slug(text):
    s = re.sub(r"[^A-Za-z0-9]+", "_", text or "project").strip("_")
    return s[:60] or "project"


def load(path_or_dict, config=None):
    """Project dict with defaults applied. Accepts a path or an already-loaded dict."""
    p = copy.deepcopy(path_or_dict) if isinstance(path_or_dict, dict) else _read(path_or_dict)
    cfg = config or load_config()
    p.setdefault("schema", SCHEMA)
    p.setdefault("project", {})
    p["project"].setdefault("state", "MD")
    p.setdefault("customer_contact", {})
    p.setdefault("submitter", dict(cfg["workbook_submitter"]))
    p.setdefault("payee", cfg.get("payee_default", "contractor"))
    p.setdefault("utility", cfg.get("utility", "BGE"))
    pricing = dict(cfg["pricing"])
    pricing.update(p.get("pricing") or {})
    p["pricing"] = pricing
    savings = copy.deepcopy(cfg["savings"])
    for k, v in (p.get("savings") or {}).items():
        if isinstance(v, dict):
            savings.setdefault(k, {}).update(v)
        else:
            savings[k] = v
    p["savings"] = savings
    p.setdefault("lines", [])
    for i, ln in enumerate(p["lines"], start=1):
        ln.setdefault("id", f"L{i}")
    return p


def _measure_for_lumens(fixture, rules, family):
    """Pick RL 14x/15x/17x by DLC lumens when the catalog leaves measure open."""
    lm = fixture.get("lumens")
    if lm is None:
        return None
    for code, r in rules["measures"].items():
        if not code.startswith(family) or "lumens" not in r:
            continue
        lo, hi = r["lumens"]
        if (lo is None or lm >= lo) and (hi is None or lm <= hi):
            return code
    return None


def resolve(project, tables=None, catalog=None, existing=None, rules=None, prices=None):
    """Returns (resolved_lines, models). Each resolved line carries 'problems': [str].
    prices: {product id: installed price incl. sensor}, normally config 'prices' (kce.local.json)."""
    prices = prices if prices is not None else load_config().get("prices", {})
    tables = tables or load_tables()
    catalog = catalog or load_catalog()
    existing = existing or load_existing()
    rules = rules or load_measure_rules()

    models = []          # ordered distinct fixture products -> M-01, M-02, ...
    model_index = {}
    out = []
    for ln in project["lines"]:
        r = {"id": ln["id"], "src": ln, "problems": []}
        r["area"] = ln.get("area")
        r["int_ext"] = ln.get("int_ext")
        r["space_type"] = ln.get("space_type")
        r["over_300"] = ln.get("over_300")
        r["space_dim"] = ln.get("space_dim")
        r["ext_zone"] = ln.get("ext_zone")
        r["existing_qty"] = ln.get("existing_qty")
        r["qty"] = ln.get("qty", ln.get("existing_qty"))
        r["daylight_qty"] = ln.get("daylight_qty", 0) or 0
        r["existing_controls"] = bool(ln.get("existing_controls"))
        r["mount_height_ft"] = ln.get("mount_height_ft")

        # Existing fixture -> BGE category + code
        ex = existing["fixtures"].get(ln.get("existing")) if ln.get("existing") else None
        code = ln.get("existing_code") or (ex or {}).get("code")
        r["existing_code"] = code
        r["existing_label"] = (ex or {}).get("label") or ln.get("existing_label") or code
        r["existing_lamps"] = (ex or {}).get("lamps", 0)
        r["existing_ballasts"] = (ex or {}).get("ballasts", 0)
        r["existing_fluorescent"] = (ex or {}).get("fluorescent", False)
        w = tables["wattage"].get(code) if code else None
        if ln.get("existing") and not ex:
            r["problems"].append(f"existing fixture {ln['existing']!r} isn't in references/existing_fixtures.json")
        r["existing_category"] = (ex or {}).get("category") or (w or {}).get("category")
        r["existing_watts"] = (w or {}).get("watts")

        # Proposed fixture -> model slot + measure
        fx = catalog["fixtures"].get(ln.get("product"))
        r["product"] = ln.get("product")
        r["fixture"] = fx
        if not fx:
            r["problems"].append(f"product {ln.get('product')!r} isn't in catalog/products.json")
        else:
            if r["product"] not in model_index:
                models.append(r["product"])
                model_index[r["product"]] = len(models)
            r["model_id"] = f"M-{model_index[r['product']]:02d}"
        measure = ln.get("measure") or (fx or {}).get("measure")
        if fx and not measure:
            pu = (fx.get("primary_use") or "").lower()
            fam = "RL 14" if "bay" in pu else "RL 15" if (fx.get("dlc_category") or "").startswith("Outdoor") else None
            measure = _measure_for_lumens(fx, rules, fam) if fam else None
            if not measure:
                r["problems"].append(f"{fx['model']}: no measure code; it depends on DLC lumens, which aren't in the catalog yet")
        r["measure"] = measure
        m = tables["measures"].get(measure) if measure else None
        if measure and not m:
            r["problems"].append(f"measure {measure!r} isn't in the template's Measure Codes table")
        r["measure_type"] = (m or {}).get("type")
        r["measure_desc"] = (m or {}).get("description")
        r["multi"] = bool((m or {}).get("multi"))
        r["units_per"] = (ln.get("ft_per_fixture") or (fx or {}).get("ft_per_fixture")) if r["multi"] else None
        r["unit_price"] = ln.get("unit_price", prices.get(r["product"], (fx or {}).get("unit_price")))

        # Control
        cp_id = ln.get("control")
        cp = catalog["controls"].get(cp_id) if cp_id else None
        r["control"] = cp_id
        r["control_product"] = cp
        if cp_id and not cp:
            r["problems"].append(f"control {cp_id!r} isn't in catalog/products.json")
        r["control_qty"] = ln.get("control_qty", r["qty"] if cp else 0) if cp else 0
        r["control_type"] = (cp or {}).get("control_type")
        sel = (cp or {}).get("control_select")
        r["control_switched_low_watt"] = False
        if sel and fx and fx.get("watts") is not None:
            code_for = next((c for c, d in tables["controls"].items() if d["select"] == sel), None)
            minw = tables["controls"].get(code_for, {}).get("min_watts") or 0
            if fx["watts"] < minw and sel in LOWER_WATTAGE_SELECT:
                sel = LOWER_WATTAGE_SELECT[sel]
                r["control_switched_low_watt"] = True
        r["control_select"] = sel
        r["other_control"] = (cp or {}).get("other_control")
        r["control_mounting"] = ln.get("control_mounting") or (cp or {}).get("mounting")
        r["control_code"] = next((c for c, d in tables["controls"].items() if d["select"] == sel), None) if sel else None
        out.append(r)
    return out, models


def model_rows(models, catalog=None):
    """[(model id, fixture dict)] in slot order."""
    catalog = catalog or load_catalog()
    return [(f"M-{i:02d}", catalog["fixtures"][pid]) for i, pid in enumerate(models, start=1)]
