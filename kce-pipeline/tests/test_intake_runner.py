import unittest

from helpers.intake_env import IntakeEnv
from helpers.minipdf import make_pdf
from kce_intake.projects import ProjectIndex
from kce_intake.runner import EXIT_CLEAN, EXIT_CRITICAL, EXIT_TOOL_FAILURE, run_changed
from kce_intake.state import HashCache, State, read_json


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.env = IntakeEnv()
        self.cfg = self.env.cfg
        self.folder = self.env.project_dir("MTX11111111 - fake_project")
        (self.folder / "Proposal Detail-Fake.pdf").write_bytes(make_pdf(["MTX11111111"]))

    def tearDown(self):
        self.env.close()

    def run_it(self, **kw):
        index = ProjectIndex(self.cfg.projects_root, self.cfg.out_subfolder).rebuild()
        state = State(self.cfg.state_path)
        cache = HashCache(self.cfg.hash_cache_path)
        worst, results = run_changed(self.cfg, index, cache, state, **kw)
        state.save(); cache.save()
        return worst, results

    def test_runs_once_then_only_on_change(self):
        worst, results = self.run_it()
        self.assertEqual(worst, EXIT_CLEAN)
        self.assertEqual(len(results), 1)
        out = self.folder / "_reconciliation"
        self.assertTrue((out / "fake_project.reconciliation.md").exists())
        self.assertTrue((out / "STATUS.md").exists())
        last = read_json(out / "last_run.json", {})
        self.assertEqual(set(last["inputs"]), {"Proposal Detail-Fake.pdf"})
        self.assertEqual(last["counts"]["warning"], 1)

        worst, results = self.run_it()
        self.assertEqual(results, [])

        (self.folder / "CRITICAL.pdf").write_bytes(make_pdf(["critical doc"]))
        worst, results = self.run_it()
        self.assertEqual(worst, EXIT_CRITICAL)
        self.assertEqual(results[0].counts["critical"], 1)
        self.assertIn("critical flags outstanding", (out / "STATUS.md").read_text(encoding="utf-8"))
        archived = list((out / "archive").iterdir())
        self.assertEqual(len(archived), 1)  # the previous report was kept

    def test_force_and_dry_run(self):
        self.run_it()
        worst, results = self.run_it(dry_run=True, force=True)
        self.assertEqual(results[0].skipped, "dry run: would run pipeline")
        worst, results = self.run_it(force=True)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].skipped)

    def test_tool_failure_is_retried_then_held(self):
        (self.folder / "BOOM.pdf").write_bytes(make_pdf(["boom"]))
        for _ in range(3):
            worst, results = self.run_it()
            self.assertEqual(worst, EXIT_TOOL_FAILURE)
            self.assertEqual(results[0].exit_code, 7)
        self.assertFalse((self.folder / "_reconciliation" / "last_run.json").exists())
        worst, results = self.run_it()
        self.assertIn("held after 3 tool failures", results[0].skipped)
        status = (self.folder / "_reconciliation" / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("pipeline failed (exit 7)", status)
        # fixing the folder clears the hold on an explicit --all
        (self.folder / "BOOM.pdf").unlink()
        worst, results = self.run_it(force=True, only_mtx="MTX11111111")
        self.assertEqual(worst, EXIT_CLEAN)

    def test_ignores_reserved_and_empty_folders(self):
        self.env.project_dir("_unmatched")
        self.env.project_dir("MTX22222222 - empty")
        worst, results = self.run_it()
        self.assertEqual([r.mtx for r in results], ["MTX11111111"])


if __name__ == "__main__":
    unittest.main()
