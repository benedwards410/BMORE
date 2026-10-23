"""A throwaway projects root + state dir + config for one test."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from kce_intake.config import Config, load_config

HELPERS = Path(__file__).resolve().parent


class IntakeEnv:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects = self.root / "projects"
        self.drop = self.root / "drop"
        self.projects.mkdir()
        self.drop.mkdir()
        self._old_home = os.environ.get("KCE_INTAKE_HOME")
        os.environ["KCE_INTAKE_HOME"] = str(self.root / "home")
        self.cfg: Config = load_config(HELPERS.parent.parent / "config" / "intake.json", overrides={
            "projectsRoot": str(self.projects),
            "dropFolders": [str(self.drop)],
            "pipelineCommand": [sys.executable, "-I", str(HELPERS / "fake_pipeline.py")],
            "pipelineCwd": str(self.root),
            "graph": {"clientId": "test", "tenantId": "common"},
        })
        # A config file of its own so `cli.main(["--config", ...])` sees the same paths.
        self.config_path = self.root / "intake.json"
        self.config_path.write_text(json.dumps(self.cfg.raw, indent=2), encoding="utf-8")
        self.cfg.path = self.config_path

    def close(self):
        if self._old_home is None:
            os.environ.pop("KCE_INTAKE_HOME", None)
        else:
            os.environ["KCE_INTAKE_HOME"] = self._old_home
        self.tmp.cleanup()

    def project_dir(self, name: str) -> Path:
        path = self.projects / name
        path.mkdir(parents=True, exist_ok=True)
        return path
