"""Golden run against a real, already-submitted job. Skipped unless these LOCAL files exist
(customer data never goes in git):

  GOLDEN_PROJECT=<project.json>    imported from the submitted workbook (import-workbook)
  GOLDEN_WORKBOOK=<.xlsm>          that submitted workbook, saved by Excel (holds Excel's own totals)
  plus a blank BGE workbook in templates/bge/ or BGE_TEMPLATE
"""

import glob
import os
import tempfile
import unittest

from helpers import PLUGIN

from prescriptive import build, reports, template_map as tm
from prescriptive._xlsx import grid, load

PROJECT = os.environ.get("GOLDEN_PROJECT") or ""
WORKBOOK = os.environ.get("GOLDEN_WORKBOOK") or ""
HAVE_TEMPLATE = bool(glob.glob(os.path.join(PLUGIN, "templates", "bge", "*.xlsm")) or os.environ.get("BGE_TEMPLATE"))


@unittest.skipUnless(os.path.exists(PROJECT) and os.path.exists(WORKBOOK) and HAVE_TEMPLATE, "local golden files not set")
class GoldenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.summary = build.run(PROJECT, cls.out, force=True)

    def test_estimate_matches_excel_line_by_line(self):
        ctx = build.prepare(PROJECT)
        rb = reports.readback(WORKBOOK, ctx["resolved"], ctx["estimate"])
        self.assertTrue(rb["ok"], rb["message"])
        self.assertEqual(round(rb["totals"]["incentive"]), round(self.summary["estimate"]["total"]))

    def test_line_inputs_match_submitted_workbook(self):
        n = len(build.prepare(PROJECT)["resolved"])
        last = tm.LINE_FIRST_ROW + n - 1
        a, b = load(WORKBOOK), load(self.summary["files"]["workbook"])
        ga, gb = grid(a[tm.LI], tm.LINE_FIRST_ROW, last, 50), grid(b[tm.LI], tm.LINE_FIRST_ROW, last, 50)
        skip = {"incentive_structure", "unit", "model_select"}
        norm = lambda v: (v.strip() if isinstance(v, str) else v) if v not in ("", 0, None) else None  # noqa: E731
        diffs = [f"{c}{r}" for r in range(tm.LINE_FIRST_ROW, last + 1) for k, c in tm.LINE_COLS.items()
                 if k not in skip and norm(ga.get(f"{c}{r}")) != norm(gb.get(f"{c}{r}"))]
        self.assertEqual(diffs, [])


if __name__ == "__main__":
    unittest.main()
