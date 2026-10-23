"""The BGE Retrofit Lighting Worksheet, tool version 07212025: where inputs go, what the lists are.

Two jobs:
  1. CELL MAP - the input cells the bot writes, pinned to one tool version. verify()
     checks header labels at known cells so a new BGE version fails loudly instead
     of writing into the wrong cells.
  2. extract() - pull the lookup tables (measure codes, rates, dropdown lists,
     rated-wattage table) out of a blank template into references/template_tables.json.
     Re-run whenever BGE issues a new tool version.
"""

import json
import os

from . import REFERENCES_DIR
from ._xlsx import get_column_letter, grid, load

TOOL_VERSION = "07212025"
TABLES_PATH = os.path.join(REFERENCES_DIR, "template_tables.json")

PI = "Project Information"
LI = "Lighting Inventory"
MCST = "Measure Codes Summary Table"

PROJECT_CELLS = {
    "name": "D9", "address": "D10", "city": "D11", "zip": "D12",
    "building_type": "F10", "heating_fuel": "F12",
    "company": "D15", "contact": "D16", "phone": "D17", "email": "D18",
}

# Model table: M-00 (row 21) is BGE's own example row and is left alone. M-01 starts at 22.
MODEL_FIRST_ROW, MODEL_LAST_ROW = 22, 120
MODEL_COLS = {
    "dlc_id": "C", "model": "D", "lumens": "E", "watts": "F", "efficacy": "G",
    "primary_use": "H", "category": "I", "manufacturer": "J",
}

LINE_FIRST_ROW, LINE_LAST_ROW = 26, 1025
LINE_COLS = {
    "area": "C", "int_ext": "D", "ext_zone": "E", "daylight_qty": "F", "space_type": "G",
    "space_dim": "H", "over_300": "I", "unit": "J", "existing_category": "K",
    "existing_code": "L", "existing_qty": "N", "measure_type": "O", "measure_desc": "P",
    "model_select": "S", "qty": "V", "units_per": "W", "incentive_structure": "AK",
    "control_type": "AN", "control_select": "AO", "other_control": "AQ", "control_qty": "AR",
    "control_mounting": "AS", "control_mfr": "AT", "control_model": "AU",
}
UTILITY_CELL = "BG20"   # on Lighting Inventory; the blank template ships set to "Pepco"

# NLC Details tab: one row per Advanced-Networked-Controls line, in Lighting Inventory order
# (the tab's array formulas pull those lines into F23:I1022; the bot fills the inputs beside them).
NLC = "NLC Details"
NLC_FIRST_ROW, NLC_LAST_ROW = 23, 1022
NLC_COLS = {"occupancy": "J", "secondary": "K", "description": "L"}
NLC_SECONDARY = ["Daylight Harvesting", "Trim", "Zoning", "Peak Demand Control", "Other"]

# Formula outputs read back after Excel has recalculated the workbook.
LINE_OUTPUTS = {
    "measure_code": "R", "installed_units": "AA", "incentivized_units": "AB",
    "hours": "AM", "control_code": "AP", "control_units": "AX",
    "lighting_incentive": "AY", "control_incentive": "AZ", "line_incentive": "BA",
}
TOTAL_CELLS = {"incentive": "L99", "kwh": "L100", "kw": "L101", "lighting": "L67", "controls": "L86"}

HEADER_CHECKS = [
    (PI, "B6", "Tool Version # " + TOOL_VERSION),
    (PI, "C9", "Project Name"),
    (PI, "C12", "ZIP"),
    (PI, "B20", "Model ID"),
    (PI, "D20", "Model Number"),
    (PI, "B22", "M-01"),
    (LI, "C23", "Location"),
    (LI, "N23", "Existing Device Quantity"),
    (LI, "V23", "Proposed LED Device"),
    (LI, "AN23", "Control Type"),
    (LI, "AR23", "Quantity of"),
    (LI, "B26", "L1"),
    (NLC, "F22", "Line"),
    (NLC, "J22", "Occupancy/Vacancy"),
    (NLC, "K22", "Secondary Control Strategy"),
    (MCST, "E99", "Total Requested Incentive"),
    (MCST, "E100", "Total Estimated kWh Savings"),
]

MOUNTINGS = ["Ceiling or Corner Mount", "Wall Switch", "Fixture Mounted"]
INT_EXT = ["Interior - Open", "Interior - Enclosed", "Exterior"]
UTILITIES = ["BGE", "SMECO", "Pepco", "Delmarva"]


class TemplateMismatch(Exception):
    pass


def verify(template_path):
    """Raise TemplateMismatch if this isn't tool version 07212025 laid out as mapped."""
    wb = load(template_path, values=True)
    problems = []
    by_sheet = {}
    for sheet, cell, _ in HEADER_CHECKS:
        by_sheet.setdefault(sheet, []).append(cell)
    seen = {}
    for sheet, cells in by_sheet.items():
        if sheet not in wb.sheetnames:
            problems.append(f"missing sheet {sheet!r}")
            continue
        rows = [int("".join(ch for ch in c if ch.isdigit())) for c in cells]
        seen[sheet] = grid(wb[sheet], min(rows), max(rows), 60)
    for sheet, cell, expected in HEADER_CHECKS:
        got = seen.get(sheet, {}).get(cell)
        if not isinstance(got, str) or not got.strip().startswith(expected):
            problems.append(f"{sheet}!{cell}: expected {expected!r}, found {got!r}")
    wb.close()
    if problems:
        raise TemplateMismatch(
            "This workbook doesn't match the pinned BGE tool version "
            f"{TOOL_VERSION}:\n  " + "\n  ".join(problems)
        )


def _col(g, letter, r0, r1):
    return [g.get(f"{letter}{r}") for r in range(r0, r1 + 1)]


def extract(template_path):
    """Read lookup tables from a blank template. Returns the tables dict."""
    verify(template_path)
    wb = load(template_path, values=True)

    m = grid(wb[MCST], 13, 85, 12)
    v = grid(wb["Validation"], 1, 240, 52)
    w = wb["Wattage Table"]
    lt = grid(wb["Lookups TRM"], 4, 15, 5)

    # Measure type -> descriptions (dropdown P depends on O)
    letters = ["O", "P", "Q", "R", "S", "T", "U", "V", "W"]
    led_types = [v.get(f"{L}11") for L in letters]
    counts = [v.get(f"{L}1") for L in letters]
    desc_type = {}
    for L, t, n in zip(letters, led_types, counts):
        for r in range(12, 12 + int(n or 0)):
            d = v.get(f"{L}{r}")
            if isinstance(d, str) and d.strip():
                desc_type[d] = t

    desc_code = {}
    for r in range(7, 46):
        d, c = v.get(f"Y{r}"), v.get(f"Z{r}")
        if isinstance(d, str) and d.strip() and c:
            desc_code[d] = c
    unit = {}
    for r in range(23, 61):
        c = v.get(f"V{r}")
        if c:
            unit[c] = (v.get(f"W{r}"), v.get(f"X{r}"))

    measures = {}
    for r in range(13, 67):
        code = m.get(f"C{r}")
        if not (isinstance(code, str) and code.startswith("RL")):
            continue
        desc = next((d for d, c in desc_code.items() if c == code), None)
        u = unit.get(code, (None, None))
        measures[code] = {
            "type": desc_type.get(desc),
            "description": desc,
            "summary_description": m.get(f"D{r}"),
            "min_watts_reduced": m.get(f"E{r}"),
            "min_efficacy": m.get(f"F{r}"),
            "rate": m.get(f"H{r}"),
            "unit": u[0],
            "multi": u[1] == "Multi",
        }

    control_types = [v.get(f"C{r}") for r in range(63, 68)]
    ctrl_letters = ["E", "F", "G", "H", "I"]
    ctrl_counts = [v.get(f"{L}62") for L in ctrl_letters]
    select_type = {}
    control_selects = {}
    for L, t, n in zip(ctrl_letters, control_types, ctrl_counts):
        opts = []
        for r in range(64, 64 + int(n or 0)):
            s = v.get(f"{L}{r}")
            if isinstance(s, str) and s.strip() and not s.isupper():
                opts.append(s)
                select_type[s] = t
        control_selects[t] = opts

    min_watts = {lt.get(f"C{r}"): lt.get(f"E{r}") for r in range(4, 16) if lt.get(f"C{r}")}
    controls = {}
    for r in range(71, 86):
        code = m.get(f"C{r}")
        if not (isinstance(code, str) and code.startswith("LC")):
            continue
        sel = m.get(f"D{r}")
        controls[code] = {
            "select": sel,
            "type": select_type.get(sel),
            "selectable": sel in select_type,
            "min_watts": min_watts.get(code, m.get(f"E{r}")),
            "cap_ceiling": m.get(f"F{r}"),
            "cap_wall": m.get(f"G{r}"),
            "rate": m.get(f"I{r}"),
        }

    # Existing device categories (row 154) and their codes (rows 155-233), dropdown K -> L
    device_categories = {}
    for ci in range(2, 45):
        L = get_column_letter(ci)
        cat = v.get(f"{L}154")
        if not cat:
            continue
        codes = [v.get(f"{L}{r}") for r in range(155, 234)]
        device_categories[cat] = [c for c in codes if c]

    wattage = {}
    for row in w.iter_rows(min_row=16, max_row=620, max_col=9, values_only=True):
        code = row[2]
        if not code:
            continue
        wattage[str(code)] = {
            "category": row[1], "description": (row[3] or "").strip(), "watts": row[4],
            "lamps": row[5], "length": row[6], "lamp_watts": row[8],
        }

    tables = {
        "tool_version": TOOL_VERSION,
        "source": os.path.basename(template_path),
        "measures": measures,
        "controls": controls,
        "control_types": control_types,
        "control_selects": control_selects,
        "other_controls": [v.get(f"F{r}") for r in range(45, 48)],
        "device_categories": device_categories,
        "wattage": wattage,
        "space_types": [x for x in _col(v, "AC", 6, 104) if x],
        "ext_space_types": [x for x in _col(v, "AF", 6, 23) if x],
        "ext_zones": [v.get(f"{L}4") for L in ("AG", "AH", "AI", "AJ")],
        "building_types": [x for x in _col(v, "I", 6, 18) if x],
        "heating_fuels": [x for x in _col(v, "AZ", 4, 8) if x],
        "occupancy_required_spaces": [x for x in _col(v, "AP", 4, 17) if x],
        "no_control_required_spaces": [v.get("AC36")],
        "mountings": MOUNTINGS,
        "int_ext": INT_EXT,
        "utilities": UTILITIES,
    }
    wb.close()
    return tables


def load_tables(path=TABLES_PATH):
    """The lookup tables. They're derived from BGE's workbook, so they aren't committed:
    the first call extracts them from the local blank template (templates/bge/ or BGE_TEMPLATE)."""
    if not os.path.exists(path):
        import glob
        tmpl = os.environ.get("BGE_TEMPLATE") or next(iter(sorted(glob.glob(
            os.path.join(os.path.dirname(REFERENCES_DIR), "templates", "bge", "*.xlsm")))), None)
        if not tmpl or not os.path.exists(tmpl):
            raise FileNotFoundError(
                "references/template_tables.json is missing and there's no blank BGE workbook to build it from. "
                "Put the blank workbook in kce-prescriptive/templates/bge/ (or set BGE_TEMPLATE).")
        write_tables(extract(tmpl), path)
    with open(path) as f:
        return json.load(f)


def write_tables(tables, path=TABLES_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(tables, f, indent=1, sort_keys=False)
        f.write("\n")
    return path
