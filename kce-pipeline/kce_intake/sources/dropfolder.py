"""Sweep the "Incoming Documents (pipeline)" folders. Files are read in place and
left where they are; the Filer's hash index makes sure each is filed once."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator

from ..config import Config
from ..filer import Candidate

log = logging.getLogger("kce_intake.dropfolder")
SETTLE_SECONDS = 120


def _looks_complete(path: Path, data: bytes) -> bool:
    if not data:
        return False
    if path.suffix.lower() == ".pdf":
        return b"%%EOF" in data[-4096:]
    return True


def find_candidates(cfg: Config, now: float | None = None) -> Iterator[Candidate]:
    now = now or time.time()
    for folder in cfg.drop_folders:
        if not folder.exists():
            log.info("drop folder missing (not synced yet?): %s", folder)
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith((".", "~$")):
                continue
            if path.suffix.lower() not in cfg.input_extensions:
                continue
            try:
                if now - path.stat().st_mtime < SETTLE_SECONDS:
                    continue  # still being written or synced; next run
                data = path.read_bytes()
            except OSError as exc:
                log.warning("cannot read %s: %s", path, exc)
                continue
            if not _looks_complete(path, data):
                log.info("skipping %s for now: file looks incomplete", path.name)
                continue
            yield Candidate(name=path.name, data=data, source="dropfolder",
                            context={"path": str(path), "received": None})
