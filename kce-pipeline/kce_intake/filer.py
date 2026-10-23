"""Decide where a candidate document goes and put a copy there.

Outcomes:
  filed      copied into <projectsRoot>/<MTX - slug>/, manifest updated
  held       copied into _unmatched/<date>/ with a WHY.md line
  duplicate  the same bytes already exist somewhere we file to — nothing written
  skipped    unsupported file type

Match labels follow the governance rules: an MTX read from the document or its
filename is "confirmed"; an MTX taken only from the email, or a site-address
match, is "inferred" and says so in the manifest."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import Config
from .identify import Address, doc_type_hint, extract_addresses, find_mtx, pdf_text
from .projects import ProjectIndex, ProjectRecord
from .state import HashCache, iso, read_json, sha256_bytes, utcnow, write_json_atomic

NAME_PROJECT_RE = re.compile(
    r"^(?:Participation Agreement|Proposal Detail|Detailed Cost|Customer)-(.+?)(?:\s*rev\w*)?\.pdf$",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    name: str
    data: bytes
    source: str                      # outlook | dropfolder | quickbooks
    context: dict = field(default_factory=dict)
    # context keys used: messageId, attachmentId, subject, sender, received,
    # bodyText, link, path, internetMessageId


@dataclass
class Outcome:
    action: str                      # filed | held | duplicate | skipped
    name: str
    mtx: str | None = None
    path: Path | None = None
    match: str | None = None         # confirmed | inferred
    matched_on: str = ""
    reason: str = ""


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")
    return cleaned or "document"


def _dedupe_name(folder: Path, name: str, digest: str, cache: HashCache) -> Path | None:
    """Return a free path for name, or None when the same bytes already sit there."""
    stem, suffix = Path(name).stem, Path(name).suffix
    attempt = folder / name
    counter = 2
    while attempt.exists():
        if cache.sha256(attempt) == digest:
            return None
        attempt = folder / f"{stem} ({counter}){suffix}"
        counter += 1
    return attempt


class Filer:
    def __init__(self, cfg: Config, index: ProjectIndex, cache: HashCache):
        self.cfg = cfg
        self.index = index
        self.cache = cache
        self.known: set[str] = set()
        self._scan_known()

    # ---- known-bytes index ----------------------------------------------
    def _scan_known(self) -> None:
        root = self.cfg.projects_root
        if not root.exists():
            return
        folders = [rec.folder for rec in self.index.records.values()]
        folders += [self.cfg.unmatched_dir, self.cfg.needs_manual_dir]
        for folder in folders:
            if not folder.exists():
                continue
            for file in folder.rglob("*"):
                if file.is_file() and file.suffix.lower() in self.cfg.input_extensions:
                    if self.cfg.out_subfolder in file.parts or "_intake" in file.parts:
                        continue
                    try:
                        self.known.add(self.cache.sha256(file))
                    except OSError:
                        continue

    # ---- main entry ------------------------------------------------------
    def file(self, cand: Candidate) -> Outcome:
        name = safe_filename(cand.name)
        if Path(name).suffix.lower() not in self.cfg.input_extensions:
            return Outcome("skipped", name, reason="unsupported file type")
        digest = sha256_bytes(cand.data)
        if digest in self.known:
            return Outcome("duplicate", name, reason="same bytes already filed")

        text = pdf_text(cand.data)
        subject = cand.context.get("subject", "") or ""
        body = cand.context.get("bodyText", "") or ""
        hint = doc_type_hint(name, text)

        # Tier 1: MTX in the document itself or its filename -> confirmed.
        tier1 = find_mtx(name) + [m for m in find_mtx(text) if m not in find_mtx(name)]
        tier1 = list(dict.fromkeys(tier1))
        if len(tier1) == 1:
            return self._file_into(cand, name, digest, tier1[0], "confirmed", "document text", hint, text)
        if len(tier1) > 1:
            return self._hold(cand, name, digest, f"document names several MTX numbers: {', '.join(tier1)}", hint)

        # Tier 2: MTX in the email subject, then body -> inferred.
        for label, source in (("email subject", subject), ("email body", body)):
            found = find_mtx(source)
            if len(found) == 1:
                return self._file_into(cand, name, digest, found[0], "inferred", label, hint, text)
            if len(found) > 1:
                return self._hold(cand, name, digest, f"{label} names several MTX numbers: {', '.join(found)}", hint)

        # Tier 3: site address -> inferred, only on exactly one match.
        addresses = (extract_addresses(name, loose=True) | extract_addresses(subject, loose=True)
                     | extract_addresses(text) | extract_addresses(body))
        matches = self.index.match_by_address(addresses) if self.cfg.match.get("autoFileOnSingleAddressMatch", True) else []
        if len(matches) == 1:
            which = ", ".join(sorted(str(a) for a in addresses if matches[0].matches({a})))
            return self._file_into(cand, name, digest, matches[0].mtx, "inferred", f"site address {which}", hint, text)
        if len(matches) > 1:
            names = ", ".join(sorted(m.mtx for m in matches))
            return self._hold(cand, name, digest, f"address matches several projects: {names}", hint)
        if addresses:
            seen = ", ".join(sorted(str(a) for a in addresses))
            return self._hold(cand, name, digest, f"no MTX, and no project matches address(es) {seen}", hint)
        return self._hold(cand, name, digest, "no MTX number and no site address found", hint)

    # ---- outcomes --------------------------------------------------------
    def _file_into(self, cand: Candidate, name: str, digest: str, mtx: str, match: str,
                   matched_on: str, hint: str, text: str) -> Outcome:
        record = self.index.find(mtx) or self.index.ensure_folder(mtx, self._name_hint(name))
        dest = _dedupe_name(record.folder, name, digest, self.cache)
        if dest is None:
            self.known.add(digest)
            return Outcome("duplicate", name, mtx=mtx, reason="already in project folder")
        record.folder.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(cand.data)
        self.known.add(digest)
        self._append_manifest(record, dest, digest, cand, hint, match, matched_on)
        if match == "confirmed":
            observed = extract_addresses(text) | extract_addresses(name)
            if observed:
                self.index.record_observed_addresses(record, observed)
        return Outcome("filed", name, mtx=mtx, path=dest, match=match, matched_on=matched_on)

    def _hold(self, cand: Candidate, name: str, digest: str, reason: str, hint: str) -> Outcome:
        day_dir = self.cfg.unmatched_dir / utcnow().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        dest = _dedupe_name(day_dir, name, digest, self.cache)
        if dest is None:
            self.known.add(digest)
            return Outcome("duplicate", name, reason="already held")
        dest.write_bytes(cand.data)
        self.known.add(digest)
        why = day_dir / "WHY.md"
        header = "" if why.exists() else "# Held for a person to file\n\nMove the file into the right `MTX… - …` folder and delete the line.\n\n"
        line = (f"- `{dest.name}` — {reason} — from {cand.source}"
                f"{': ' + cand.context['subject'] if cand.context.get('subject') else ''}"
                f"{' <' + cand.context['sender'] + '>' if cand.context.get('sender') else ''}\n")
        with open(why, "a", encoding="utf-8") as fh:
            fh.write(header + line)
        self._append_manifest(None, dest, digest, cand, hint, None, reason, day_dir / "manifest.json")
        return Outcome("held", name, path=dest, reason=reason)

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _name_hint(name: str) -> str:
        match = NAME_PROJECT_RE.match(name)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _append_manifest(record: ProjectRecord | None, dest: Path, digest: str, cand: Candidate,
                         hint: str, match: str | None, matched_on: str, path: Path | None = None) -> None:
        manifest_path = path or (record.intake_dir / "manifest.json")
        manifest = read_json(manifest_path, {"files": []})
        if record is not None:
            manifest["mtx"] = record.mtx
        received = cand.context.get("received")
        manifest["files"].append({
            "file": dest.name,
            "sha256": digest,
            "source": cand.source,
            "messageId": cand.context.get("messageId"),
            "internetMessageId": cand.context.get("internetMessageId"),
            "attachmentId": cand.context.get("attachmentId"),
            "subject": cand.context.get("subject"),
            "sender": cand.context.get("sender"),
            "received": received if isinstance(received, str) or received is None else iso(received),
            "originalPath": cand.context.get("path"),
            "link": cand.context.get("link"),
            "filedAt": iso(utcnow()),
            "docTypeHint": hint,
            "match": match,
            "matchedOn": matched_on,
        })
        write_json_atomic(manifest_path, manifest)
