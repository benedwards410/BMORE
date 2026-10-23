import json
import unittest

from helpers.intake_env import IntakeEnv
from helpers.minipdf import make_pdf
from kce_intake.filer import Candidate, Filer
from kce_intake.projects import ProjectIndex, slugify
from kce_intake.state import HashCache, read_json

PA = make_pdf(["BGE Small Business Participation Agreement", "Audit / Proposal: MTX79857647 / Steve's Pools",
               "Fox Valley Homeowners Assoc", "3320 GREAT VALLEY Drive, West Friendship MD 21794"])
PROPOSAL = make_pdf(["Proposal Detail Report for Fox Valley Homeowners Assoc", "MTX79857647 / Steve's Pools",
                     "3320 GREAT VALLEY Drive, West Friendship MD 21794"])
INVOICE = make_pdf(["Let There Be Light Electric", "Invoice #2025-26", "Job: Steves Pool, 3320 Great Valley Dr",
                    "13 - 4' Vaportight @ $75.00"])
BEACON = make_pdf(["Beacon Lighting Supply", "Invoice 148", "Ship To: 3320 GREAT VALLEY DRIVE WEST FRIENDSHIP MD"])
NO_CLUES = make_pdf(["Some scanned thing with nothing useful"])


class FilerTests(unittest.TestCase):
    def setUp(self):
        self.env = IntakeEnv()
        self.cfg = self.env.cfg
        self.open()

    def open(self):
        self.index = ProjectIndex(self.cfg.projects_root, self.cfg.out_subfolder).rebuild()
        self.cache = HashCache(self.cfg.hash_cache_path)
        self.filer = Filer(self.cfg, self.index, self.cache)

    def tearDown(self):
        self.env.close()

    def test_slugify_matches_pipeline(self):
        self.assertEqual(slugify("Steve's Pools"), "steve_s_pools")
        self.assertEqual(slugify("HBs to Strips (no vapors)"), "hbs_to_strips_no_vapors")

    def test_confirmed_from_document_creates_folder_and_manifest(self):
        out = self.filer.file(Candidate("Participation Agreement-Steve's Pools.pdf", PA, "outlook",
                                        {"messageId": "m1", "attachmentId": "a1", "subject": "Paperwork", "sender": "tommy@matrixescorp.com"}))
        self.assertEqual(out.action, "filed")
        self.assertEqual(out.mtx, "MTX79857647")
        self.assertEqual(out.match, "confirmed")
        folder = self.cfg.projects_root / "MTX79857647 - steve_s_pools"
        self.assertTrue((folder / "Participation Agreement-Steve's Pools.pdf").exists())
        manifest = read_json(folder / "_intake" / "manifest.json", {})
        self.assertEqual(manifest["mtx"], "MTX79857647")
        self.assertEqual(manifest["files"][0]["docTypeHint"], "participation_agreement")
        self.assertEqual(manifest["files"][0]["match"], "confirmed")
        self.assertNotIn("bodyText", manifest["files"][0])
        observed = read_json(folder / "_intake" / "addresses.json", [])
        self.assertEqual(observed[0]["number"], "3320")

    def test_address_inferred_match_after_pa(self):
        self.filer.file(Candidate("Participation Agreement-Steve's Pools.pdf", PA, "outlook", {"subject": "x"}))
        out = self.filer.file(Candidate("Justin - Steves Pool Invoice 2025-26.pdf", INVOICE, "outlook",
                                        {"subject": "Invoice for Steves pool", "sender": "justin@ltbl.example"}))
        self.assertEqual((out.action, out.mtx, out.match), ("filed", "MTX79857647", "inferred"))
        self.assertIn("3320 great", out.matched_on)
        beacon = self.filer.file(Candidate("148.pdf", BEACON, "quickbooks", {"subject": "New payment request - invoice 148"}))
        self.assertEqual((beacon.action, beacon.match), ("filed", "inferred"))

    def test_no_clues_is_held_with_why(self):
        out = self.filer.file(Candidate("mystery.pdf", NO_CLUES, "dropfolder", {"path": "/drop/mystery.pdf"}))
        self.assertEqual(out.action, "held")
        day_dirs = list(self.cfg.unmatched_dir.iterdir())
        self.assertEqual(len(day_dirs), 1)
        why = (day_dirs[0] / "WHY.md").read_text(encoding="utf-8")
        self.assertIn("mystery.pdf", why)
        self.assertIn("no MTX number and no site address", why)

    def test_ambiguous_address_is_held(self):
        a = self.env.project_dir("MTX11111111 - suite_a")
        b = self.env.project_dir("MTX22222222 - suite_b")
        for folder, suite in ((a, "A"), (b, "B")):
            (folder / "_intake").mkdir()
            (folder / "_intake" / "aliases.txt").write_text(f"5114 Dorsey Hall Suite {suite}\n", encoding="utf-8")
        self.open()
        vague = make_pdf(["Smart Solutions Inc", "Invoice 1030", "Site: 5114 Dorsey Hall"])
        out = self.filer.file(Candidate("Smart Solutions Invoice 1030.pdf", vague, "outlook", {"subject": "Invoice Dorsey Hall"}))
        self.assertEqual(out.action, "held")
        self.assertIn("several projects", out.reason)
        exact = make_pdf(["Smart Solutions Inc", "Invoice 1031", "Site: 5114 Dorsey Hall Suite B"])
        out = self.filer.file(Candidate("Smart Solutions Invoice 1031.pdf", exact, "outlook", {"subject": "Invoice"}))
        self.assertEqual((out.action, out.mtx), ("filed", "MTX22222222"))

    def test_mtx_from_subject_is_inferred_and_body_with_many_is_held(self):
        out = self.filer.file(Candidate("scan.pdf", NO_CLUES, "outlook", {"subject": "WO for MTX43021446"}))
        self.assertEqual((out.action, out.mtx, out.match), ("filed", "MTX43021446", "inferred"))
        self.assertEqual(out.matched_on, "email subject")
        many = Candidate("scan2.pdf", make_pdf(["other scan"]), "outlook",
                         {"subject": "Work Orders for Dorsey Hall", "bodyText": "MTX60617457 MTX83070560 MTX16953741"})
        out = self.filer.file(many)
        self.assertEqual(out.action, "held")
        self.assertIn("several MTX", out.reason)

    def test_document_with_two_mtx_is_held(self):
        two = make_pdf(["Credit memo covers MTX79857647 and MTX20616192"])
        out = self.filer.file(Candidate("credit.pdf", two, "outlook", {}))
        self.assertEqual(out.action, "held")

    def test_duplicates_by_hash_and_name_collisions(self):
        c = Candidate("Participation Agreement-Steve's Pools.pdf", PA, "outlook", {"messageId": "m1"})
        self.assertEqual(self.filer.file(c).action, "filed")
        self.assertEqual(self.filer.file(Candidate("renamed.pdf", PA, "dropfolder", {})).action, "duplicate")
        # fresh process: known set rebuilt from disk
        self.open()
        self.assertEqual(self.filer.file(Candidate("again.pdf", PA, "dropfolder", {})).action, "duplicate")
        # same name, different bytes → suffixed, never overwritten
        out = self.filer.file(Candidate("Participation Agreement-Steve's Pools.pdf", PROPOSAL, "outlook", {}))
        self.assertEqual(out.action, "filed")
        self.assertEqual(out.path.name, "Participation Agreement-Steve's Pools (2).pdf")
        self.assertEqual((out.path.parent / "Participation Agreement-Steve's Pools.pdf").read_bytes(), PA)

    def test_unsupported_type_skipped(self):
        out = self.filer.file(Candidate("notes.docx", b"PK..", "outlook", {}))
        self.assertEqual(out.action, "skipped")

    def test_index_reads_pipeline_project_json(self):
        folder = self.env.project_dir("MTX55555555 - jabez")
        (folder / "_reconciliation").mkdir()
        (folder / "_reconciliation" / "x.project.json").write_text(json.dumps(
            {"project": {"name": "Jabez", "address": "1514 JABEZ Run SUITE 106, Millersville MD"}}), encoding="utf-8")
        self.open()
        rec = self.index.find("MTX55555555")
        self.assertEqual(rec.name, "jabez")
        self.assertEqual([str(a) for a in rec.addresses], ["1514 jabez #106"])
        human = read_json(self.cfg.projects_root / "index.json", {})
        self.assertIn("MTX55555555", human)


if __name__ == "__main__":
    unittest.main()
