"""Run state (mail watermark, seen attachments, per-project run records),
the hash cache, and the lock that stops two syncs overlapping."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class State:
    """intake_state.json — small, local, never synced."""

    SEEN_RETENTION_DAYS = 45

    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path, {})
        self.data.setdefault("mailWatermark", None)
        self.data.setdefault("seenAttachments", {})
        self.data.setdefault("runs", {})

    def save(self) -> None:
        self._prune_seen()
        write_json_atomic(self.path, self.data)

    # ---- mail ------------------------------------------------------------
    @property
    def mail_watermark(self) -> datetime | None:
        value = self.data.get("mailWatermark")
        return parse_iso(value) if value else None

    def advance_mail_watermark(self, received: datetime) -> None:
        current = self.mail_watermark
        if current is None or received > current:
            self.data["mailWatermark"] = iso(received)

    def seen_attachment(self, key: str) -> bool:
        return key in self.data["seenAttachments"]

    def mark_attachment(self, key: str, received: datetime) -> None:
        self.data["seenAttachments"][key] = iso(received)

    def _prune_seen(self) -> None:
        cutoff = utcnow() - timedelta(days=self.SEEN_RETENTION_DAYS)
        seen = self.data["seenAttachments"]
        for key in [k for k, v in seen.items() if parse_iso(v) < cutoff]:
            del seen[key]

    # ---- runs ------------------------------------------------------------
    def run_record(self, mtx: str) -> dict:
        return self.data["runs"].setdefault(mtx, {})

    def set_run_record(self, mtx: str, record: dict) -> None:
        self.data["runs"][mtx] = record


class HashCache:
    """sha256 per file keyed by (path, size, mtime) so a 20 MB PDF is hashed once."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = read_json(path, {})
        self.dirty = False

    def sha256(self, file: Path) -> str:
        stat = file.stat()
        key = str(file)
        entry = self.data.get(key)
        if entry and entry.get("size") == stat.st_size and entry.get("mtime") == stat.st_mtime:
            return entry["sha256"]
        digest = sha256_file(file)
        self.data[key] = {"size": stat.st_size, "mtime": stat.st_mtime, "sha256": digest}
        self.dirty = True
        return digest

    def save(self) -> None:
        if self.dirty:
            write_json_atomic(self.path, self.data)
            self.dirty = False


class Lock:
    """PID lock file. A lock older than stale_hours is considered abandoned."""

    def __init__(self, path: Path, stale_hours: float = 2.0):
        self.path = path
        self.stale_hours = stale_hours
        self.held = False

    def acquire(self) -> bool:
        if self.path.exists():
            age_hours = (time.time() - self.path.stat().st_mtime) / 3600
            if age_hours < self.stale_hours:
                return False
            self.path.unlink(missing_ok=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {iso(utcnow())}\n")
        self.held = True
        return True

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"another intake run holds {self.path}")
        return self

    def __exit__(self, *exc):
        self.release()
