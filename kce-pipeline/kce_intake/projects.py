"""The project index: MTX → folder, name and every address we have seen for it.

Sources of addresses, in order of trust:
  1. the pipeline's own <slug>.project.json (project.address) — written by the pipeline
  2. _intake/addresses.json — addresses intake observed in MTX-bearing documents
  3. _intake/aliases.txt   — one address per line, hand-edited by a person
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .identify import Address, extract_addresses
from .state import read_json, write_json_atomic

FOLDER_RE = re.compile(r"^(MTX\d{8})(?:\s*-\s*(.*))?$")
RESERVED_PREFIX = "_"


def slugify(text: str, max_len: int = 60) -> str:
    """Same shape the pipeline produces: "Steve's Pools" -> "steve_s_pools"."""
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug[:max_len] or "project"


@dataclass
class ProjectRecord:
    mtx: str
    folder: Path
    name: str = ""
    addresses: set[Address] = field(default_factory=set)

    @property
    def intake_dir(self) -> Path:
        return self.folder / "_intake"

    def matches(self, candidates: set[Address]) -> bool:
        return any(a.compatible(b) for a in self.addresses for b in candidates)


class ProjectIndex:
    def __init__(self, root: Path, out_subfolder: str = "_reconciliation"):
        self.root = root
        self.out_subfolder = out_subfolder
        self.records: dict[str, ProjectRecord] = {}

    # ---- discovery -------------------------------------------------------
    def rebuild(self) -> "ProjectIndex":
        self.records = {}
        if not self.root.exists():
            return self
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or entry.name.startswith(RESERVED_PREFIX):
                continue
            match = FOLDER_RE.match(entry.name)
            if not match:
                continue
            mtx, name = match.group(1), (match.group(2) or "").strip()
            record = ProjectRecord(mtx=mtx, folder=entry, name=name)
            self._load_addresses(record)
            self.records[mtx] = record
        self._write_human_index()
        return self

    def _load_addresses(self, record: ProjectRecord) -> None:
        for project_json in self._project_jsons(record.folder):
            data = read_json(project_json, {})
            project = data.get("project") or {}
            if project.get("address"):
                record.addresses |= extract_addresses(str(project["address"]))
            if project.get("name") and not record.name:
                record.name = str(project["name"])
        observed = read_json(record.intake_dir / "addresses.json", [])
        for item in observed:
            try:
                record.addresses.add(Address.from_dict(item))
            except (KeyError, TypeError, ValueError):
                continue
        aliases = record.intake_dir / "aliases.txt"
        if aliases.exists():
            for line in aliases.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    record.addresses |= extract_addresses(line)

    def _project_jsons(self, folder: Path) -> list[Path]:
        found = list(folder.glob("*.project.json"))
        out_dir = folder / self.out_subfolder
        if out_dir.exists():
            found += list(out_dir.glob("*.project.json"))
        return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)

    def _write_human_index(self) -> None:
        if not self.root.exists():
            return
        data = {
            mtx: {
                "name": rec.name,
                "folder": rec.folder.name,
                "addresses": sorted(str(a) for a in rec.addresses),
            }
            for mtx, rec in sorted(self.records.items())
        }
        try:
            write_json_atomic(self.root / "index.json", data)
        except OSError:
            pass  # read-only or mid-sync; the index is a convenience view

    # ---- lookups ---------------------------------------------------------
    def find(self, mtx: str) -> ProjectRecord | None:
        return self.records.get(mtx)

    def match_by_address(self, addresses: set[Address]) -> list[ProjectRecord]:
        if not addresses:
            return []
        return [rec for rec in self.records.values() if rec.matches(addresses)]

    # ---- mutation --------------------------------------------------------
    def ensure_folder(self, mtx: str, name_hint: str = "") -> ProjectRecord:
        record = self.records.get(mtx)
        if record:
            return record
        slug = slugify(name_hint) if name_hint else ""
        folder = self.root / (f"{mtx} - {slug}" if slug else mtx)
        folder.mkdir(parents=True, exist_ok=True)
        record = ProjectRecord(mtx=mtx, folder=folder, name=name_hint)
        self.records[mtx] = record
        return record

    def record_observed_addresses(self, record: ProjectRecord, addresses: set[Address]) -> None:
        new = addresses - record.addresses
        if not new:
            return
        record.addresses |= new
        path = record.intake_dir / "addresses.json"
        existing = read_json(path, [])
        existing.extend(a.to_dict() for a in sorted(new, key=str))
        write_json_atomic(path, existing)
