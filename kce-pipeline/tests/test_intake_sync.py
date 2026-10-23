"""End to end, offline: drop folder + fake mailbox → filed per MTX → pipeline run."""
import os
import time
import unittest
from datetime import datetime, timezone

from helpers.fake_mail import FakeMailClient
from helpers.intake_env import IntakeEnv
from helpers.minipdf import make_pdf
from kce_intake import cli
from kce_intake.filer import Filer
from kce_intake.projects import ProjectIndex
from kce_intake.sources import dropfolder, outlook
from kce_intake.state import HashCache, State, read_json

PA = make_pdf(["Participation Agreement", "MTX38729390 / Solar Energy Services", "1514 JABEZ Run SUITE 106, Millersville MD 21108"])
COST = make_pdf(["Detailed Cost Report", "MTX38729390 / Solar Energy Services", "Program Share Customer Share"])
SMART = make_pdf(["Smart Solutions Inc Invoice 1028", "Site: 1514 Jabez Run Suite 106", "9 x 2x4 Volumetric @ $50"])

MESSAGES = [
    {"id": "m-matrix", "subject": "Re: Submit for payment- solar energy", "receivedDateTime": "2026-10-21T18:33:30Z",
     "sender": "thomas.tillman@matrixescorp.com", "internetMessageId": "<x1@matrix>",
     "bodyText": "Paperwork attached for 1514 Jabez under the correct MTX.",
     "attachments": [
         {"id": "a1", "name": "image.png", "contentType": "image/png", "isInline": True, "data": b"png"},
         {"id": "a2", "name": "Participation Agreement-Solar Energy Services.pdf", "contentType": "application/pdf", "isInline": False, "data": PA},
         {"id": "a3", "name": "Detailed Cost-Solar Energy Services.pdf", "contentType": "application/pdf", "isInline": False, "data": COST},
     ]},
    {"id": "m-smart", "subject": "Invoice for Payment for Smart Solutions Inc for 1514 Jabez Suite 106", "receivedDateTime": "2026-10-22T10:00:00Z",
     "sender": "smartsolutionsfast@gmail.com", "internetMessageId": "<x2@gmail>", "bodyText": "Please see attached.",
     "attachments": [{"id": "a4", "name": "Smart Solutions Inc Invoice 1028.pdf", "contentType": "application/pdf", "isInline": False, "data": SMART}]},
    {"id": "m-beacon", "subject": "New payment request from Beacon Lighting Supply - invoice 216en", "receivedDateTime": "2026-10-22T18:46:03Z",
     "sender": "rdeuber@beaconlightingsupply.com", "internetMessageId": "<x3@beacon>",
     "bodyText": "View and pay https://connect.intuit.com/t/scs-v1-abc?cta=viewinvoicenow&locale=en_US Dear Ben",
     "attachments": [{"id": "a5", "name": "QB Logo", "contentType": "image/png", "isInline": False, "data": b"png"}]},
    {"id": "m-noise", "subject": "Lunch?", "receivedDateTime": "2026-10-22T19:00:00Z", "sender": "friend@example.com",
     "bodyText": "menu attached", "attachments": [{"id": "a6", "name": "menu.pdf", "contentType": "application/pdf", "isInline": False, "data": make_pdf(["tacos"])}]},
]


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.env = IntakeEnv()
        self.cfg = self.env.cfg

    def tearDown(self):
        self.env.close()

    def test_outlook_candidates_and_link_requests(self):
        state = State(self.cfg.state_path)
        client = FakeMailClient(MESSAGES)
        links = []
        cands = list(outlook.find_candidates(self.cfg, client, state, datetime(2026, 10, 1, tzinfo=timezone.utc), on_link=links.append))
        self.assertEqual([c.name for c in cands], [
            "Participation Agreement-Solar Energy Services.pdf", "Detailed Cost-Solar Energy Services.pdf",
            "Smart Solutions Inc Invoice 1028.pdf"])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].invoice_number, "216en")
        self.assertTrue(links[0].link.startswith("https://connect.intuit.com/t/scs-v1-abc"))
        self.assertEqual(state.mail_watermark, datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc))
        # second pass downloads nothing new
        again = list(outlook.find_candidates(self.cfg, client, state, datetime(2026, 10, 1, tzinfo=timezone.utc), on_link=links.append))
        self.assertEqual(again, [])
        self.assertEqual(len(links), 1)

    def test_filing_from_mail_lands_per_mtx_and_invoice_is_inferred(self):
        state = State(self.cfg.state_path)
        index = ProjectIndex(self.cfg.projects_root, self.cfg.out_subfolder).rebuild()
        filer = Filer(self.cfg, index, HashCache(self.cfg.hash_cache_path))
        outcomes = [filer.file(c) for c in outlook.find_candidates(self.cfg, FakeMailClient(MESSAGES), state, datetime(2026, 10, 1, tzinfo=timezone.utc))]
        self.assertEqual([o.action for o in outcomes], ["filed", "filed", "filed"])
        self.assertEqual([o.match for o in outcomes], ["confirmed", "confirmed", "inferred"])
        folder = self.cfg.projects_root / "MTX38729390 - solar_energy_services"
        self.assertEqual(sorted(p.name for p in folder.iterdir() if p.is_file()), [
            "Detailed Cost-Solar Energy Services.pdf", "Participation Agreement-Solar Energy Services.pdf",
            "Smart Solutions Inc Invoice 1028.pdf"])
        manifest = read_json(folder / "_intake" / "manifest.json", {})
        inv = [f for f in manifest["files"] if f["file"].startswith("Smart")][0]
        self.assertEqual(inv["match"], "inferred")
        self.assertIn("1514 jabez", inv["matchedOn"])
        self.assertEqual(inv["internetMessageId"], "<x2@gmail>")

    def test_dropfolder_waits_for_settle_and_eof(self):
        good = self.env.drop / "Proposal Detail-Thing.pdf"
        good.write_bytes(make_pdf(["MTX99999999"]))
        old = time.time() - 600
        os.utime(good, (old, old))
        partial = self.env.drop / "half.pdf"
        partial.write_bytes(make_pdf(["MTX99999999"], truncated=True))
        os.utime(partial, (old, old))
        fresh = self.env.drop / "fresh.pdf"
        fresh.write_bytes(make_pdf(["MTX99999999"]))
        names = [c.name for c in dropfolder.find_candidates(self.cfg)]
        self.assertEqual(names, ["Proposal Detail-Thing.pdf"])

    def test_cli_sync_no_mail_then_run_changed_then_status(self):
        good = self.env.drop / "Proposal Detail-Thing.pdf"
        good.write_bytes(make_pdf(["Proposal Detail Report", "MTX99999999 / Thing", "710 Aquahart Rd"]))
        old = time.time() - 600
        os.utime(good, (old, old))
        rc = cli.main(["--config", str(self.cfg.path), "sync", "--no-mail"])
        self.assertEqual(rc, 0)
        self.assertTrue(good.exists(), "drop-folder original is never moved")
        folder = self.cfg.projects_root / "MTX99999999 - thing"
        self.assertTrue((folder / "Proposal Detail-Thing.pdf").exists())
        # second sync: duplicate, nothing new
        self.assertEqual(cli.main(["--config", str(self.cfg.path), "sync", "--no-mail"]), 0)
        self.assertEqual(len([p for p in folder.iterdir() if p.is_file()]), 1)
        rc = cli.main(["--config", str(self.cfg.path), "run-changed"])
        self.assertEqual(rc, 0)
        self.assertTrue((folder / "_reconciliation" / "STATUS.md").exists())
        self.assertEqual(cli.main(["--config", str(self.cfg.path), "run-changed"]), 0)
        self.assertEqual(cli.main(["--config", str(self.cfg.path), "status"]), 0)

    def test_lock_refuses_second_run(self):
        from kce_intake.state import Lock
        with Lock(self.cfg.lock_path):
            rc = cli.main(["--config", str(self.cfg.path), "sync", "--no-mail"])
        self.assertEqual(rc, 3)
        self.assertEqual(cli.main(["--config", str(self.cfg.path), "sync", "--no-mail"]), 0)


if __name__ == "__main__":
    unittest.main()
