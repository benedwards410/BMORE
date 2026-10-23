# Backlog — improvements to the intake pipeline

Written 2026-09-09. Each item is self-contained: why it matters, what to change,
which files, and how to know it's done. Nothing here is required for the tool to
work today — these are quality-of-life and safety improvements found while
running the first two real projects.

## Status

| # | Item | Status |
|---|---|---|
| 1 | Write outputs into the project folder | **DONE 2026-10-23** |
| 2 | A real `projects/` root | **DONE 2026-10-23** |
| 3 | Refuse to read half-synced OneDrive files | **DONE 2026-09-09** |
| 4 | "What changed since last run" diff | **DONE 2026-09-09** |
| 5 | Fix the launcher's exit code | **DONE 2026-10-23** |

> ⚠️ **Folder split — resolved 2026-10-23.**
> The working code used to live in `KCE -Document-Pipeline (b)`, while this
> file sat alone in `KCE -Document-Pipeline` after OneDrive split the folder.
> The single place is now `kce-pipeline/` in the BMORE git repo (public):
> code, config, docs and tests are versioned there; the regression fixtures and
> the extraction cache stay in OneDrive and are git-ignored.

Hand this file to Claude Code (or any developer) and say "do item 3" and it
should have enough to work from without re-reading the whole task outline.

---

## Where things stand today

```
kce-pipeline/                 (in the BMORE repo; was KCE -Document-Pipeline (b))
├── RUN A PROJECT.cmd      drag a project folder onto this
├── CHECK SETUP.cmd        double-click diagnostics
├── RUN INTAKE.cmd         sync + run-changed, for the scheduler
├── QUICKSTART.md          one-page guide for the team
├── kce.cmd                CLI wrapper (py + correct working directory)
├── BACKLOG.md             this file
├── README.md              intake + how the two packages fit
├── PIPELINE_README.md     the pipeline's own README
├── config/                canonical_fixtures.json, settings.json,
│                          standard_piece_rates.json, intake.example.json
├── kce_pipeline/          extract, normalize, transform, checks, report,
│                          diff (item 4), run, cli
├── kce_intake/            Outlook + drop-folder intake, files per MTX
├── extraction_cache/      per-document replay, keyed by SHA-256 of file bytes
│                          (git-ignored — lives in OneDrive only)
├── regression_fixtures/   the two frozen known-good jobs (git-ignored)
│   ├── steves_pools/      6 files,  MTX79857647
│   └── Bob Bell/          10 files, MTX20616192
├── projects/              live jobs, one "MTX… - slug" folder each (git-ignored)
│   └── <job>/_reconciliation/   that job's reports + history   <-- item 1
├── tests/                 79 pipeline + 30 intake tests
└── task/                  original task outline
```

There is no `pipeline/` level any more: `kce_pipeline/`, `config/` and
`extraction_cache/` sit directly in `kce-pipeline/`, and outputs live with each
project rather than in a shared `out/`.

**Two invariants that must never break.** Any change must keep these exact:

| Project | `modeledCosts[]` total | Must equal |
|---|---|---|
| Steve's Pools | **$7,609.83** | the report's own SubTotals |
| Bob Bell | **$181,745.89** | the report's own Lighting Totals |

Run before and after every change:

```bash
py -m unittest discover -s tests -q
```

79 tests, all passing. Both projects also replay offline with `--backend cache`,
so regression checks cost nothing.

---

## 1. Write outputs into the project folder  ✅ DONE

**Why.** Results currently land in `pipeline/out/`, nowhere near the documents
they describe. Worse, the filename is derived from the project name
(`slugify(project.name)`), so two jobs with similar names silently overwrite each
other — and the second run gives no warning that it clobbered the first.

**What to do.** Default the output directory to the project folder itself, so the
report sits beside the PDFs it was built from. Keep `--out` for anyone who wants
the old behaviour, and keep a copy in `pipeline/out/` only if that turns out to
be useful for the regression runs.

Add a timestamp or a run counter so a re-run never destroys the previous result
without asking. Reconciliation reports are working documents people annotate —
losing one to an accidental re-run would be a real loss.

**Files.** `pipeline/kce_pipeline/cli.py` — `out_dir` defaults around the
`args.out or (base_dir / "out")` line, and the `slugify()` filename construction
just below it.

**Watch out.** Project folders live under OneDrive. Writing there means the
outputs sync, which is good for sharing but means two people running the same job
at once could conflict. Consider writing to a `_reconciliation/` subfolder inside
the project folder rather than dropping files loose among the source documents.

**Done when.** Running a project writes its report next to that project's
documents; running it twice does not silently destroy the first report; and the
regression runs for both known-good projects still produce their invariant
totals.

### ✅ BUILT 2026-10-23

`--out` now defaults to `<project folder>/_reconciliation/` (`default_out_dir()`
in `kce_pipeline/cli.py`) — a subfolder, so the source PDFs stay uncluttered,
discovery never reads a report back in as an input, and it is the same folder
`kce_intake` already passes with `--out` and reads the newest report from.

Every run is stamped: `<slug>.<YYYYMMDD-HHMMSS>.project.json` and
`<slug>.<YYYYMMDD-HHMMSS>.reconciliation.md` (`output_paths()`). Two runs inside
one second get `_2`, `_3`… appended rather than clobbering each other, and the
underscore keeps a plain name sort in run order. Nothing is ever overwritten;
the previous report stays exactly where it was.

Run history (item 4) moved beside the outputs: `<out>/history/<slug>/`, still
pruned to the last 20. Snapshots recorded earlier under `<pipeline>/out/history/`
are read once, when the new location is still empty, so the first run after the
move keeps its "since last run" diff.

`--out DIR` still works and uses the same stamped names, so the old shared-folder
behaviour is one flag away. Intake is untouched: `runner.py` keeps archiving the
previous report before each run (now a belt-and-braces copy) and picks the newest
`*.project.json` / `*.reconciliation.md` by modification time, which the stamped
names satisfy. 4 tests in `TestOutputLocation`; both invariant totals unchanged.

---

## 2. A real `projects/` root instead of `test_fixtures/`  ✅ DONE

**Why.** Bob Bell is a live job with real customer financial documents, and it is
currently filed under a folder literally named "test fixtures". Anyone new to
this will either mistake real jobs for test data or, worse, mistake test data for
a real job. The two need to be separate places.

**What to do.** Create `projects/` for real work. Keep the two known-good jobs as
a frozen regression set — either leave them where they are or move them somewhere
explicitly named (`regression_fixtures/`). The important part is that a person
browsing for a real job never lands in the test set.

**Files.** `pipeline/tests/test_pipeline.py` has `FIXTURES = BASE.parent /
"test_fixtures" / "steves_pools"` near the top, and the `TestInventoryAndCredits`
and `TestEndToEnd` classes both use it. `QUICKSTART.md` mentions folder layout.
No pipeline code hardcodes these paths — the folder is always passed in — so this
is mostly a move plus a test-constant update.

**Watch out.** The extraction cache is keyed by SHA-256 of file *contents*, not by
path, so moving folders costs nothing and invalidates nothing. Moving files is
safe.

**Done when.** Real projects and regression fixtures live in visibly different
places, and all 79 tests still pass.

### ✅ BUILT 2026-10-23

`test_fixtures/` is now `regression_fixtures/` (`FIXTURES = BASE /
"regression_fixtures" / "steves_pools"` in `tests/test_pipeline.py`), and live
jobs go under `projects/`, one `MTX… - slug` folder each, which is where
`kce_intake` files documents. Both are git-ignored — the repo is public — so a
new machine gets them from OneDrive, and the extraction cache (keyed by content,
not path) needs nothing re-read. `QUICKSTART.md`, `PIPELINE_README.md` and the
tree above describe the new layout. 79 pipeline tests still pass.

---

## 3. Refuse to read half-synced OneDrive files  ✅ DONE

**Why.** These folders sync. OneDrive can present a file that is still uploading,
or an online-only placeholder that has never been downloaded. Either can be read
as a truncated or empty PDF. The extraction would then quietly return fewer rows
than the document actually has — and because the model returns *something*, no
error is raised.

The SubTotals cross-check would catch this on a Detailed Cost Report (that is
exactly how the missing Miscellaneous table was found). But it would **not** catch
a truncated supplier or contractor invoice, because nothing cross-checks those
against a stated total. That is a silent wrong answer, which is the worst
possible failure for this tool.

**What to do.** Add a pre-flight check before the extraction pass: for every input
file, confirm it is fully materialised locally and not a placeholder. On Windows
this means checking the file attributes for the offline / recall-on-open flags
(`FILE_ATTRIBUTE_OFFLINE`, `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`,
`FILE_ATTRIBUTE_RECALL_ON_OPEN`) — readable from Python via `ctypes` and
`GetFileAttributesW`, no new dependency needed.

Also worth checking the file is non-trivially sized and that its bytes start with
`%PDF`, which catches truncation and outright corruption cheaply.

Treat a failure as a skip-and-flag, never a crash — the outline is explicit that
one bad file must not abort a batch (§3).

**Files.** `pipeline/kce_pipeline/run.py` — the discovery/read loop in
`run_batch()`, before `backend.read(path)` is called. A helper in
`pipeline/kce_pipeline/extract.py` alongside `file_digest()` would fit naturally.

**Done when.** A placeholder or partially-synced file produces a clear warning
flag naming the file and telling the user to wait for sync, the rest of the batch
still processes, and a fully-synced file is unaffected.

### ✅ BUILT 2026-09-09

`file_readiness()` in `kce_pipeline/extract.py`, called from the read loop in
`run_batch()` **before** any API call is spent. Checks file size, the `%PDF`
header, and the `%%EOF` trailer, and reports OneDrive placeholder attributes.

A rejected file raises a **critical** flag, not a warning — its data is missing
from the report entirely, which is a bigger deal than an unreadable extra file.
The batch continues either way. 6 tests in `TestFileReadiness`.

Two things learned while building it:

- Cloud placeholder attributes turned out to be **advisory, not fatal**. Windows
  recalls a dehydrated file transparently, so refusing to read one would have
  been a false positive. They are reported as `info` only.
- The `%%EOF` trailer check is what actually catches truncation, and it is
  content-based rather than filesystem-based — so it also catches a corrupt file
  that has nothing to do with OneDrive.

---

## 4. A "what changed since last run" diff  ✅ DONE

**Why.** Jobs are reconciled repeatedly as invoices arrive. The second time you
run a project, the useful question is not "what does the whole report say" but
"what moved". Right now you get the full report again and have to spot the
difference by eye — across a report with 20-plus flags, that will not happen
reliably.

**What to do.** Save each run's project JSON with a timestamp, then compare
against the most recent previous run and emit a short "Changes since
<timestamp>" section at the top of the report:

- flags raised that were not there before
- flags that have cleared
- quantities that moved (ordered / approved / installed, per fixture type)
- cost totals that moved
- documents added to or removed from the batch

Keep it short. The point is a five-line summary someone reads in ten seconds,
not another table.

**Files.** New module, e.g. `pipeline/kce_pipeline/diff.py`, called from
`run_batch()` or `cli.py` once the project dict is assembled. Render at the top of
`build_report()` in `pipeline/kce_pipeline/report.py`. Depends on item 1 deciding
where historical runs are stored.

**Watch out.** Flag messages contain dollar amounts and quantities, so comparing
raw message strings will report spurious changes. Compare on something stable —
severity plus `relatedFixtureType` plus the `[§x.y]` rule tag — rather than the
full text.

**Done when.** Re-running an unchanged project reports "no changes since last
run", and adding one new invoice to a folder produces a diff naming just what
that invoice changed.

### ✅ BUILT 2026-09-09

`kce_pipeline/diff.py` — `snapshot()`, `compare()`, `render()`. History is kept
at `pipeline/out/history/<slug>/<timestamp>.json`, last 20 runs, pruned
automatically. *(2026-10-23: item 1 moved it to `<project>/_reconciliation/history/<slug>/`;
the old location is read once if the new one is still empty.)* Rendered at the top of the report and summarised in the console
as a "Since last run" line.

Comparison keys on `(severity, rule tag, fixtureType)` exactly as planned, so a
dollar figure moving inside a flag message does not register as a change — there
is a test that pins this.

The storage location was chosen so it does **not** depend on item 1; moving
outputs later will not disturb the history.

Verified end to end by removing a document and truncating another, then
restoring both:

```
- 📄 Document added: `Bob Bell Ford Credit Calculation.pdf`
- 🔢 Sensor (all tiers) — installed — → 419
- 💵 Credits total $0.00 → $838.00
- ⚠️ New warning flag [§8.3]
- ✅ Cleared critical flag [§3]
```

5 tests in `TestRunDiff`.

---

## 5. Fix the launcher's exit code (cosmetic)  ✅ DONE

**Why.** `RUN A PROJECT.cmd` returns **255** instead of **1** when run
non-interactively, because the trailing `pause` gets EOF when there is no console
input. Harmless for double-click and drag-and-drop — which is all anyone does
today — but it means the launcher cannot be used in a scheduled task or script
until it reports honestly.

The convention the Python CLI already follows, and which any automation should
rely on:

| Code | Meaning |
|---|---|
| 0 | ran fine, no critical flags |
| 1 | ran fine, critical flags outstanding — a person must decide |
| other | the tool itself failed |

**What to do.** Capture `%ERRORLEVEL%` before `pause` (already done — it is in
`RESULT`), and either skip the `pause` when there is no interactive console or
make sure `exit /b %RESULT%` is not overwritten by `pause`'s own status. Simplest
fix: pass a `--no-pause` switch through, or test for interactivity before pausing.

**Files.** `RUN A PROJECT.cmd`, the last few lines. `CHECK SETUP.cmd` has the same
pattern and probably the same issue.

**Done when.** `RUN A PROJECT.cmd <folder>` returns 0 or 1 matching the Python
CLI, and double-clicking still holds the window open so the user can read the
result.

### ✅ BUILT 2026-10-23

`RUN A PROJECT.cmd` and `CHECK SETUP.cmd` route every exit through one
`:finish` label. The result is captured in `RESULT` first, and `pause` runs only
when a person is there to see it — both must hold:

- the script's own name appears in `CMDCMDLINE` (double-click / drag-and-drop
  put it there; an open console window does not), and
- `timeout /t 0` succeeds — it fails when stdin is redirected or absent, which
  is exactly the case where `pause` used to hit end-of-input and kill cmd before
  `exit /b` ran.

`--no-pause` as the last argument, or `KCE_NO_PAUSE=1`, skips the pause outright
for a scheduler that runs with a hidden console. Launcher-side failures (no
Python, no folder given, folder missing) now return **2**, not 1, so they are
never mistaken for "critical flags outstanding". `kce.cmd` never paused and is
unchanged. `.gitattributes` keeps every `*.cmd` CRLF on checkout.

Written in a Linux session, so the one thing still owed is a run on a Windows
box: `cmd /c ""RUN A PROJECT.cmd" "<folder>" < nul" & echo %ERRORLEVEL%` should
print 0 or 1 (never 255), and a double-click must still hold the window.

---

## Ordering suggestion

**3 first** — it is the only item on this list that prevents a *wrong answer*
rather than an inconvenience. Everything else is comfort.

Then **1**, since item 4 depends on where outputs live. Then **2** and **4**.
Item **5** is five minutes whenever someone is in that file anyway.
