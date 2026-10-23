"""Test suite: each of the nine section 8 behaviors, individually testable,
plus an end-to-end run against the Steve's Pools fixtures.

    python -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from kce_pipeline import checks, transform                      # noqa: E402
from kce_pipeline.normalize import Vocabulary, parse_money      # noqa: E402
from kce_pipeline.run import blank_project, load_config, run_batch  # noqa: E402
from kce_pipeline.transform import FlagList                     # noqa: E402

SETTINGS, VOCAB_CONFIG = load_config(BASE)
FIXTURES = BASE / "regression_fixtures" / "steves_pools"

RECESSED_CAN_ROW = 'Recessed Can - 6" or 8"'


def vocab():
    return Vocabulary(VOCAB_CONFIG, SETTINGS.get("fuzzyMatchThreshold", 0.82))


def severities(flags, rule=None):
    return [f for f in flags.entries
            if rule is None or f["message"].startswith(f"[{rule}]")]


class TestDefensiveParsing(unittest.TestCase):
    """4.1: parse defensively, don't fail a document over one bad cell."""

    def test_repeated_punctuation_typo(self):
        self.assertEqual(parse_money("$30..00"), 30.00)

    def test_normal_currency(self):
        self.assertEqual(parse_money("$1,925.00"), 1925.00)

    def test_included_is_not_a_number(self):
        self.assertIsNone(parse_money("Included"))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_money("n/a"))


class TestCanonicalVocabulary(unittest.TestCase):
    """8.1 / 6.2: the foundational normalization fix."""

    def test_three_wordings_one_type(self):
        """The exact example from 6.2: three parties, one physical fixture."""
        v = vocab()
        for text in ("Wallpack Watt/CCT Select 60-120W",
                     "Exterior LED 100W Wall Mount",
                     "Wall Pack"):
            self.assertEqual(v.match_type(text).canonical, "Wall Pack", text)

    def test_vapor_tight_sizes_stay_distinct(self):
        v = vocab()
        self.assertEqual(v.match_type("4' Vaportight").canonical, "Vapor Tight 4'")
        self.assertEqual(v.match_type("8ft LED Vaportight").canonical, "Vapor Tight 8'")

    def test_primary_fixture_outranks_accessory_mention(self):
        """'Exterior LED 70W Flood, Photocell w/ knuckle' is a Flood Light."""
        self.assertEqual(
            vocab().match_type("Exterior LED 70W Flood, Photocell w/ knuckle").canonical,
            "Flood Light")

    def test_accessory_alone_resolves_to_accessory(self):
        self.assertEqual(vocab().match_type("Photocell w/ knuckle").canonical, "Photocell")

    def test_unknown_name_is_not_invented(self):
        self.assertIsNone(vocab().match_type("Zorblatt Quantum Luminaire").canonical)

    def test_sensor_work_line_vs_fixture_with_bundled_sensor(self):
        """A sensor-labour line is a sensor. A fixture SKU that merely says
        'WITH ... SENSOR' is a FIXTURE (4.2 hasSensor), not a sensor line --
        mis-classifying it invents phantom sensor purchases."""
        v = vocab()
        self.assertEqual(v.match_type("-Sensor install and programming").canonical,
                         "Sensor - Unspecified")
        self.assertEqual(v.match_type("Sensor Programming").canonical,
                         "Sensor - Unspecified")
        for sku in ("RCH/HE/4/35WS/CS/LPR/UNV/12A/WH/SRB KEII WITH KEI-IFS108 SENSOR",
                    "VEFT2X2/8T-ADSRB-20W/25W/30W W/KEIIFS108 WITH KEI-IFS108 SENSOR"):
            self.assertNotEqual(v.match_type(sku).canonical, "Sensor - Unspecified", sku)

    def test_tiered_sensors_still_resolve(self):
        v = vocab()
        self.assertEqual(
            v.match_type("Integrated Fixture Sensor Smart Interior Advance").canonical,
            "Sensor - Advance")
        self.assertEqual(
            v.match_type("Integrated Fixture Sensor Smart Interior Basic").canonical,
            "Sensor - Basic")

    def test_bundled_area_line_parsing(self):
        """Area-billed contractor lines yield quantities but never a split rate."""
        from kce_pipeline.transform import _parse_bundled_fixtures
        v = vocab()
        got = _parse_bundled_fixtures(
            "Service Bay 2- 57 8' Strips, 28 4' Strips, 31 High Bays", v)
        self.assertEqual([(t, q) for t, q, _ in got],
                         [("8' Strip", 57), ("4' Strip", 28), ("High Bay", 31)])

    def test_bundled_parser_ignores_materials_list(self):
        """'1900 Boxes' in a materials list must not become a fixture."""
        from kce_pipeline.transform import _parse_bundled_fixtures
        got = _parse_bundled_fixtures(
            'Material- 12-2 MC and Connectors, 12AWG THHN, 1900 Boxes, Blank Plates',
            vocab())
        self.assertEqual(got, [])

    def test_components_are_not_reconcilable(self):
        v = vocab()
        self.assertFalse(v.is_reconcilable("Photocell"))
        self.assertFalse(v.is_reconcilable("EM Battery Backup"))
        self.assertTrue(v.is_reconcilable("Sensor - Basic"))


class TestSizeClass(unittest.TestCase):
    """8.6: sizeClass is deliberately coarser than fixtureType."""

    def test_coarser_than_canonical_type(self):
        v = vocab()
        self.assertNotEqual(v.match_type("4ft LED Strip").canonical,
                            v.match_type("2x4 Volumetric Kit").canonical)
        self.assertEqual(v.size_class("4ft LED Strip"), "4ft")
        self.assertEqual(v.size_class("2x4 Volumetric Kit"), "4ft")

    def test_exterior_and_high_bay(self):
        v = vocab()
        self.assertEqual(v.size_class("Exterior LED 100W Wall Mount"), "Exterior")
        self.assertEqual(v.size_class("HB sensors"), "High Bay")
        self.assertEqual(v.size_class("4ft sensors"), "4ft")

    def test_high_bay_spelling_variants(self):
        """Real BGE documents write this at least three ways. A 'Hi-Bay' fixture
        row that yields no sizeClass makes its 'HB sensors' row look unmatched."""
        v = vocab()
        for text in ("LED Hi-Bay Dimmable, 160W, 5000CCT",
                     "LED Hi-Bay 160W 1LED160HB",
                     "LED Highbay Fixture >15 ft no relocation",
                     "High Bay 150W"):
            self.assertEqual(v.size_class(text), "High Bay", text)
            self.assertEqual(v.match_type(text).canonical, "High Bay", text)

    def test_volumetric_sized_without_grid_notation(self):
        """BGE writes '4ft LED Volumetric', not '2x4 Volumetric Kit'."""
        v = vocab()
        self.assertEqual(v.match_type("4ft LED Volumetric, 25W, 2500lm").canonical,
                         "2x4 Volumetric Kit")
        self.assertEqual(v.match_type("2ft LED Volumetric, 20W, 2000lm").canonical,
                         "2x2 Volumetric Kit")


def _proposal(lines, meta=None):
    return {"meta": meta or {"auditProposal": "MTX1 / T", "customer": "C"},
            "lines": lines}


def _row(n, location, proposed, qty, existing="old fixture", watts=None):
    return {"line": n, "location": location, "existingDescription": existing,
            "proposedDescription": proposed, "qty": qty, "watts": watts}


class TestSensorSizeClassValidation(unittest.TestCase):
    """8.6: sum every fixture row sharing the sensor row's size class."""

    def _rows_from(self, lines):
        flags = FlagList()
        _, out = transform.transform_proposal_detail(
            _proposal(lines), vocab(), flags, "Doc")
        return [{"sourceDoc": "Doc", "location": r["location"],
                 "fixtureType": r["fixtureType"], "sizeClass": r["sizeClass"],
                 "qty": r["qtyApproved"]} for r in out], flags

    def test_steves_pools_passes_cleanly(self):
        """2 + 1 + 10 = 13 matches the sensor row's 13 -- no critical flag."""
        rows, _ = self._rows_from([
            _row(1, "Pool Room", "LED 4ft Fixture 25W, 4ft Vaportight", 2),
            _row(2, "Lifeguard Room", "LED 4ft Fixture 25W, 4ft Vaportight", 1),
            _row(3, "Restrooms", "LED 4ft Fixture 25W, 4ft Vaportight", 10),
            _row(6, "Sensors", "Integrated Fixture Sensor Smart Interior Basic", 13,
                 existing="LED 4ft Fixture 25W 4LED25FX"),
        ])
        flags = FlagList()
        checks.check_sensor_size_classes(rows, vocab(), SETTINGS, flags)
        self.assertEqual([f for f in flags.entries if f["severity"] == "critical"], [])

    def test_mismatch_raises_critical(self):
        rows, _ = self._rows_from([
            _row(1, "Pool Room", "LED 4ft Fixture 25W, 4ft Vaportight", 2),
            _row(6, "Sensors", "Integrated Fixture Sensor Smart Interior Basic", 13,
                 existing="LED 4ft Fixture 25W 4LED25FX"),
        ])
        flags = FlagList()
        checks.check_sensor_size_classes(rows, vocab(), SETTINGS, flags)
        critical = [f for f in flags.entries if f["severity"] == "critical"]
        self.assertEqual(len(critical), 1)
        self.assertIn("sum to 2", critical[0]["message"])

    def test_bob_bell_cross_canonical_summing(self):
        """8.6 worked example MTX20616192: a '4ft sensors' row sums 4' Strips AND
        2x4 Volumetric Kits -- distinct canonical types, one size class."""
        rows, _ = self._rows_from([
            _row(1, "Area A", "4ft LED Strip", 222),
            _row(2, "Area B", "2x4 Volumetric Kit", 3),
            _row(3, "Area C", "4ft LED Strip", 28),
            _row(4, "Area D", "2x4 Volumetric Kit", 5),
            _row(5, "Area E", "8ft LED Strip", 15),
            _row(6, "Area F", "8ft LED Strip", 91),
            _row(7, "Area G", "2ft LED Strip", 2),
            _row(8, "Area H", "2x2 Volumetric Kit", 2),
            _row(9, "Area I", "High Bay 150W", 50),
            _row(10, "4ft sensors", "Integrated Fixture Sensor Smart Interior Basic", 258),
            _row(11, "8ft sensors", "Integrated Fixture Sensor Smart Interior Basic", 106),
            _row(12, "2ft sensors", "Integrated Fixture Sensor Smart Interior Basic", 4),
            _row(13, "HB sensors", "Integrated Fixture Sensor Smart Interior Basic", 50),
        ])
        flags = FlagList()
        checks.check_sensor_size_classes(rows, vocab(), SETTINGS, flags)
        self.assertEqual([f["message"] for f in flags.entries
                          if f["severity"] == "critical"], [])


DC_META = {"auditProposal": "MTX79857647 / Steve's Pools", "customer": "Fox Valley"}


def _dc(rows, subtotals=None):
    return {"meta": DC_META, "rows": rows,
            "summary": {"subTotals": subtotals}, "feeRows": []}


def _dcrow(line, location, equipment, component, kind, qty, price,
           program=None, customer=None):
    if program is None:
        program = round(price * 0.85, 2)
        customer = round(price - program, 2)
    return {"line": line, "location": location, "proposedEquipment": equipment,
            "component": component, "type": kind, "qty": qty, "price": price,
            "programShare": program, "customerShare": customer}


class TestAccessoryGrouping(unittest.TestCase):
    """8.5: group, don't float."""

    def test_photocell_grouped_certain_without_flag(self):
        flags = FlagList()
        result = transform.transform_detailed_cost(_dc([
            _dcrow(4, "Outside", "Exterior LED 70W Flood",
                   "70 watt flood LED Fixture 4000CCT", "Material", 3, 808.50),
            _dcrow(4, "Outside", "Exterior LED 70W Flood",
                   "Photocell w/ knuckle", "Material", 3, 165.00),
            _dcrow(4, "Outside", "Exterior LED 70W Flood",
                   "LED HW Fixtures, Exterior wall mount < 18 ft", "Labor", 3, 303.60),
        ]), vocab(), flags, "DC", 0.005)

        self.assertEqual(len(result["modeledCosts"]), 1, "photocell must not float")
        row = result["modeledCosts"][0]
        self.assertEqual(row["fixtureType"], "Flood Light")
        self.assertEqual(row["qty"], 3, "qty must not be inflated to 6")
        self.assertEqual(row["materialCost"], 973.50)
        photocell = [c for c in row["components"] if c["type"] == "Photocell"][0]
        self.assertEqual(photocell["groupingConfidence"], "certain")
        self.assertEqual(severities(flags, "§8.5"), [], "certain grouping needs no flag")

    def test_em_battery_backup_always_flags(self):
        """8.5: 'always raise a warning flag, even when the pairing looks obvious'.
        No Steve's Pools document exercises this, so it is covered here."""
        flags = FlagList()
        result = transform.transform_detailed_cost(_dc([
            _dcrow(1, "Office", "LED 4ft Fixture", "4ft LED Strip", "Material", 5, 500.00),
            _dcrow(1, "Office", "LED 4ft Fixture", "EM Battery Backup", "Material", 5, 250.00),
            _dcrow(1, "Office", "LED 4ft Fixture", "2-4ft Fixture LED", "Labor", 5, 200.00),
        ]), vocab(), flags, "DC", 0.005)

        row = result["modeledCosts"][0]
        self.assertEqual(row["qty"], 5)
        self.assertEqual(row["materialCost"], 750.00)
        backup = [c for c in row["components"] if c["type"] == "EM Battery Backup"][0]
        self.assertEqual(backup["groupingConfidence"], "needs_confirmation")
        self.assertEqual(len(severities(flags, "§8.5")), 1)

    def test_sensors_are_never_accessory_grouped(self):
        flags = FlagList()
        result = transform.transform_detailed_cost(_dc([
            _dcrow(6, "Sensors", "Sensor Advance",
                   "Integrated Fixture Sensor Smart Interior Advance", "Material", 6, 600.00),
            _dcrow(6, "Sensors", "Sensor Advance",
                   "Integrated Fixture Sensor Smart Interior Advance", "Labor", 6, 345.00),
        ]), vocab(), flags, "DC", 0.005)
        self.assertEqual(result["modeledCosts"][0]["fixtureType"], "Sensor - Advance")


class TestModeledCostSummation(unittest.TestCase):
    """4.4: material + labor summed per line; SubTotals self-check."""

    def test_identity_and_unit_cost(self):
        flags = FlagList()
        result = transform.transform_detailed_cost(_dc([
            _dcrow(1, "Pool Room", "LED 4ft", "4ft LED Vaportight", "Material",
                   2, 385.00, 327.26, 57.74),
            _dcrow(1, "Pool Room", "LED 4ft", "2-4ft Fixture LED", "Labor",
                   2, 194.82, 165.60, 29.22),
        ], subtotals=579.82), vocab(), flags, "DC", 0.005)
        row = result["modeledCosts"][0]
        self.assertEqual(row["totalCost"], 579.82)
        self.assertEqual(row["unitCostLoaded"], 289.91)
        self.assertEqual(severities(flags, "§4.4"), [])

    def test_broken_identity_raises_critical(self):
        flags = FlagList()
        transform.transform_detailed_cost(_dc([
            _dcrow(1, "X", "F", "4ft LED Strip", "Material", 1, 100.00, 50.00, 10.00),
        ]), vocab(), flags, "DC", 0.005)
        self.assertEqual(len(severities(flags, "§4.4")), 1)


class TestBlendedRates(unittest.TestCase):
    """8.3 / 4.5: blended only from explicit text, never from price."""

    def _invoice(self, description, note, rate=110.0, qty=3):
        return {"isCostAllocation": False, "vendor": "V", "invoiceNumber": "1",
                "date": "01/01/2026",
                "lines": [{"description": description, "note": note,
                           "unitPrice": rate, "qty": qty, "lineTotal": rate * qty}]}

    def test_explicit_text_sets_blended(self):
        fixtures, _ = transform.transform_contractor_invoice(
            self._invoice("-Knuckle Mount Flood",
                          "*Fixtures provided by Let There Be Light. "
                          "$60 install and $50 fixture price."),
            vocab(), FlagList(), "Inv")
        self.assertTrue(fixtures[0]["blended"])

    def test_high_price_alone_does_not(self):
        fixtures, _ = transform.transform_contractor_invoice(
            self._invoice("-Knuckle Mount Flood", None, rate=999.0),
            vocab(), FlagList(), "Inv")
        self.assertFalse(fixtures[0]["blended"])

    def test_cost_allocation_refused(self):
        fixtures, others = transform.transform_contractor_invoice(
            {"isCostAllocation": True, "lines": []}, vocab(), FlagList(), "Inv")
        self.assertEqual((fixtures, others), ([], []))

    def test_fixture_and_flat_line_from_one_read(self):
        """4.5: one read produces both arrays -- no second upload."""
        fixtures, others = transform.transform_contractor_invoice({
            "isCostAllocation": False, "vendor": "V", "invoiceNumber": "1",
            "lines": [
                {"description": "-4' Vaportight", "note": None,
                 "unitPrice": 75.0, "qty": 13, "lineTotal": 975.0},
                {"description": "-Material pick up, scrap/trash removal", "note": None,
                 "unitPrice": None, "qty": None, "lineTotal": 350.0},
            ]}, vocab(), FlagList(), "Inv")
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(len(others), 1)
        self.assertEqual(others[0]["category"], "Disposal")
        self.assertEqual(others[0]["amount"], 350.00)


class TestQuantityReconciliation(unittest.TestCase):
    """8.8: flag, never auto-reconcile; handle negative remaining."""

    def _project(self, ordered=None, approved=None, installed=None, ftype="Wall Pack"):
        project = blank_project()
        if ordered is not None:
            project["supplierLines"].append(
                {"fixtureType": ftype, "qtyOrdered": ordered, "source": "actual_invoice"})
        if approved is not None:
            project["workOrderLines"].append(
                {"fixtureType": ftype, "qtyApproved": approved})
        if installed is not None:
            project["contractorLines"].append({"fixtureType": ftype, "qty": installed})
        return project

    def test_clean_case_does_not_flag(self):
        flags = FlagList()
        rows = checks.check_quantities(
            self._project(13, 13, 13, "Vapor Tight 4'"), vocab(), SETTINGS, flags)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(severities(flags, "§8.8"), [])

    def test_mismatch_flags_critical(self):
        flags = FlagList()
        rows = checks.check_quantities(self._project(5, 2, 2), vocab(), SETTINGS, flags)
        self.assertEqual(rows[0]["status"], "mismatch")
        self.assertEqual(rows[0]["remaining"], 3)
        self.assertEqual(len(severities(flags, "§8.8")), 1)

    def test_negative_remaining_is_graceful(self):
        flags = FlagList()
        rows = checks.check_quantities(self._project(2, 2, 5), vocab(), SETTINGS, flags)
        self.assertEqual(rows[0]["remaining"], -3, "must not clamp to zero")
        self.assertIn("Installed exceeds ordered",
                      severities(flags, "§8.8")[0]["message"])

    def test_components_excluded(self):
        flags = FlagList()
        rows = checks.check_quantities(
            self._project(3, None, None, "Photocell"), vocab(), SETTINGS, flags)
        self.assertEqual(rows, [], "a photocell must never reconcile independently")

    def test_modeled_lines_never_count_as_ordered(self):
        project = blank_project()
        project["supplierLines"].append(
            {"fixtureType": "Wall Pack", "qtyOrdered": 2, "source": "modeled_cost"})
        project["workOrderLines"].append({"fixtureType": "Wall Pack", "qtyApproved": 2})
        flags = FlagList()
        rows = checks.check_quantities(project, vocab(), SETTINGS, flags)
        self.assertIsNone(rows[0]["ordered"])
        self.assertEqual(severities(flags, "§8.8"), [])


class TestModeledVsActual(unittest.TestCase):
    """8.2: never conflate the two cost bases."""

    def test_both_present_warns(self):
        project = blank_project()
        project["supplierLines"] += [
            {"fixtureType": "Vapor Tight 4'", "qtyOrdered": 13, "unitPrice": 65.0,
             "source": "actual_invoice"},
            {"fixtureType": "Vapor Tight 4'", "qtyOrdered": 13, "unitPrice": 192.50,
             "source": "modeled_cost"},
        ]
        flags = FlagList()
        checks.check_modeled_vs_actual(project, flags)
        self.assertEqual(len(severities(flags, "§8.2")), 1)
        self.assertIn("not 26", severities(flags, "§8.2")[0]["message"])


class TestMtxConsistency(unittest.TestCase):
    """8.9: exclude a mismatched document, process the rest."""

    class Doc:
        def __init__(self, name, doc_type, mtx):
            self.name, self.doc_type, self.mtx = name, doc_type, mtx

    def test_rate_card_is_exempt(self):
        flags = FlagList()
        agreed, excluded = checks.check_mtx_consistency([
            self.Doc("a.pdf", "proposal_detail", "MTX1"),
            self.Doc("rates.pdf", "piece_rate_schedule", None),
        ], SETTINGS, flags)
        self.assertEqual((agreed, excluded), ("MTX1", set()))
        self.assertEqual(flags.entries, [])

    def test_stranger_is_excluded_with_critical(self):
        flags = FlagList()
        agreed, excluded = checks.check_mtx_consistency([
            self.Doc("a.pdf", "proposal_detail", "MTX1"),
            self.Doc("b.pdf", "detailed_cost", "MTX1"),
            self.Doc("c.pdf", "supplier_invoice", "MTX999"),
        ], SETTINGS, flags)
        self.assertEqual(agreed, "MTX1")
        self.assertEqual(excluded, {"c.pdf"})
        self.assertEqual(len(severities(flags, "§8.9")), 1)


class TestPieceRates(unittest.TestCase):
    """4.1 / 8.7: tiers stay separate, 'Included' rows are skipped."""

    def _rates(self, rows):
        return transform.transform_piece_rates({"rows": rows}, vocab(), FlagList(), "RC")

    def test_typo_rate_and_tiers(self):
        out = self._rates([
            {"description": RECESSED_CAN_ROW, "installUnit": "per fixture",
             "rateText": "$30..00"},
            {"description": "Wall Pack < 50W", "installUnit": "per fixture",
             "rateText": "$50.00"},
            {"description": "Wall Pack > 50W", "installUnit": "per fixture",
             "rateText": "$75.00"},
            {"description": "+ Bluetooth Sensor (add-on)", "installUnit": "per sensor",
             "rateText": "Included"},
        ])
        by_type = {(r["fixtureType"], r["wattageTier"]): r["contractedRate"] for r in out}
        self.assertEqual(by_type[("Recessed Can", None)], 30.00)
        self.assertEqual(by_type[("Wall Pack", "<50W")], 50.00)
        self.assertEqual(by_type[("Wall Pack", ">50W")], 75.00)
        self.assertEqual(len(out), 3, "'Included' row must be skipped")

    def test_size_range_expands(self):
        out = self._rates([{"description": "Strip - 2 ft or 4 ft",
                            "installUnit": "per fixture", "rateText": "$50.00"}])
        self.assertEqual({r["fixtureType"] for r in out}, {"2' Strip", "4' Strip"})


class TestWorkOrderSourceRestriction(unittest.TestCase):
    """8.4: the Detailed Cost Report never populates workOrderLines."""

    def test_detailed_cost_does_not_write_work_order(self):
        result = transform.transform_detailed_cost(_dc([
            _dcrow(1, "Pool Room", "LED 4ft", "4ft LED Vaportight", "Material", 2, 385.00),
            _dcrow(1, "Pool Room", "LED 4ft", "2-4ft Fixture LED", "Labor", 2, 194.82),
        ]), vocab(), FlagList(), "DC", 0.005)
        self.assertNotIn("workOrderLines", result)


class TestInventoryAndCredits(unittest.TestCase):
    """Document types 6 and 7 -- added beyond the outline's five at KCE's request."""

    INVENTORY = {"rows": [
        {"description": "8' Strip (w/ sensor)", "sku": "ESPRCHHE875WSCSLPRUNV12AWHSRBKEIIFS108",
         "delivered": 129, "remaining": 9, "note": "Justn -14"},
        {"description": "2x2 Volumetric Kit (w/ sensor)", "sku": "ESPVEFT2X28TADSRB20W25W30WKEIIFS108",
         "delivered": 3, "remaining": 1, "note": None},
        {"description": "8' Vaportight (no sensor)", "sku": "ESPREVT890WSCSUNV12A",
         "delivered": 10, "remaining": 10, "note": None},
    ]}

    def test_sku_map_overrides_a_misleading_description(self):
        """ESPVEFT2X28... reads like a 2x2 volumetric; KCE confirms it is a 2' Strip.
        The SKU must win, or 3 units land under the wrong fixture type."""
        rows = transform.transform_inventory(self.INVENTORY, vocab(), FlagList(), "Inv")
        by_sku = {r["sku"]: r for r in rows}
        self.assertEqual(by_sku["ESPVEFT2X28TADSRB20W25W30WKEIIFS108"]["fixtureType"],
                         "2' Strip")
        self.assertEqual(by_sku["ESPREVT890WSCSUNV12A"]["fixtureType"], "Vapor Tight 8'")

    def test_sku_matching_ignores_punctuation(self):
        v = vocab()
        self.assertEqual(v.match_sku("KEI-IFS108").canonical,
                         v.match_sku("KEIIFS108").canonical)

    def test_consumed_is_delivered_minus_remaining(self):
        rows = transform.transform_inventory(self.INVENTORY, vocab(), FlagList(), "Inv")
        self.assertEqual(rows[0]["consumed"], 120)
        self.assertEqual(rows[2]["consumed"], 0)

    def test_excess_and_transfer_note_are_flagged(self):
        project = blank_project()
        project["inventory"] = transform.transform_inventory(
            self.INVENTORY, vocab(), FlagList(), "Inv")
        reconciliation = [{"fixtureType": "8' Strip", "installed": 106}]
        flags = FlagList()
        checks.check_inventory(project, reconciliation, vocab(), flags)

        messages = " ".join(f["message"] for f in flags.entries)
        # 129 delivered - 9 remaining = 120 consumed vs 106 installed -> 14, the
        # exact number in the "Justn -14" note. Quote it, do not assume it.
        self.assertIn("difference 14", messages)
        self.assertIn("Justn -14", messages)
        self.assertIn("Excess inventory", messages)
        self.assertIn("10 x Vapor Tight 8'", messages)

    CREDIT = {"contractor": "Cartwright Electric & Build", "totalCreditDue": 838,
              "invoices": [
                  {"invoiceNumber": "123-456-1176", "date": "August 2, 2026",
                   "billedTotal": 14023, "correctedTotal": 13539, "creditDue": 484,
                   "rows": [{"description": "8' Strip", "qty": 15, "billedRate": 65,
                             "correctRate": 63, "overcharge": 30}]},
                  {"invoiceNumber": "123-456-1179", "date": "August 11, 2026",
                   "billedTotal": 11465, "correctedTotal": 11111, "creditDue": 354,
                   "rows": []}]}

    def test_credits_extracted_per_invoice(self):
        credits = transform.transform_credit_calculation(
            self.CREDIT, vocab(), FlagList(), "Memo")
        self.assertEqual([c["creditDue"] for c in credits], [484.0, 354.0])
        self.assertEqual(credits[0]["lines"][0]["fixtureType"], "8' Strip")

    def test_credit_memo_that_does_not_add_up_is_critical(self):
        broken = json.loads(json.dumps(self.CREDIT))
        broken["totalCreditDue"] = 900
        flags = FlagList()
        transform.transform_credit_calculation(broken, vocab(), flags, "Memo")
        self.assertEqual(len(severities(flags, "§8.3")), 1)
        self.assertEqual(flags.entries[0]["severity"], "critical")

    def test_batch_without_these_documents_stays_silent(self):
        """Steve's Pools has neither document. Empty arrays, no spurious flags."""
        result = run_batch(FIXTURES, BASE, backend_override="cache")
        self.assertEqual(result["project"]["inventory"], [])
        self.assertEqual(result["project"]["credits"], [])
        messages = " ".join(f["message"] for f in result["project"]["flags"])
        self.assertNotIn("Excess inventory", messages)
        self.assertNotIn("piece-rate credit", messages)


class TestEndToEnd(unittest.TestCase):
    """Section 9 acceptance criteria against the real fixture batch."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_batch(FIXTURES, BASE, backend_override="cache")
        cls.project = cls.result["project"]
        cls.flags = cls.project["flags"]

    def test_schema_keys_match_6_1_exactly(self):
        """Every 6.1 key present, in order. Extra keys are allowed only if they
        are the documented additions -- the ROI tracker ignores unknown keys, but
        a silently renamed 6.1 key would break the import."""
        required = ["project", "supplierLines", "workOrderLines", "pieceRates",
                    "contractorLines", "otherExpenses", "modeledCosts", "flags"]
        keys = list(self.project.keys())
        self.assertEqual([k for k in keys if k in required], required)
        self.assertEqual(set(keys) - set(required), {"inventory", "credits"})
        self.assertEqual(list(self.project["project"].keys()),
                         ["name", "poNumber", "customer", "address", "contactName",
                          "contactPhone", "revenue"])

    def test_project_metadata(self):
        meta = self.project["project"]
        self.assertEqual(meta["name"], "Steve's Pools")
        self.assertEqual(meta["poNumber"], "MTX79857647")
        self.assertEqual(meta["customer"], "Fox Valley Homeowners Assoc")
        self.assertEqual(meta["address"],
                         "3320 GREAT VALLEY Drive, West Friendship MD 21794")

    def test_revenue_never_autofilled(self):
        self.assertIsNone(self.project["project"]["revenue"])
        self.assertTrue(any("revenue" in f["message"] for f in self.flags))

    def test_modeled_subtotal_is_exact(self):
        self.assertEqual(self.result["subtotals"]["computed"], 7609.83)
        self.assertTrue(self.result["subtotals"]["matches"])

    def test_vapor_tight_unit_cost_identical_across_locations(self):
        rows = [r for r in self.project["modeledCosts"]
                if r["fixtureType"] == "Vapor Tight 4'"]
        self.assertEqual(len(rows), 3)
        self.assertEqual({r["unitCostLoaded"] for r in rows}, {289.91})

    def test_vapor_tight_reconciles_without_flag(self):
        row = [r for r in self.result["reconciliation"]
               if r["fixtureType"] == "Vapor Tight 4'"][0]
        self.assertEqual((row["ordered"], row["approved"], row["installed"]),
                         (13, 13, 13))
        self.assertEqual(row["status"], "ok")

    def test_wall_pack_mismatch_is_critical(self):
        row = [r for r in self.result["reconciliation"]
               if r["fixtureType"] == "Wall Pack"][0]
        self.assertEqual((row["ordered"], row["approved"], row["installed"]), (5, 2, 2))
        self.assertTrue(any(f["severity"] == "critical"
                            and f["relatedFixtureType"] == "Wall Pack"
                            for f in self.flags))

    def test_wall_pack_modeled_grouping(self):
        row = [r for r in self.project["modeledCosts"]
               if r["fixtureType"] == "Wall Pack"][0]
        self.assertEqual(row["materialCost"], 825.00)
        self.assertEqual(row["laborCost"], 202.40)
        self.assertEqual(row["unitCostLoaded"], 513.70)
        self.assertEqual(row["qty"], 2)

    def test_flood_light_modeled_grouping(self):
        row = [r for r in self.project["modeledCosts"]
               if r["fixtureType"] == "Flood Light"][0]
        self.assertEqual(row["materialCost"], 973.50)
        self.assertEqual(row["unitCostLoaded"], 425.70)
        photocell = [c for c in row["components"] if c["type"] == "Photocell"][0]
        self.assertEqual(photocell["materialCost"], 165.00)
        self.assertEqual(photocell["groupingConfidence"], "certain")

    def test_photocell_is_not_a_free_floating_type(self):
        self.assertNotIn("Photocell",
                         {r["fixtureType"] for r in self.result["reconciliation"]})

    def test_flood_light_blended_and_no_actual_invoice(self):
        line = [r for r in self.project["contractorLines"]
                if r["fixtureType"] == "Flood Light"][0]
        self.assertTrue(line["blended"])
        self.assertEqual(line["billedRate"], 110.00)
        self.assertTrue(any("no actual_invoice material record" in f["message"]
                            for f in self.flags))

    def test_sensor_tier_disagreement_flagged(self):
        self.assertTrue(any("tier breakdown" in f["message"] for f in self.flags))

    def test_sensor_size_class_validation_passed_silently(self):
        """13 = 2 + 1 + 10 on the Proposal Detail -- no critical flag."""
        sensor_criticals = [f for f in self.flags
                            if f["severity"] == "critical"
                            and "size class" in f["message"]]
        self.assertEqual(sensor_criticals, [])
        sensor_row = [r for r in self.project["workOrderLines"]
                      if r["fixtureType"] == "Sensor - Basic"][0]
        self.assertEqual(sensor_row["sizeClass"], "4ft")
        self.assertEqual(sensor_row["qtyApproved"], 13)

    def test_contractor_invoice_totals(self):
        """13x75 + 2x60 + 3x110 + 350 = 1775.00"""
        fixtures = sum(r["qty"] * r["billedRate"]
                       for r in self.project["contractorLines"])
        disposal = sum(r["amount"] for r in self.project["otherExpenses"]
                       if r["category"] == "Disposal")
        self.assertEqual(fixtures + disposal, 1775.00)

    def test_fee_rows(self):
        fees = {r["category"]: r["amount"] for r in self.project["otherExpenses"]}
        self.assertEqual(fees["Recycling Fee"], 99.32)
        self.assertEqual(fees["Sales Tax"], 321.02)

    def test_recessed_can_typo_parsed(self):
        rate = [r for r in self.project["pieceRates"]
                if r["fixtureType"] == "Recessed Can"][0]
        self.assertEqual(rate["contractedRate"], 30.00)

    def test_tiered_categories_produce_two_rows(self):
        for fixture_type in ("Wall Pack", "Flood Light"):
            rows = [r for r in self.project["pieceRates"]
                    if r["fixtureType"] == fixture_type]
            self.assertEqual(len(rows), 2, fixture_type)
            self.assertEqual({r["wattageTier"] for r in rows}, {"<50W", ">50W"})

    def test_every_line_carries_a_source(self):
        for array in ("supplierLines", "workOrderLines", "pieceRates",
                      "contractorLines", "otherExpenses", "modeledCosts"):
            for row in self.project[array]:
                self.assertIn("source", row, f"{array} row missing source")

    def test_unclassifiable_file_skipped_not_fatal(self):
        names = {d.name: d for d in self.result["documents"]}
        outline = names["Document_Intake_Pipeline_Task_Outline.md"]
        self.assertEqual(outline.doc_type, "unknown")
        self.assertTrue(any("Document_Intake_Pipeline_Task_Outline.md" in f["message"]
                            for f in self.flags))

    def test_mtx_consistency_passed(self):
        self.assertEqual(self.result["mtx"], "MTX79857647")
        self.assertFalse(any(d.excluded for d in self.result["documents"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestFileReadiness(unittest.TestCase):
    """Backlog item 3: never read a half-synced file."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, data: bytes) -> Path:
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def test_complete_pdf_passes(self):
        from kce_pipeline.extract import file_readiness
        body = b"%PDF-1.7\n" + b"x" * 2000 + b"\n%%EOF\n"
        problem, _ = file_readiness(self._write("good.pdf", body))
        self.assertIsNone(problem)

    def test_empty_file_is_rejected(self):
        from kce_pipeline.extract import file_readiness
        problem, _ = file_readiness(self._write("empty.pdf", b""))
        self.assertIsNotNone(problem)
        self.assertIn("0 bytes", problem)

    def test_tiny_file_is_rejected(self):
        from kce_pipeline.extract import file_readiness
        problem, _ = file_readiness(self._write("stub.pdf", b"%PDF-1.7\n%%EOF\n"))
        self.assertIsNotNone(problem)
        self.assertIn("too small", problem)

    def test_truncated_pdf_is_rejected(self):
        """The real hazard: a plausible-looking PDF with no %%EOF. Reading it
        would return fewer rows and no error."""
        from kce_pipeline.extract import file_readiness
        body = b"%PDF-1.7\n" + b"x" * 4000  # transfer stopped part-way
        problem, _ = file_readiness(self._write("half.pdf", body))
        self.assertIsNotNone(problem)
        self.assertIn("TRUNCATED", problem)

    def test_non_pdf_header_is_rejected(self):
        from kce_pipeline.extract import file_readiness
        problem, _ = file_readiness(self._write("bad.pdf", b"\x00" * 4000))
        self.assertIsNotNone(problem)
        self.assertIn("PDF header", problem)

    def test_real_fixture_passes(self):
        from kce_pipeline.extract import file_readiness
        for pdf in FIXTURES.glob("*.pdf"):
            problem, _ = file_readiness(pdf)
            self.assertIsNone(problem, f"{pdf.name}: {problem}")


class TestRunDiff(unittest.TestCase):
    """Backlog item 4: what moved since last time."""

    def _snap(self, **overrides):
        base = {
            "timestamp": "2026-01-01T00:00:00", "project": "P", "poNumber": "MTX1",
            "documents": ["a.pdf", "b.pdf"],
            "flags": [["critical", "§8.8", "Wall Pack"]],
            "quantities": {"Wall Pack": {"ordered": 5, "approved": 2, "installed": 2}},
            "totals": {"modeledCosts": 100.0, "otherExpenses": 0.0,
                       "credits": 0.0, "inventoryRemaining": 0},
        }
        base.update(overrides)
        return base

    def test_first_run_has_no_diff(self):
        from kce_pipeline import diff
        self.assertIsNone(diff.compare(None, self._snap()))

    def test_identical_runs_report_unchanged(self):
        from kce_pipeline import diff
        out = diff.compare(self._snap(), self._snap())
        self.assertTrue(out["unchanged"])
        self.assertIn("Nothing changed", "\n".join(diff.render(out)))

    def test_new_document_and_quantity_move_are_reported(self):
        from kce_pipeline import diff
        after = self._snap(
            documents=["a.pdf", "b.pdf", "c.pdf"],
            quantities={"Wall Pack": {"ordered": 5, "approved": 2, "installed": 5}})
        out = diff.compare(self._snap(), after)
        self.assertFalse(out["unchanged"])
        self.assertEqual(out["documentsAdded"], ["c.pdf"])
        self.assertEqual(out["quantityMoves"],
                         [{"fixtureType": "Wall Pack", "field": "installed",
                           "from": 2, "to": 5}])
        rendered = "\n".join(diff.render(out))
        self.assertIn("c.pdf", rendered)
        self.assertIn("installed 2 → **5**", rendered)

    def test_cleared_flag_is_reported(self):
        from kce_pipeline import diff
        out = diff.compare(self._snap(), self._snap(flags=[]))
        self.assertEqual(out["flagsCleared"], [("critical", "§8.8", "Wall Pack")])
        self.assertIn("Cleared critical flag", "\n".join(diff.render(out)))

    def test_amounts_inside_messages_do_not_create_false_changes(self):
        """Flag text embeds dollar figures. Comparing rendered strings would
        report a change every time a number moved by a cent -- the diff must key
        on (severity, rule, fixtureType) only."""
        from kce_pipeline import diff
        before = diff.snapshot({
            "project": {"project": {"name": "P", "poNumber": "M"}, "flags": [
                {"severity": "warning", "message": "[§8.2] Wall Pack cost $1.00",
                 "relatedFixtureType": "Wall Pack"}],
                "otherExpenses": [], "credits": [], "inventory": []},
            "documents": [], "reconciliation": [], "subtotals": {"computed": 1.0}})
        after = diff.snapshot({
            "project": {"project": {"name": "P", "poNumber": "M"}, "flags": [
                {"severity": "warning", "message": "[§8.2] Wall Pack cost $2.00",
                 "relatedFixtureType": "Wall Pack"}],
                "otherExpenses": [], "credits": [], "inventory": []},
            "documents": [], "reconciliation": [], "subtotals": {"computed": 1.0}})
        out = diff.compare(before, after)
        self.assertEqual(out["flagsRaised"], [])
        self.assertEqual(out["flagsCleared"], [])
