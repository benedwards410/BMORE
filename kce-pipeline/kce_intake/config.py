"""Load config/intake.json and resolve every path once."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # the kce-pipeline/ folder
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "intake.json"

DEFAULTS: dict = {
    "projectsRoot": str(PACKAGE_ROOT / "projects"),
    "dropFolders": [],
    "pipelineCommand": ["py", "-m", "kce_pipeline"],
    "pipelineCwd": None,
    "graph": {"clientId": "", "tenantId": "common", "scopes": ["Mail.Read"]},
    "mail": {
        "lookbackDaysFirstRun": 60,
        "overlapMinutes": 10,
        "senderAllowlist": [],
        "filenamePatterns": [],
        "skipAttachments": [],
        "quickbooksLinkSenders": [],
    },
    "match": {"autoFileOnSingleAddressMatch": True},
    "runner": {"outSubfolder": "_reconciliation", "timeoutSeconds": 1800, "maxToolFailuresBeforeHold": 3},
    "inputExtensions": [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"],
}


def local_state_dir() -> Path:
    """Per-user, never-synced folder for the token cache, state and logs.

    Override with KCE_INTAKE_HOME (tests do). On Windows this is
    %LOCALAPPDATA%\\kce_intake, which OneDrive does not sync."""
    base = os.environ.get("KCE_INTAKE_HOME") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "kce_intake"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    raw: dict
    path: Path | None = None

    # ---- paths -----------------------------------------------------------
    @property
    def projects_root(self) -> Path:
        return Path(self.raw["projectsRoot"]).expanduser()

    @property
    def drop_folders(self) -> list[Path]:
        return [Path(p).expanduser() for p in self.raw.get("dropFolders", [])]

    @property
    def pipeline_command(self) -> list[str]:
        return list(self.raw["pipelineCommand"])

    @property
    def pipeline_cwd(self) -> Path:
        cwd = self.raw.get("pipelineCwd")
        return Path(cwd).expanduser() if cwd else PACKAGE_ROOT

    @property
    def unmatched_dir(self) -> Path:
        return self.projects_root / "_unmatched"

    @property
    def needs_manual_dir(self) -> Path:
        return self.projects_root / "_needs_manual"

    @property
    def state_path(self) -> Path:
        return local_state_dir() / "intake_state.json"

    @property
    def hash_cache_path(self) -> Path:
        return local_state_dir() / "hashes.json"

    @property
    def lock_path(self) -> Path:
        return local_state_dir() / "intake.lock"

    @property
    def log_path(self) -> Path:
        return local_state_dir() / "intake.log"

    @property
    def token_cache_path(self) -> Path:
        return local_state_dir() / "token_cache.bin"

    # ---- sections --------------------------------------------------------
    @property
    def input_extensions(self) -> set[str]:
        return {e.lower() for e in self.raw["inputExtensions"]}

    @property
    def mail(self) -> dict:
        return self.raw["mail"]

    @property
    def graph(self) -> dict:
        return self.raw["graph"]

    @property
    def runner(self) -> dict:
        return self.raw["runner"]

    @property
    def match(self) -> dict:
        return self.raw["match"]

    @property
    def out_subfolder(self) -> str:
        return self.runner.get("outSubfolder", "_reconciliation")


def load_config(path: str | os.PathLike | None = None, overrides: dict | None = None) -> Config:
    chosen = Path(path or os.environ.get("KCE_INTAKE_CONFIG") or DEFAULT_CONFIG_PATH)
    raw = dict(DEFAULTS)
    if chosen.exists():
        with open(chosen, encoding="utf-8") as fh:
            loaded = json.load(fh)
        raw = _merge(raw, {k: v for k, v in loaded.items() if not k.startswith("_")})
    if overrides:
        raw = _merge(raw, overrides)
    return Config(raw=raw, path=chosen if chosen.exists() else None)
