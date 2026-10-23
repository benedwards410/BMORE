# KCE Document Pipeline + Intake

Two Python packages that live together:

| Package | Job | Status in this repo |
|---|---|---|
| `kce_pipeline` | One project folder of PDFs → `*.project.json` + `*.reconciliation.md` (flag, don't overwrite) | In the repo since 2026-10-23 — fixtures and cache stay in OneDrive, see Step 0 |
| `kce_intake` | Finds the PDFs in Outlook and the drop folder, files them per MTX, runs the pipeline when a folder changes | Built and tested here |

```
Outlook (Mail.Read)        "Incoming Documents (pipeline)"        Beacon QuickBooks link
 Matrix / Docusign /         drop folder (OneDrive-synced)         (headless Chromium, best effort)
 contractor emails                   │                                      │
        └───────────────┬────────────┴──────────────────────────────────────┘
                        ▼
              py -m kce_intake sync          MTX from the PDF text → confirmed
                        │                    MTX from the email, or a site-address match → inferred
                        ▼                    anything else → _unmatched/<date>/ + WHY.md
   <projectsRoot>/MTX######## - <slug>/
        Participation Agreement-….pdf  Proposal Detail-….pdf  …invoices…
        _intake/manifest.json          where each file came from, sha256, match label
        _reconciliation/STATUS.md      last run, flag counts, newest report
                        │
                        ▼
              py -m kce_intake run-changed   runs kce_pipeline only where inputs changed
```

Intake only ever **adds copies**. It never edits, moves or deletes a source document, never touches
HubSpot, DocuSign or a tracker, and never puts dollar amounts or email bodies in its manifests or logs.

---

## Step 0 — the pipeline source (done 2026-10-23)

The pipeline source could not be pulled through the SharePoint connector (it is read-only and serves
`.py` files as binary), so it was copied by hand from the OneDrive folder
`KeyElectric-Operational → KCE -Document-Pipeline (b)` — the **(b)** copy was the good one. The layout
here is flatter than OneDrive's: `kce_pipeline/`, `config/`, `tests/` and `extraction_cache/` sit
directly in `kce-pipeline/`, with no `pipeline/` level, and the launchers assume that.

**This repo is public.** `.gitignore` keeps `regression_fixtures/`, `test_fixtures/`, `extraction_cache/`
and every `projects/` folder out of git: real project documents, and the cache (which holds transcriptions
of them), live in OneDrive only. On a new machine, copy them in from OneDrive once:

```
test_fixtures/steves_pools/   → regression_fixtures/steves_pools/   (6 files)
test_fixtures/Bob Bell/       → regression_fixtures/Bob Bell/       (10 files)
pipeline/extraction_cache/    → extraction_cache/                  (15 entries, keyed by file content)
```

Then, from `kce-pipeline/`:

```bat
py -m unittest discover -s tests -q
```

Expect 83 pipeline + 30 intake tests passing. The two invariants that must never move, replayed offline
with `--backend cache`: Steve's Pools `modeledCosts` total **$7,609.83**; Bob Bell **$181,745.89**.

BACKLOG items **1** (reports into `<project>/_reconciliation/`, stamped per run, history beside them),
**2** (`regression_fixtures/` + `projects/`) and **5** (launcher exit codes) were done on 2026-10-23;
item 5 still wants one run on a Windows box, see `BACKLOG.md`.

---

## Install

```bat
cd kce-pipeline
copy config\intake.example.json config\intake.json      :: then edit the paths; intake.json is git-ignored
py -m pip install -r requirements-intake.txt
py -m pip install anthropic                 :: pipeline, if not already
rem Optional, for Beacon invoices from the QuickBooks link:
py -m pip install playwright && py -m playwright install chromium
```

### One-time: Microsoft 365 app registration

Intake reads mail through Microsoft Graph with the signed-in user's own permission (`Mail.Read`,
delegated). It needs an app registration in Entra ID:

1. Entra admin center → App registrations → **New registration**. Name `KCE Intake`, single tenant,
   no redirect URI.
2. Authentication → *Allow public client flows* → **Yes**.
3. API permissions → Microsoft Graph → Delegated → **Mail.Read** → *Grant admin consent* if the tenant
   requires it (the Claude connector was granted the same scope, so there is precedent).
4. Copy the **Application (client) ID** and **Directory (tenant) ID** into `config/intake.json → graph`.

No client secret exists. Nothing in the repo or under OneDrive holds a credential: the sign-in token is
cached at `%LOCALAPPDATA%\kce_intake\token_cache.bin`, DPAPI-protected.

Files are **not** written through Graph. Intake writes into the OneDrive-synced folder on disk and the
OneDrive client uploads — so no Files/Sites write permission is ever requested.

---

## Config: `config/intake.json` (copied from `intake.example.json`)

| Key | Meaning |
|---|---|
| `projectsRoot` | The synced folder that holds one `MTX… - slug` folder per project, plus `_unmatched/` and `_needs_manual/` |
| `dropFolders` | Folders a person can save into; swept every sync, originals left in place |
| `pipelineCommand`, `pipelineCwd` | How to run `kce_pipeline` (defaults: `py -m kce_pipeline`, this folder) |
| `graph` | App id, tenant, scopes |
| `mail.senderAllowlist` | Domains/addresses whose PDF attachments are always candidates |
| `mail.filenamePatterns` | Attachment names that are candidates from any sender |
| `mail.quickbooksLinkSenders` | Senders whose link-only mail is fetched with the headless browser |
| `match.autoFileOnSingleAddressMatch` | `true` (Ben's call): an MTX-less invoice with exactly one address match is filed as *inferred* |
| `runner.*` | Output subfolder, timeout, how many tool failures before a project is held |

Per-project hand edits: `<project>/_intake/aliases.txt` — one site address per line — when an invoice
names the site differently from the BGE paperwork ("Vacant 5114 A Dorsey Hall").

---

## Running it

```bat
py -m kce_intake login                     :: once; device-code sign-in
py -m kce_intake sync --since 2026-09-01   :: first backfill; later runs continue from the watermark
py -m kce_intake run-changed --all         :: first pass over every project
py -m kce_intake status                    :: one table: project, last run, critical/warning, inferred
```

`RUN INTAKE.cmd` does `sync` then `run-changed`. Schedule it:

```bat
schtasks /Create /SC MINUTE /MO 15 /TN "KCE Intake" /TR "\"%CD%\RUN INTAKE.cmd\"" /F
```

Leave *Run whether user is logged on or not* **unchecked** (the token lives in the user profile) and keep
*Do not start a new instance* (intake also holds its own lock). Log:
`%LOCALAPPDATA%\kce_intake\intake.log`.

Exit codes follow the pipeline: **0** nothing critical · **1** some project has critical flags
outstanding · **2** intake/pipeline failed · **3** another run was in progress.

### What to look at

- `<projectsRoot>/index.json` — every project, folder and known address.
- `<project>/_reconciliation/STATUS.md` — last run, counts, newest report. The pipeline stamps every
  report (`<slug>.<YYYYMMDD-HHMMSS>.reconciliation.md`) so earlier ones stay put; `archive/` is intake's
  extra copy of the previous one, and `history/` feeds the "Changes since the last run" section.
- `<projectsRoot>/_unmatched/<date>/WHY.md` — what intake could not place and why. Move the file, delete the line.
- `<projectsRoot>/_needs_manual/*.md` — Beacon links the browser could not turn into a PDF. Download by hand, save into the project (or drop) folder, delete the note.

### How a file gets placed

| Evidence | Label | Where |
|---|---|---|
| Exactly one `MTX########` in the PDF text or filename | **confirmed** | that project |
| Exactly one MTX in the email subject, else body | **inferred** (`matchedOn: email subject/body`) | that project |
| No MTX, exactly one project matches a site address | **inferred** (`matchedOn: site address …`) | that project |
| Several MTX, several address matches, or nothing | — | `_unmatched/` |

Suites are respected: `5114 Dorsey Hall Suite A` and `Suite B` are different projects, and an invoice
that only says `5114 Dorsey Hall` is held when both exist.

---

## Tests

```bat
py -m unittest discover -s tests -q                    :: everything
py -m unittest discover -s tests -p "test_intake_*.py" :: intake only (30 tests, no network, no API key)
```

The intake tests build their own tiny PDFs (`tests/helpers/minipdf.py`) and drive a fake pipeline and a
fake mailbox, so no customer document is in the repo.
