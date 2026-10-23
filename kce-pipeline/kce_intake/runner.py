"""Run kce_pipeline on every project whose input documents changed since the
last recorded run. The pipeline is a subprocess; this module never imports it.

Per project folder:
  _reconciliation/last_run.json   {inputs: {name: sha256}, ranAt, exitCode, counts, log}
  _reconciliation/STATUS.md       one screen: last run, flag counts, newest report
  _reconciliation/archive/        previous report, kept before each re-run
  _reconciliation/<timestamp>.log pipeline stdout/stderr"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .projects import ProjectIndex, ProjectRecord
from .state import HashCache, State, iso, read_json, utcnow, write_json_atomic

log = logging.getLogger("kce_intake.runner")

EXIT_CLEAN, EXIT_CRITICAL, EXIT_TOOL_FAILURE = 0, 1, 2


@dataclass
class RunResult:
    mtx: str
    exit_code: int
    counts: dict = field(default_factory=dict)
    report: Path | None = None
    log_path: Path | None = None
    skipped: str = ""


def input_snapshot(folder: Path, exts: set[str], cache: HashCache, out_subfolder: str) -> dict[str, str]:
    snap: dict[str, str] = {}
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.suffix.lower() in exts and not file.name.startswith("~$"):
            snap[file.name] = cache.sha256(file)
    return snap


def flag_counts(project_json: Path) -> dict:
    data = read_json(project_json, {})
    counts = {"critical": 0, "warning": 0, "info": 0}
    for flag in data.get("flags", []) or []:
        sev = str(flag.get("severity", "")).lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def newest(out_dir: Path, pattern: str) -> Path | None:
    files = sorted(out_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def write_status(rec: ProjectRecord, out_dir: Path, result: RunResult, inputs: dict[str, str]) -> None:
    verdict = {
        EXIT_CLEAN: "✅ reconciles — no critical flags",
        EXIT_CRITICAL: "🔴 critical flags outstanding — a person must decide",
    }.get(result.exit_code, f"⚠️ pipeline failed (exit {result.exit_code}) — see log")
    lines = [
        f"# {rec.folder.name}",
        "",
        f"**Last run:** {iso(utcnow())}  ",
        f"**Result:** {verdict}  ",
    ]
    if result.counts:
        c = result.counts
        lines.append(f"**Flags:** {c.get('critical', 0)} critical · {c.get('warning', 0)} warning · {c.get('info', 0)} info  ")
    if result.report:
        lines.append(f"**Report:** `{result.report.name}`  ")
    if result.log_path:
        lines.append(f"**Log:** `{result.log_path.name}`  ")
    lines += ["", "## Inputs", ""] + [f"- `{name}`" for name in sorted(inputs)] + [
        "", "_Written by kce_intake. Dollars in the report are INTERNAL._", ""]
    (out_dir / "STATUS.md").write_text("\n".join(lines), encoding="utf-8")


def run_project(cfg: Config, rec: ProjectRecord, cache: HashCache, state: State,
                force: bool = False, dry_run: bool = False) -> RunResult | None:
    """Run the pipeline if inputs changed. None = nothing to do."""
    out_dir = rec.folder / cfg.out_subfolder
    last = read_json(out_dir / "last_run.json", {})
    inputs = input_snapshot(rec.folder, cfg.input_extensions, cache, cfg.out_subfolder)
    if not inputs:
        return None
    if not force and last.get("inputs") == inputs:
        return None
    record = state.run_record(rec.mtx)
    failures = int(record.get("toolFailures", 0))
    limit = int(cfg.runner.get("maxToolFailuresBeforeHold", 3))
    if not force and failures >= limit:
        return RunResult(rec.mtx, EXIT_TOOL_FAILURE, skipped=f"held after {failures} tool failures; run with --all --mtx {rec.mtx} to retry")
    if dry_run:
        return RunResult(rec.mtx, EXIT_CLEAN, skipped="dry run: would run pipeline")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    previous = newest(out_dir, "*.reconciliation.md")
    if previous:
        archive = out_dir / "archive"
        archive.mkdir(exist_ok=True)
        shutil.copy2(previous, archive / f"{stamp}-{previous.name}")

    cmd = cfg.pipeline_command + [str(rec.folder), "--out", str(out_dir)]
    log_path = out_dir / f"{stamp}.log"
    log.info("running pipeline for %s", rec.folder.name)
    try:
        proc = subprocess.run(cmd, cwd=str(cfg.pipeline_cwd), capture_output=True, text=True,
                              timeout=int(cfg.runner.get("timeoutSeconds", 1800)))
        exit_code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        exit_code, output = EXIT_TOOL_FAILURE, f"timed out after {exc.timeout}s\n{exc.stdout or ''}{exc.stderr or ''}"
    except OSError as exc:
        exit_code, output = EXIT_TOOL_FAILURE, f"could not start pipeline: {exc}\ncommand: {cmd}"
    log_path.write_text(output, encoding="utf-8", errors="replace")

    project_json = newest(out_dir, "*.project.json")
    counts = flag_counts(project_json) if project_json else {}
    result = RunResult(rec.mtx, exit_code, counts, newest(out_dir, "*.reconciliation.md"), log_path)

    if exit_code in (EXIT_CLEAN, EXIT_CRITICAL):
        record["toolFailures"] = 0
        write_json_atomic(out_dir / "last_run.json", {
            "inputs": inputs, "ranAt": iso(utcnow()), "exitCode": exit_code,
            "counts": counts, "log": log_path.name,
            "report": result.report.name if result.report else None,
        })
    else:
        record["toolFailures"] = failures + 1
        record["lastFailureLog"] = str(log_path)
    record["lastExit"] = exit_code
    record["lastRanAt"] = iso(utcnow())
    state.set_run_record(rec.mtx, record)
    write_status(rec, out_dir, result, inputs)
    return result


def run_changed(cfg: Config, index: ProjectIndex, cache: HashCache, state: State,
                force: bool = False, dry_run: bool = False, only_mtx: str | None = None) -> tuple[int, list[RunResult]]:
    results: list[RunResult] = []
    for mtx, rec in sorted(index.records.items()):
        if only_mtx and mtx != only_mtx:
            continue
        result = run_project(cfg, rec, cache, state, force=force, dry_run=dry_run)
        if result:
            results.append(result)
    worst = EXIT_CLEAN
    for r in results:
        if r.skipped and r.exit_code == EXIT_CLEAN:
            continue
        if r.exit_code >= EXIT_TOOL_FAILURE:
            worst = EXIT_TOOL_FAILURE
        elif r.exit_code == EXIT_CRITICAL and worst == EXIT_CLEAN:
            worst = EXIT_CRITICAL
    return worst, results
