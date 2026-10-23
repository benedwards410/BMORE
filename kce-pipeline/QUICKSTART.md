# Reconciling a project — quick start

You do **not** need to know how to code, and you do not need to open a terminal.

---

## The whole process

1. Make one folder for the project. Put every document for that job in it.
2. **Drag that folder onto `RUN A PROJECT.cmd`** and let go.
3. Wait. Roughly 10–30 seconds per document.
4. Read the report it points you to.

That's it. If you'd rather not drag, double-click `RUN A PROJECT.cmd` and paste
the folder path when it asks.

---

## What to put in the folder

Anything you have. Nothing is required, and the order doesn't matter. The tool
works out what each document is on its own.

| Document | What it gives us |
|---|---|
| BGE Proposal Detail Report | What BGE **approved** — the work order |
| BGE Detailed Cost Report | BGE's **modelled** cost (not what we paid) |
| Supplier / distributor invoice | What we **ordered** and what it actually cost |
| Contractor / installer invoice | What was **installed** and what we were billed |
| Piece rate schedule | The contracted install rates |
| Inventory reconciliation | What was delivered vs what's **left over** |
| Credit calculation | Any credit already worked out against a contractor |

**No piece rate schedule?** Fine — the standard KCE rate card is used
automatically. Only include one if this job's rates differ from standard.

Extra files that aren't any of these (participation agreements, photos, notes)
are skipped and listed, not treated as errors.

---

## Reading the result

The tool prints a summary and writes two files:

- **`<project>.reconciliation.md`** — read this one. It's the report.
- **`<project>.project.json`** — the data, for importing into the ROI Tracker.

The summary ends with one of two lines:

- **"No blocking issues found."** — review the warnings, then close the job out.
- **"NOT READY TO CLOSE OUT"** — something needs a decision from a person first.
  The specific items are listed right there.

### The three flag levels

| | Meaning |
|---|---|
| 🔴 **critical** | Quantities or money that materially change the reconciliation. Decide before closing out. |
| 🟡 **warning** | Real, but not blocking. Worth a look. |
| 🔵 **info** | Cosmetic. Two documents spelling an address differently, that sort of thing. |

---

## The one rule to understand

**The tool never picks a winner.** When two documents disagree, it reports both
and asks you. It will not quietly "fix" a number.

So a report full of flags is not a broken run — that's the tool doing its job.
A job where the supplier says 5, BGE approved 2 and the installer fitted 2 is a
real problem worth knowing about, and you'll see it stated plainly.

Things it will deliberately never do on its own:

- Fill in project revenue (BGE's numbers are their cost model, not our revenue)
- Add BGE's modelled costs to real invoice costs — different things, never summed
- Split a blended "install + fixture" rate into its parts
- Guess a wattage tier when the invoice doesn't state the wattage
- Merge in a document whose MTX number doesn't match the rest

---

## If something looks wrong

### "could not be normalized to a canonical fixture type"

The tool met a product name or SKU it doesn't know. It's told you exactly which.
Nothing is lost — the cost is still counted — but that item won't reconcile by
fixture type until someone adds it.

This is a **settings change, not a code change**: `pipeline/config/canonical_fixtures.json`.
If you know the SKU, add it under `skuMap`; a part number always beats a guess
from the description. If you're not sure, send the flag text to whoever maintains
the tool.

### "Python was not found"

Install Python 3.11 or newer from python.org. Tick **"Add Python to PATH"**
during install.

### It says the API key isn't set

Only needed for documents the tool hasn't read before. Double-click
`CHECK SETUP.cmd` — it tells you exactly what's missing and how to fix it.

### It ran but found nothing

Usually the folder held documents it has never seen and there's no API key, so it
had nothing to read them with. Run `CHECK SETUP.cmd`.

---

## Re-running the same project

Free and instant. Every document is remembered after its first read, so running
the same folder again costs nothing and gives an identical result.

Change a document and it gets re-read automatically — the tool notices the file's
contents changed, not just its name.
