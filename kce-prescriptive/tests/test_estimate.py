import copy
import unittest

from helpers import CATALOG, example_project, run


class EstimateTest(unittest.TestCase):
    def test_kit_and_controls(self):
        _, resolved, models, est, _ = run(example_project())
        a, b = est["lines"]
        # RL 164 is $60/kit; both lines qualify (88W -> 34W DLC-listed = 54W reduced >= 20)
        self.assertEqual((a["measure"], a["lighting"]), ("RL 164", 600))
        self.assertEqual(a["watts_reduced_per_unit"], 54)
        # LC 111 pays only on daylight-zone fixtures: 4 x $50
        self.assertEqual((a["control_code"], a["control"]), ("LC 111", 200))
        # LC 101 networked: 2 x $60, NLC details come from the catalog
        self.assertEqual((b["control_code"], b["control"]), ("LC 101", 120))
        self.assertEqual(est["total"], 600 + 200 + 120 + 120)
        self.assertEqual(models, ["VEKT2X4-8T"])

    def test_enclosed_office_without_sensor_pays_nothing(self):
        p = example_project()
        del p["lines"][1]["control"]
        _, _, _, est, findings = run(p)
        self.assertEqual(est["lines"][1]["lighting"], 0)
        self.assertTrue(any(f["rule"] == 10 and f["level"] == "BLOCKER" for f in findings))

    def test_strip_is_per_foot(self):
        p = example_project()
        p["lines"] = [{"area": "Back room", "int_ext": "Interior - Open", "space_type": "Warehouse Storage - Small hand carry items",
                       "over_300": "Yes", "existing": "8ft-2L-F96T8HO", "existing_qty": 11, "product": "KT-MSLED90PS-8",
                       "control": "KEYSTONE-SMARTLOOP"}]
        _, _, _, est, _ = run(p)
        e = est["lines"][0]
        # RL 111B: $12/ft x 8 ft x 11 fixtures; reduction checked per fixture (160-90=70 >= 5 W/ft x 8)
        self.assertEqual((e["installed_units"], e["lighting"]), (88, 1056))
        self.assertEqual(e["min_watts_reduced"], 40)

    def test_networked_control_needs_nlc_details(self):
        cat = copy.deepcopy(CATALOG)
        del cat["controls"]["SILVAIR-SHARKWARD"]["nlc"]
        _, _, _, est, findings = run(example_project(), catalog=cat)
        self.assertEqual(est["lines"][1]["control"], 0)
        self.assertTrue(any("NLC Details" in f["message"] and f["level"] == "BLOCKER" for f in findings))

    def test_wall_switch_cap(self):
        p = example_project()
        p["lines"][0].update({"control_mounting": "Wall Switch", "control_qty": 1, "daylight_qty": 10})
        _, _, _, est, _ = run(p)
        # LC 111 wall cap is $80 per control; 10 x $50 would be $500
        self.assertEqual(est["lines"][0]["control"], 80)


if __name__ == "__main__":
    unittest.main()
