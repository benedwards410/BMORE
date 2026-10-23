"""Each QA rule against the real misses it was written for (synthetic data)."""

import copy
import unittest

from helpers import CATALOG, example_project, has, run

from prescriptive import qa


class QATest(unittest.TestCase):
    def test_missed_room_is_caught(self):
        p = example_project(audit_totals={"existing_qty": 12 + 29})   # audit had a 29-fixture lecture room
        _, _, _, _, f = run(p)
        self.assertTrue(has(f, "BLOCKER", "A room was dropped"))

    def test_strip_on_high_bay_measure_blocks(self):
        p = example_project()
        cat = copy.deepcopy(CATALOG)
        cat["fixtures"]["KT-MSLED90PS-8"]["primary_use"] = "Direct Linear Ambient Luminaires"
        cat["fixtures"]["KT-MSLED90PS-8"]["dlc_category"] = "Indoor"
        p["lines"] = [{"area": "Exterior rear", "int_ext": "Interior - Open", "space_type": "Warehouse Storage - Small hand carry items",
                       "over_300": "Yes", "existing": "MH-400W", "existing_qty": 7, "product": "KT-MSLED90PS-8",
                       "measure": "RL 142", "control": "KEYSTONE-SMARTLOOP", "mount_height_ft": 20}]
        _, _, _, _, f = run(p, catalog=cat)
        self.assertTrue(has(f, "BLOCKER", "doesn't qualify for RL 142"))

    def test_wall_pack_vs_high_bay(self):
        cat = copy.deepcopy(CATALOG)
        cat["fixtures"]["KT-WPLED120PSHV"]["primary_use"] = "Outdoor Full-Cutoff Wall-Mounted Area Luminaires"
        cat["fixtures"]["KT-WPLED120PSHV"]["dlc_category"] = "Outdoor"
        p = example_project()
        p["lines"] = [{"area": "Warehouse", "int_ext": "Interior - Open", "space_type": "Warehouse Storage - Medium/ Bulky Palletized Material",
                       "over_300": "Yes", "existing": "MH-400W", "existing_qty": 10, "product": "KT-WPLED120PSHV",
                       "measure": "RL 142", "control": "KEYSTONE-SMARTLOOP", "mount_height_ft": 24}]
        _, _, _, _, f = run(p, catalog=cat)
        self.assertTrue(has(f, "BLOCKER", "doesn't qualify for RL 142"))

    def test_lumen_band(self):
        cat = copy.deepcopy(CATALOG)
        hb = cat["fixtures"]["RFHB-23-185WS"]
        hb.update({"dlc_id": "X", "lumens": 23000, "watts": 160, "efficacy": 143, "measure": "RL 142", "cutsheet": None})
        p = example_project()
        p["lines"] = [{"area": "Shop", "int_ext": "Interior - Open", "space_type": "Workshop", "over_300": "Yes",
                       "existing": "MH-400W", "existing_qty": 4, "product": "RFHB-23-185WS", "control": "KEYSTONE-SMARTLOOP",
                       "mount_height_ft": 12}]
        _, _, _, _, f = run(p, catalog=cat)
        self.assertTrue(has(f, "BLOCKER", "outside RL 142's band"))
        self.assertTrue(has(f, "BLOCKER", "needs 15 ft or higher"))

    def test_identity_mismatch_between_documents(self):
        project, *_ = run(example_project())
        f = qa.compare_identity(project, {"city": "Elsewhere", "zip": "20000"}, "old workbook")
        self.assertTrue(has(f, "BLOCKER", "City: project says 'Columbia'"))
        self.assertTrue(has(f, "BLOCKER", "ZIP"))

    def test_payee_mismatch(self):
        project, *_ = run(example_project())
        f = qa.compare_identity(project, {"payee": "customer"}, "T&C")
        self.assertTrue(has(f, "BLOCKER", "Payee"))

    def test_kce_email_as_customer_signer(self):
        p = example_project(customer_contact={"name": "A. Staffer", "email": "staff@key-cre.com"})
        _, _, _, _, f = run(p)
        self.assertTrue(has(f, "BLOCKER", "KCE address"))

    def test_missing_account_and_fuel(self):
        p = example_project()
        p["project"].pop("bge_account")
        p["project"]["heating_fuel"] = None
        _, _, _, _, f = run(p)
        self.assertTrue(has(f, "BLOCKER", "account number is blank"))
        self.assertTrue(has(f, "BLOCKER", "Heating fuel"))

    def test_exterior_needs_photocell(self):
        p = example_project()
        p["lines"] = [{"area": "Rear lot", "int_ext": "Exterior", "space_type": "Uncovered Parking Areas and Driveways",
                       "ext_zone": "Miscellaneous areas not included in other options", "existing": "MH-400W",
                       "existing_qty": 3, "product": "KT-WPLED120PSHV", "unit_price": 325}]
        _, _, _, est, f = run(p)
        self.assertEqual(est["lines"][0]["lighting"], 0)
        self.assertTrue(has(f, "BLOCKER", "time clock or photocell"))
        p["lines"][0]["control"] = "PHOTOCELL"
        _, _, _, est, _ = run(p)
        self.assertEqual(est["lines"][0]["lighting"], 190 * 3)

    def test_ambiguous_dock_asks(self):
        p = example_project()
        p["lines"][0]["area"] = "Loading dock"
        _, _, _, _, f = run(p)
        self.assertTrue(has(f, "ASK", "could be interior or exterior"))

    def test_missing_dlc_data_blocks(self):
        p = example_project()
        p["lines"][0]["product"] = "VEKT2X2-8XX"
        p["lines"][0]["existing"] = "2x2-3L-F17T8"
        _, _, _, _, f = run(p)
        self.assertTrue(has(f, "BLOCKER", "not in the catalog. BGE needs the reported values"))

    def test_clean_project_is_ready_except_cutsheets(self):
        _, _, _, _, f = run(example_project())
        blockers = [x for x in f if x["level"] == "BLOCKER"]
        self.assertEqual([x["rule"] for x in blockers], [6])           # only: Silvair cut sheet not on file
        self.assertIn("Silvair", blockers[0]["message"])


if __name__ == "__main__":
    unittest.main()
