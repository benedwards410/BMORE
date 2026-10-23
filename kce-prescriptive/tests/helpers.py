"""Shared fixtures: a synthetic project (no customer data) and loaders."""

import copy
import unittest

from _path import PLUGIN  # noqa: F401

from prescriptive import estimate, qa
from prescriptive.project import load, load_catalog, load_config, load_existing, load_measure_rules, resolve
from prescriptive.template_map import load_tables

try:
    TABLES = load_tables()
except FileNotFoundError as e:   # no blank BGE workbook on this machine
    raise unittest.SkipTest(str(e))
CATALOG = load_catalog()
RULES = load_measure_rules()
CONFIG = load_config()
CONFIG["workbook_submitter"] = {"company": "Key Commercial Electric LLC", "contact": "Test Submitter",
                                "phone": "410-555-0199", "email": "submitter@example.com"}
CONFIG["prices"] = {}


def example_project(**over):
    p = {
        "project": {
            "customer_of_record": "Example Holdings LLC", "site_address": "100 Example Ave", "suite": "Suite 2",
            "city": "Columbia", "state": "MD", "zip": "21045", "bge_account": "1234567890",
            "building_type": "Office", "heating_fuel": "Gas", "square_feet": 5000,
        },
        "customer_contact": {"name": "Pat Example", "title": "Owner", "email": "pat@example.com", "phone": "410-555-0100"},
        "payee": "contractor",
        "lines": [
            {"area": "Open office", "int_ext": "Interior - Open", "space_type": "Office - Open Plan", "over_300": "Yes",
             "existing": "2x4-3L-F32T8", "existing_qty": 10, "product": "VEKT2X4-8T", "control": "IFS108", "daylight_qty": 4,
             "unit_price": 100},
            {"area": "Private office", "int_ext": "Interior - Enclosed", "space_type": "Office - Enclosed", "over_300": "No",
             "existing": "2x4-3L-F32T8", "existing_qty": 2, "product": "VEKT2X4-8T", "control": "SILVAIR-SHARKWARD",
             "unit_price": 100},
        ],
    }
    for k, v in over.items():
        p[k] = v
    return p


def run(project_dict, catalog=None):
    catalog = catalog or CATALOG
    project = load(copy.deepcopy(project_dict), CONFIG)
    resolved, models = resolve(project, TABLES, catalog, load_existing(), RULES, prices={})
    est = estimate.project(resolved, TABLES)
    findings = qa.check(project, resolved, est, TABLES, RULES, catalog, CONFIG)
    return project, resolved, models, est, findings


def has(findings, level, text):
    return any(f["level"] == level and text.lower() in f["message"].lower() for f in findings)
