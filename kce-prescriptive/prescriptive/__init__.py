"""KCE prescriptive application bot: audit -> BGE workbook, proposal, T&C, cut sheets, portal sheet."""

import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(PKG_DIR)
REFERENCES_DIR = os.path.join(PLUGIN_DIR, "references")
CATALOG_DIR = os.path.join(PLUGIN_DIR, "catalog")
TEMPLATES_DIR = os.path.join(PLUGIN_DIR, "templates")
CONFIG_DIR = os.path.join(PLUGIN_DIR, "config")
