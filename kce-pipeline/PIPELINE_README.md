# KCE Document Intake Pipeline

Takes a folder of 2–10 documents belonging to **one** LED retrofit project and
produces a structured project JSON plus a human-readable reconciliation report.

Built to `task/Document_Intake_Pipeline_Task_Outline.md`. Section references
throughout the code and in every flag message (`[§8.5]`, `[§4.4]`, …) point back
to that document.

---

## Running it on a new project

```bash
python -m kce_pipeline "path/to/that_projects_folder"
```

That's the whole interface. Drop the project's PDFs in a folder, point at the
folder. Outputs land in `<folder>/_reconciliation/`, beside the documents they
were built from, and every run carries its own stamp so a re-run never
overwrites the previous report:

- `<project>.<YYYYMMDD-HHMMSS>.project.json` — the §6.1 schema, a drop-in for the ROI tracker
- `<project>.<YYYYMMDD-HHMMSS>.reconciliation.md` — every discrepancy needing a human decision
- `history/<project>/` — one snapshot per run, feeding the "Changes since the last run" section

Useful flags:

```bash
python -m kce_pipeline <folder> --out "C:/somewhere/else"   # choose output dir (same naming)
python -m kce_pipeline <folder> --backend cache             # offline replay
python -m kce_pipeline <folder> --backend api               # force live API
```

Exit code is `1` when any `critical` flag is outstanding, `0` otherwise — so
this can gate an automated workflow later.

**You do not need to re-read the task outline to run a new project.** The rules
live in `config/`, not in prose.

---

## The two extraction backends

Document reading is pluggable. Everything downstream — classification routing,
normalization, accessory grouping, sensor validation, reconciliation, reporting —
is identical either way.

| Backend | When it's used | Needs a key? |
|---|---|---|
| `api` | `ANTHROPIC_API_KEY` is set and `anthropic` is installed | yes |
| `cache` | replays `extraction_cache/<sha256>.json` | no |

`backend: "auto"` (the default in `config/settings.json`) prefers the live API
and silently falls back to the cache.

**To switch on live extraction:**

```bash
pip install anthropic
setx ANTHROPIC_API_KEY "sk-ant-..."
```

`setx` only affects *future* terminals — open a new one, then verify:

```bash
python -m kce_pipeline --check-api
```

That checks the package, the key (printing only its length and last 4 chars),
and makes one ~20-token live call. Never put the key in a `.env` inside this
folder — it lives under OneDrive and would sync to the cloud. A Windows user
environment variable stays on this machine.

Every live read backfills the cache automatically, so any run can later be
replayed offline and deterministically.

The cache is content-addressed by SHA-256 of the file bytes: renaming a document
does not invalidate its entry, and editing one cannot silently reuse a stale one.

> The entries currently in `extraction_cache/` were captured by reading the five
> Steve's Pools PDFs with Claude's native document understanding inside a Claude
> Code session, using the exact prompts in `kce_pipeline/extract.py`. They are
> transcriptions of the source documents, not hand-authored answers — all the
> grouping, summing and checking is done by the code.

---

## Layout

```
kce-pipeline/
├── config/
│   ├── canonical_fixtures.json   ← EDIT THIS to teach new fixture names
│   ├── settings.json             ← tolerances and policy knobs
│   └── standard_piece_rates.json ← KCE's standing rate card
├── kce_pipeline/
│   ├── extract.py      two-pass document reading + both backends + all prompts
│   ├── normalize.py    canonical vocabulary, size classes, defensive parsing
│   ├── transform.py    raw rows → §6.1 arrays (one function per doc type)
│   ├── checks.py       the nine §8 behaviors → flags[]
│   ├── report.py       Markdown reconciliation report
│   ├── diff.py         "what changed since the last run"
│   └── run.py / cli.py orchestration and entry point
├── extraction_cache/   content-addressed extraction replays (git-ignored)
├── regression_fixtures/ the two frozen known-good projects (git-ignored)
└── tests/              79 pipeline tests + the intake suite
```

Outputs are not kept here: each project folder gets its own `_reconciliation/`.

```bash
python -m unittest discover -s tests -v
```

---

## Adding a fixture type

Everything about the vocabulary lives in `config/canonical_fixtures.json` —
adding one is a config edit, never a code change.

1. Add the name to `canonicalTypes`.
2. Add a rule to `rules`. A rule matches when every regex in `all` matches, at
   least one in `any` matches, and none in `none` do. Lower `priority` wins, so
   primary fixtures (10) beat accessories (50) on a string like
   `"Exterior LED 70W Flood, Photocell w/ knuckle"`.
3. If the type is wattage-tiered, add it to `wattageTiers`.
4. If it's an accessory that should be rolled into a parent fixture, add it to
   `componentTypes` **and** `accessoryRules`.

Unmatched names are never invented into a new canonical type — matching goes
exact → rules → fuzzy (`fuzzyMatchThreshold`), and anything below that threshold
raises a `[§6.2]` warning naming the string so you can add a rule.

---

## Policy knobs (`config/settings.json`)

| Setting | Default | Effect |
|---|---|---|
| `quantityTolerance` | `0` | Difference allowed between ordered/approved/installed before a `critical` fires (§8.8). `0` flags any difference. |
| `sensorSizeClassUnknownPolicy` | `skip_with_info` | What to do when a sensor row states no size class. See below. |
| `fuzzyMatchThreshold` | `0.82` | Below this, refuse to guess a canonical name. |
| `centsTolerance` | `0.005` | Slack on the cost identity and SubTotals checks. |

### `sensorSizeClassUnknownPolicy` — a documented assumption

**This is the one place the pipeline goes beyond an explicit rule in the task
outline.** §8.6 says a sensor row's size class comes from its Location text or
its Existing/Proposed Description, but gives no rule for when neither states one.
The Steve's Pools Detailed Cost Report is exactly that case: its two sensor rows
read only `"Integrated Fixture Sensor Smart Interior Advance/Basic"`, with no
size anywhere, split 6 and 7 against 13 matching fixtures. Read literally, §8.6
fires two `critical` flags there — which §9 does not expect.

Three implemented options:

- `skip_with_info` *(default)* — don't run the check on that row; raise an `info`
  flag saying so. Never invents an answer, never emits a false `critical`, and
  leaves the Proposal Detail check (the one §9 specifies) firing normally.
- `document_totals` — compare all sensor rows against all size-class-bearing
  fixture rows in that document (6+7 vs 2+1+10 → passes). Validates more, but is
  looser than §8.6 and could mask a genuine per-tier error.
- `borrow_from_sibling` — adopt a size class stated on another document in the
  batch. Uses more evidence, but infers across documents.

Change the one string to switch. Rows that **do** state a size class always get
the strict §8.6 check regardless of this setting.

---

## What the pipeline will never do

- **Auto-fill `revenue`.** Always `null` plus a flag (§5). BGE's Work Order
  Totals is its modeled system cost, not KCE's revenue.
- **Add modeled costs to actual costs.** BGE's $192.50/unit modeled vapor tight
  and Beacon's actual $65/unit are different cost bases for the same fixture and
  are never summed (§8.2).
- **Split a blended rate.** A `"$60 install and $50 fixture price"` line is
  tagged `blended: true` and excluded from credit-due math (§8.3).
- **Guess a wattage tier.** It cross-references BGE's wattage and offers it as a
  *suggestion* (§8.7).
- **Let an accessory float.** A photocell is rolled into its parent fixture's
  line with the split preserved in `components[]`, never reconciled on its own
  (§8.5).
- **Silently merge a stray document.** A file with a different MTX number is
  excluded with a `critical` flag; the rest of the batch processes normally (§8.9).
- **Pick a winner.** Where two documents disagree, both values appear in the
  output (§7).
