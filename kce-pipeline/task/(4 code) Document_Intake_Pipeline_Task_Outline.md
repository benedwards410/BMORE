# Task: Multi-Document Intake Pipeline for LED Retrofit Project Reconciliation

**Audience:** Claude Code (autonomous coding agent). This document is self-contained —
do not assume any prior conversation context. Everything you need is here or in the
attached test fixtures.

**Test fixtures:** `test_fixtures/steves_pools/` contains 5 real, unmodified project
documents. Use them to build against and to self-verify your output before calling
this done. Expected values for every fixture are given in §9 — if your pipeline's
output doesn't match those numbers, the pipeline is wrong, not the fixtures.

---

## 1. Background

Key Commercial Electric (KCE) is a Maryland-based commercial LED lighting retrofit
contractor. KCE participates in a BGE (utility) incentive program: BGE audits a
customer's site, approves a scope of LED fixtures, and subsidizes most of the cost.
KCE buys materials, hires subcontractor crews to install them, and later reconciles
what was purchased against what was installed and what BGE actually approved.

Each project is identified by an **MTX number** (e.g. `MTX79857647`), which appears
on every document tied to that job except the company's own standing rate card.

For every project, up to five kinds of source documents exist, produced by different
parties, in different formats, at different times:

1. **Piece Rate Schedule** — KCE's own standing subcontractor rate card. Not
   project-specific. No MTX number.
2. **Supplier/Distributor Invoice** — a real invoice from an electrical supply house
   (e.g. Beacon Lighting Supply) for materials KCE purchased.
3. **BGE Proposal Detail Report** — the utility's audit/proposal: approved fixture
   locations, types, and quantities. This is the work order.
4. **BGE Detailed Cost Report** — the utility's *priced-out* version of the same
   audit, splitting each line into a Material sub-row and a Labor sub-row, with a
   Program Share / Customer Share cost split. **This is BGE's internal cost model,
   not a real invoice** — see §8.2.
5. **Contractor/Installer Invoice** — a real invoice from the subcontractor crew
   that did the install, billed back to KCE.

A companion tool (a browser-based React reconciliation dashboard) already exists and
consumes a specific JSON shape per project (§6). This pipeline's output must be
directly importable into that shape — you are not designing the schema from scratch,
you are producing data that conforms to it, with two additions (`source` per line,
and a top-level `flags` array) that the existing tool doesn't have yet but should.

---

## 2. Task Description

Build a tool that takes a folder of 2–10 PDF/image documents belonging to **one**
project, and produces:

1. One structured JSON file describing the full project (§6), and
2. One human-readable reconciliation report (Markdown) listing every discrepancy,
   ambiguity, and item that needs a human's judgment call, per the **FLAG, DON'T
   OVERWRITE** principle (§7) — the tool's job is to surface disagreements between
   documents accurately, never to silently pick a winner.

The tool must:
- **Classify** each input file into one of the 5 document types above (§4).
- **Extract** structured line items from each, per that type's schema.
- **Auto-fill project metadata** (name, MTX number, customer, address, contact)
  from whichever BGE documents are present — see §5 for exactly which fields are
  safe to auto-fill and which are not.
- **Normalize fixture-type names** to one shared vocabulary so the same physical
  fixture type produces the same string regardless of which document it came from
  (§6.2) — without this, quantities from different documents can never reconcile.
- **Cross-check** that all project-specific documents in the batch reference the
  same MTX number, and refuse to silently merge if they don't (§8.6).
- **Flag, not resolve,** every case in §8 — do not invent a "correct" answer where
  the source documents disagree or the answer requires a business judgment call.

---

## 3. Environment & Tooling Notes

- You have full Anthropic API access and are **not** subject to a `max_tokens: 1000`
  cap that an earlier browser-artifact version of this idea was constrained by.
  Extract completely; don't truncate or compact JSON keys to save tokens.
- Prefer Python for orchestration (file I/O, batching, cross-checks, report
  generation). For the actual document reading, Claude's native PDF/vision
  understanding (via the Anthropic SDK's document content blocks) has already
  proven, in manual testing, to correctly read mixed tables, footnotes, and
  handwritten-style notes (e.g. a note explaining a blended unit price) that
  a pure table-extraction library like `pdfplumber` or `camelot` would likely
  miss or misparse. Use the API for extraction; use plain code for everything
  structural (classification routing, merging, validation, reporting).
- Two-pass design recommended: (1) a cheap classification pass per file (which
  of the 5 types is this?), (2) a type-specific extraction pass using that
  type's dedicated prompt/schema. Do not use one giant prompt trying to handle
  all 5 types at once — that's how the earlier version's ambiguity crept in.
- Output the reconciliation report even on partial failures (e.g. one
  unreadable file) — never let one bad file abort the whole batch silently.

---

## 4. Document Type Schemas (extraction targets)

### 4.1 Piece Rate Schedule → `pieceRates[]`
```json
{ "fixtureType": "8' Strip", "wattageTier": null, "contractedRate": 65.00 }
```
- No MTX number on this document type — do not require one.
- **Wattage tiers matter.** Several categories in a real KCE schedule have two
  rates depending on wattage (Wall Pack: <50W = $50, >50W = $75; Flood Light:
  <50W = $50, >50W = $75; Pole Light: ≤150W and >150W, both $75 in the current
  schedule but modeled as separate tiers since they could diverge). Capture
  `wattageTier` (e.g. `"<50W"`, `">50W"`, `"<=150W"`, `">150W"`, or `null` if
  the category has no tiering) as its own field — do not collapse a two-tier
  category into a single rate.
- Rows priced "Included" (e.g. add-on sensor rows bundled into the primary
  fixture's rate) are not separate rate entries — skip them.
- Real-world data quality: expect occasional typos in source PDFs (e.g. a
  price rendered as `$30..00`). Parse defensively — strip repeated punctuation
  before parsing a number, don't fail the whole document over one bad cell.

### 4.2 Supplier/Distributor Invoice → `supplierLines[]`
```json
{ "fixtureType": "Vapor Tight 4'", "sku": "LVT4WSCCTD1S", "qtyOrdered": 13, "unitPrice": 65.00, "hasSensor": false, "source": "actual_invoice", "sourceDoc": "Beacon Invoice #148" }
```
- `source` must be `"actual_invoice"` for this document type (see §8.2).
- Accessory/component rows (photocells, EM battery backup modules, mounting
  hardware, sensor lens kits) that appear as their own SKU/line should be
  extracted as their **own** line item with their own `fixtureType` (e.g.
  `"Photocell"`), not merged into or double-counting the primary fixture's
  quantity. A "3 flood lights + 3 photocells" invoice is 3 installed fixtures,
  not 6 — see §8.5.

### 4.3 BGE Proposal Detail Report → project metadata + `workOrderLines[]`
```json
{ "location": "Pool Room", "fixtureType": "Vapor Tight 4'", "sizeClass": "4ft", "qtyApproved": 2, "source": "proposal_detail" }
```
- This is the **preferred** work-order source (see §8.4 for why, vs. §4.4).
- `sizeClass` (`2ft`, `4ft`, `8ft`, `High Bay`, or `Exterior`) is derived from
  the fixture's wattage/size description and is **coarser** than `fixtureType`
  — it exists specifically to support the sensor validation in §8.6, where a
  single sensor row's quantity must be checked against multiple fixture rows
  of different canonical types that share one size class. Populate it on every
  work-order row, not just the ones near a sensor row.
- If this document also contains dedicated sensor rows (it usually does — see
  §8.6), extract those into `workOrderLines[]` too, with `fixtureType` set to
  the appropriate `Sensor - Basic` / `Sensor - Advance` canonical value.
- Also extract project metadata from this document — see §5.

### 4.4 BGE Detailed Cost Report → `modeledCosts[]` + `supplierLines[]` (Material only, grouped) + `otherExpenses[]` (fees/tax) + project metadata

This document requires two related but distinct outputs. Get **every fixture
line** — not just the fee/tax rows at the bottom — and for the fully-loaded
figure, **material + labor must be summed per line**, not extracted separately
or with labor discarded.

**(a) `modeledCosts[]` — one row per Line number, material + labor combined:**
```json
{
  "line": 4,
  "location": "Outside",
  "fixtureType": "Flood Light",
  "qty": 3,
  "materialCost": 973.50,
  "laborCost": 303.60,
  "totalCost": 1277.10,
  "programShare": 1085.55,
  "customerShare": 191.55,
  "source": "modeled_cost",
  "sourceDoc": "BGE Detailed Cost Report",
  "components": [
    { "type": "fixture", "materialCost": 808.50 },
    { "type": "Photocell", "materialCost": 165.00, "groupingConfidence": "certain" }
  ]
}
```
- Group every Material row sharing a Line number into that line's `materialCost`
  (see §8.5 for the accessory-grouping rules — a photocell's material row is
  **added into** its parent fixture's line, not kept as a separate `modeledCosts`
  entry). Record the breakdown in `components[]` so the split is still visible.
- Sum that line's Labor row into `laborCost`. `totalCost` = `materialCost` +
  `laborCost`, and must equal `programShare` + `customerShare` for that line —
  use this identity as a self-check on every line you extract.
- Extract **all** lines this way, including the Sensor lines (still tagged with
  their own canonical Sensor type per §8.6 — sensors are not folded into another
  fixture's line, they get their own `modeledCosts` row).
- This whole array sums to the report's `SubTotals` figure — use that as a
  batch-level self-check (see §9 for the exact number to match).

**(b) `supplierLines[]` — material-only fallback, same grouping applied:**
```json
{ "fixtureType": "Flood Light", "sku": null, "qtyOrdered": 3, "unitPrice": 324.50, "hasSensor": false, "source": "modeled_cost", "sourceDoc": "BGE Detailed Cost Report", "components": [ { "type": "fixture", "unitPrice": 269.50 }, { "type": "Photocell", "unitPrice": 55.00, "groupingConfidence": "certain" } ] }
```
- Same grouped-material figure as `modeledCosts[].materialCost`, expressed as a
  per-unit price, for use as the material-cost fallback described in §8.2 when
  no `actual_invoice` exists yet for that fixture type.

**(c) `otherExpenses[]` — fees and tax only, unchanged from before:**
```json
{ "category": "Recycling Fee", "description": "Recycling Fee", "amount": 99.32 }
```
- Confirmed correct as originally scoped: only the fee/tax rows (Recycling Fee,
  Sales Tax) belong here from this document. Fixture material and labor do
  **not** — they go to `modeledCosts[]` and `supplierLines[]` above. This was
  tested against the real fixture and works as intended; no change needed here.

**Still applies, unchanged:**
- **Do not** write this document's rows into `workOrderLines[]` — see §8.4.
  This restriction applies regardless of the `modeledCosts[]` addition above;
  `modeledCosts[]` is a cost dataset, not a work-order/approved-quantity one.
- Ignore the Program Share / Customer Share **split** everywhere except inside
  `modeledCosts[]`, where it's captured as reference context, not used to
  compute any cost figure.
- Also extract project metadata — see §5.

### 4.5 Contractor/Installer Invoice → `contractorLines[]` + `otherExpenses[]`
```json
// Fixture line
{ "invoiceNum": "2025-26", "date": "08/05/2026", "description": "-4' Vaportight", "fixtureType": "Vapor Tight 4'", "qty": 13, "billedRate": 75.00, "blended": false, "source": "actual_invoice" }
// Flat non-fixture line, same invoice
{ "category": "Disposal", "description": "Material pick up, scrap/trash removal", "amount": 350.00 }
```
- One invoice commonly contains **both** per-fixture lines and flat, non-fixture
  service lines (trip charges, disposal fees, mobilization). Route each to the
  correct array from a **single** read of the document — do not require the
  document to be uploaded twice to capture both. This was a real usability gap
  in the earlier version; do not repeat it.
- Set `"blended": true` **only** when the line's own text explicitly says the
  rate bundles fixture/material cost with install cost (e.g. "$60 install and
  $50 fixture price"). Do not guess at this from price alone — only from
  explicit text. See §8.3 for why this can't be auto-corrected.
- If the document is actually a BGE Detailed Cost Report or other cost
  allocation (recognizable by a Program Share / Customer Share column), it is
  **not** a contractor invoice — the classifier in step 1 should have already
  routed it to §4.4, but as a safety net this extraction step should also
  refuse to extract fixtures from a document with those columns.

---

## 5. Auto-Extracted Project Metadata

From the Proposal Detail and/or Detailed Cost reports (§4.3, §4.4), safely auto-fill:

| Field | Source | Notes |
|---|---|---|
| `name` | "Audit / Proposal" field, the part after the `/` (e.g. "Steve's Pools") | |
| `poNumber` | "Audit / Proposal" field, the part before the `/` (the MTX number) | |
| `customer` | Report title ("...Report for **[Customer]**") | |
| `address` | Address block under the title | |
| `contactName` / `contactPhone` | "Contact Name" / "Contact Phone" fields | |

**Do NOT auto-fill `revenue`** from either BGE document. `Work Order Totals` on the
Detailed Cost Report (Program Share + Customer Share) is BGE's modeled *system
cost*, not KCE's revenue from the customer — these are frequently different
numbers, and treating one as the other would silently corrupt every ROI
calculation downstream. Leave `revenue` as `null` with a flag noting it needs
manual entry, in every case, with no exceptions.

If the Proposal Detail and Detailed Cost reports disagree on any metadata field
(e.g. a different **auditor name** on each — this happens in real data and is
usually benign), do not error or silently pick one — record both under an
`info`-severity flag (§7) and proceed with the value from Proposal Detail as the
working value.

---

## 6. Output Schema

### 6.1 Top-level project JSON
```json
{
  "project": {
    "name": "",
    "poNumber": "",
    "customer": "",
    "address": "",
    "contactName": "",
    "contactPhone": "",
    "revenue": null
  },
  "supplierLines": [],
  "workOrderLines": [],
  "pieceRates": [],
  "contractorLines": [],
  "otherExpenses": [],
  "modeledCosts": [],
  "flags": []
}
```
Every line item in every array carries a `source` field (which document it came
from) for traceability — this does not exist in the earlier browser-artifact
version and should be added here as a real improvement. `modeledCosts[]` is
populated only from the BGE Detailed Cost Report (§4.4) and is never used as an
input to `supplierLines[]`-vs-`contractorLines[]` reconciliation math directly —
it's a separate, clearly-labeled benchmark dataset (see §8.2).

### 6.2 Canonical fixture-type vocabulary

Normalize every extracted fixture type to one of these exact strings. This is the
single most important correctness requirement in this whole task — the entire
point of building this pipeline is that "Wallpack Watt/CCT Select 60-120W" (a
distributor's SKU description), "Exterior LED 100W Wall Mount" (BGE's wording),
and "Wall Pack" (KCE's own rate card) are the same physical thing, and must
produce the identical string so their quantities can be reconciled against each
other:

```
8' Strip, 4' Strip, 2' Strip
High Bay
2x2 Volumetric Kit, 2x4 Volumetric Kit
Flat Panel
Wrap Fixture
Vapor Tight 8', Vapor Tight 4', Vapor Tight 2'
Wall Pack
Flood Light
Pole Light
Recessed Can
Photocell, EM Battery Backup
Sensor - Basic, Sensor - Advance
```

`Photocell` and `EM Battery Backup` remain in this vocabulary as **component
type labels** used inside a parent fixture's `components[]` array (§8.5) — they
are not independent top-level fixture types subject to the ordered/approved/
installed reconciliation in §8.8. Sensors, by contrast, **are** independent
top-level types (§8.6) — do not treat the two categories the same way.

Maintain this list as an editable JSON/YAML config file, not a hardcoded string
in a prompt — it will need new entries as KCE takes on new project types, and it
should be maintained without touching extraction code. Match new incoming names
against it via exact match first, then a fuzzy/semantic pass, before ever
inventing a new canonical name.

---

## 7. Flagging Rules ("Flag, Don't Overwrite")

Every entry in the output `flags[]` array has this shape:
```json
{ "severity": "info" | "warning" | "critical", "message": "", "relatedFixtureType": "Wall Pack" }
```

- `critical` — quantities or costs that materially change the reconciliation and
  need a human decision before the project can be considered reconciled (e.g. a
  quantity mismatch between ordered/approved/installed of more than a couple
  units).
- `warning` — something real but not immediately blocking (e.g. a blended-rate
  line, a document referencing no source for a required cost).
- `info` — cosmetic or low-stakes inconsistency (e.g. differing auditor names
  across two BGE reports for the same audit).

**Never** let the pipeline auto-resolve a disagreement by picking one source over
another and discarding the other silently. If two documents disagree, both
values should be visible in the output (e.g. via `flags[]`), not just the one
the code happened to process last.

---

## 8. Complexities & Required Behaviors

### 8.1 Fixture-type naming inconsistency (§6.2)
Already covered above — this is the foundational fix. Test against §9.

### 8.2 Modeled cost vs. actual cost — do not conflate

**Rule, stated flatly: BGE Detailed Cost Report material numbers are not, and
must never be treated as, the supplier's actual cost.** They are a utility
cost-allocation model, using round, standardized per-unit figures (in the test
fixtures: $192.50/unit for a 4' vaportight, modeled) — not what KCE actually
paid ($65/unit, per the real Beacon invoice). These are two different cost
bases for the same physical fixture, produced by different parties for
different purposes, and the fact that both happen to describe the same
fixture type does not make them comparable or additive.

**Required behavior:** when both a `modeled_cost` line and an `actual_invoice`
line exist for the same fixture type, the pipeline must:
1. Never sum their quantities or dollar amounts together as if they were two
   purchases of the same thing.
2. Prefer `actual_invoice` as the material cost of record whenever it exists for
   that fixture type.
3. Keep `modeled_cost` lines only as a reference/fallback (e.g. for an early ROI
   estimate before real invoices exist), clearly tagged, and raise a `warning`
   flag whenever both exist for the same type so a human can see the both-tagged
   entries and confirm which is authoritative.

### 8.3 Blended material+labor rates on contractor invoices
A subcontractor invoice line can bundle install labor and self-supplied material
into one rate (test fixture: "$60 install and $50 fixture price" = $110/unit).
Comparing that $110 directly against a pure-labor contracted rate produces a
number that looks like an overcharge or undercharge but isn't a real one — the
comparison bases don't match.

**Required behavior:** tag such lines `"blended": true` per §4.5, and exclude
`blended` lines from any automatic "credit due" calculation, or clearly segregate
them into their own subtotal with a warning rather than blending them into a
single trusted total. Do not attempt to algorithmically split the $110 into $60 /
$50 components — that requires a business decision (was KCE told materials would
be reimbursed at this rate? at all?) that the pipeline cannot make. Flag it for a
human to split manually.

### 8.4 Overlapping work-order sources
The Proposal Detail report and the Detailed Cost report describe the same
underlying approved scope, but the Detailed Cost report splits each line into a
Material row and a Labor row. If both get parsed into `workOrderLines[]`
additively, quantities double.

**Required behavior:** only the Proposal Detail report populates
`workOrderLines[]` (§4.3). The Detailed Cost report's rows go to `supplierLines[]`
and `otherExpenses[]` only (§4.4), never to `workOrderLines[]`. If a batch
contains a Detailed Cost report but no Proposal Detail report, and you must
derive approved quantities from the Detailed Cost report as a fallback, de-
duplicate its Material/Labor row pairs into exactly one work-order row per
physical fixture per location before writing to `workOrderLines[]`.

### 8.5 Accessory grouping (photocells, EM battery backup, and similar add-ons)
A BGE Detailed Cost report frequently lists an accessory (photocell, EM battery
backup, sensor lens) as its own Material row under the same "Line" number as the
primary fixture (test fixture: Line 4 "Exterior LED 70W Flood" has both a $808.50
fixture Material row and a $165.00 photocell Material row, both qty 3).

**Why this needs a rule at all:** an accessory has no corresponding entry of its
own on the work order or the contractor invoice — the work order approves "3
Flood Lights," not "3 Flood Lights + 3 Photocells" as two separate line items,
and the contractor invoice bills one blended rate per fixture, never a separate
photocell line. If a "Photocell" canonical type is extracted as its own free-
floating line, §8.8's reconciliation check will flag it as "3 ordered, 0
approved, 0 installed" — a false positive. The accessory's approval and
install status is inherited from its parent fixture, not tracked independently.

**Required behavior — group, don't float:**
- Identify the accessory's parent fixture using the shared Line number (or
  Location, if Line isn't present) within the same document — this linkage is
  already present in the BGE report's own structure; use it rather than
  re-deriving it.
- Roll the accessory's cost **into** the parent fixture's line as a `components[]`
  entry (see §4.4 schema) rather than creating an independent `fixtureType` row.
  The parent fixture's `qtyOrdered` / `qty` is never inflated by the accessory's
  presence — 3 flood lights + 3 photocells is still qty 3, at a higher grouped
  unit cost, not qty 6.
- Association confidence varies by accessory type — apply this table:

| Accessory | Association rule | Confidence |
|---|---|---|
| Photocell | Always pairs with the exterior fixture on the same Line/Location (Wall Pack, Flood Light, Pole Light) | `certain` — group automatically, no flag needed |
| EM Battery Backup | Typically pairs with an interior fixture (Strip, Flat Panel, High Bay, Vapor Tight, Wrap Fixture, Recessed Can) on the same Line/Location | `needs_confirmation` — group by best guess, but **always** raise a `warning` flag asking for confirmation, even when the pairing looks obvious |
| Any other accessory-type row with no fixture rule above, and no clear parent on the same Line/Location | No default | `needs_confirmation` — raise a `warning` flag and ask how to group it; do not guess |

- Sensors (`Sensor - Basic` / `Sensor - Advance`) are **not** covered by this
  section — they are tracked as their own first-class canonical type per §8.6,
  since they have independent quantity, tier, and cost significance and their
  own work-order line. Do not apply accessory-grouping logic to sensor rows.
- Every `needs_confirmation` grouping must produce a corresponding entry in
  `flags[]` naming the accessory, the fixture it was tentatively grouped with,
  and asking for confirmation — per §7, a tentative grouping is not the same
  as a confirmed one and must not be presented as settled.

### 8.6 Sensor line items, size-class validation, and tier mismatches
Sensors sometimes appear bundled into a fixture's SKU (a distributor's line
literally includes "WITH SENSOR" in the description) and sometimes as their own
separate purchased/installed line item with a cost tier (`Sensor - Basic` vs.
`Sensor - Advance`, different unit costs). Different source documents for the
same job can disagree on the tier breakdown even when the total count matches
(test fixture: Proposal Detail says 13 Basic; Detailed Cost Report says 6
Advance + 7 Basic — both total 13).

**How a BGE-format document represents sensors:** a Proposal Detail or Detailed
Cost report typically has one or more dedicated sensor rows, separate from the
individual fixture rows, whose quantity is the **sum of every fixture row in
that same document sharing the same base size class** — not tied to one
location, and not one sensor row per fixture row. The size class is usually
identifiable either from the sensor row's own Location text (a "4ft sensors,"
"HB sensors," "8ft sensors," "2ft sensors" naming pattern seen in some reports)
or, when the sensor row's Location is just "Sensors," from its Existing/Proposed
Description column stating the fixture wattage/size it corresponds to (the
pattern in the Steve's Pools test fixture).

**Size class is coarser than the canonical fixture-type vocabulary — this
matters.** A "4ft sensors" row's quantity sums across *every* 4-foot fixture
row regardless of canonical fixture subtype — Strips *and* Volumetric Kits both
count toward it, even though §6.2 treats `4' Strip` and `2x4 Volumetric Kit` as
distinct canonical types for cost/quantity reconciliation everywhere else in
this pipeline. Do not implement the sensor check using the canonical
`fixtureType` field — derive a separate, coarser `sizeClass` (`2ft`, `4ft`,
`8ft`, `High Bay`, `Exterior`) from each fixture row's wattage/size description,
and sum by that instead.

**Required behavior:**
- For every sensor row found, sum the quantity of every other fixture row in
  the same document sharing that sensor row's size class, and confirm the two
  totals match exactly.
- If they don't match, raise a `critical` flag — this is a strong signal of
  either an extraction error or a genuine discrepancy in the source document,
  and should not be treated as a soft warning.
- Extract sensor line items with their tier when stated. If two documents in
  the same batch disagree on tier breakdown for the same total count, raise a
  `warning` flag citing both breakdowns — do not silently pick one.

**Worked examples (both independently confirmed by hand against real project
documents — use these as acceptance tests in addition to §9):**
- Steve's Pools Proposal Detail: `4ft` size class fixture rows (Pool Room 2 +
  Lifeguard Room 1 + Restrooms 10 = 13) match the "Sensors" row's qty 13 exactly.
- A second, independently-verified project (MTX20616192, Bob Bell Ford) shows
  the same pattern with explicit size-named sensor rows and confirms the
  cross-canonical-type summing behavior: "4ft sensors" qty 258 = 222 (4' Strip)
  + 3 (2x4 Volumetric Kit) + 28 (4' Strip) + 5 (2x4 Volumetric Kit); "8ft
  sensors" qty 106 = 15 + 91 (both 8' Strip); "2ft sensors" qty 4 = 2 (2' Strip)
  + 2 (2' Volumetric); "HB sensors" qty 50 = 50 (High Bay, single line).

### 8.7 Wattage-dependent rate tiers
Wall Pack, Flood Light, and Pole Light categories on the piece rate schedule have
two rates depending on wattage. A contractor invoice line often doesn't state
wattage (test fixture: Justin's invoice just says "-Wall Pack," no wattage). In
that case the pipeline cannot determine which contracted rate applies with
certainty.

**Required behavior:** when a contractor-billed fixture's wattage can't be
determined from its own invoice, but the type has wattage-tiered rates, raise a
`warning` flag rather than guessing a tier — cross-reference the Proposal Detail
or Detailed Cost report's wattage for that location/fixture if present and note
it as a suggested (not authoritative) tier.

### 8.8 Ordered vs. approved vs. installed quantity mismatches
The three quantities (ordered on a supplier invoice, approved on the work order,
installed per the contractor invoice) frequently won't match, and shouldn't be
auto-reconciled — the mismatch itself is the useful signal (over-ordering,
under-installing, scope creep, etc.).

**Required behavior:** for every canonical fixture type, compute all three
quantities where available and raise a `critical` flag whenever they differ by
more than a small, configurable tolerance (default: any difference at all,
tolerance is a config knob, not a hardcoded skip). This includes the case where
installed quantity exceeds ordered quantity (a negative "remaining") — handle
that gracefully as a flag, not a crash or a silently clamped-to-zero value.

### 8.9 Batch consistency check (MTX number)
Before merging data from multiple files into one project, verify every
project-specific document (all types except the Piece Rate Schedule, which has
no MTX number and should be exempt from this check) references the same MTX/PO
number.

**Required behavior:** if any project-specific document in the batch has a
different MTX number than the others, do not merge its data into the project.
Raise a `critical` flag naming the mismatched file and its MTX number, and
exclude that file's extracted data from the merged output (process the rest of
the batch normally).

---

## 9. Test Fixtures & Acceptance Criteria

Files in `test_fixtures/steves_pools/`, project MTX79857647 ("Steve's Pools" /
Fox Valley Homeowners Assoc):

- `KCE_Piece_Rate_Schedule.pdf`
- `Justin_-_Steves_Pool_Invoice_2025-26_080526.pdf` (contractor invoice)
- `Proposal_Detail-Steve_s_Pools.pdf` (BGE work order)
- `Detailed_Cost-Steve_s_Pools.pdf` (BGE cost allocation)
- `148_MTX79857647_steves_pool.pdf` (Beacon supplier invoice)

Run the full batch through the pipeline and verify:

**Project metadata:** name "Steve's Pools", poNumber "MTX79857647", customer "Fox
Valley Homeowners Assoc", address "3320 GREAT VALLEY Drive, West Friendship MD
21794", revenue `null` with a flag noting it needs manual entry.

**MTX consistency check:** passes — all 4 project-specific documents reference
MTX79857647 (Piece Rate Schedule correctly exempted).

**Vapor Tight 4' — the clean case, everything agrees:**
- Approved (work order): 13 (2 Pool Room + 1 Lifeguard Room + 10 Restrooms)
- Ordered (Beacon, actual): 13 @ $65.00/unit
- Installed (Justin): 13 @ $75.00/unit billed
- Modeled (Detailed Cost, `supplierLines[]` fallback): 13 total @ $192.50/unit
  material-only, tagged `modeled_cost` — must not be summed with Beacon's actual
  13 units into a combined qty of 26
- Modeled (Detailed Cost, `modeledCosts[]`, material + labor combined — no
  accessories on this fixture type): three rows, all at **$289.91/unit fully
  loaded** — Pool Room qty 2 = $579.82, Lifeguard Room qty 1 = $289.91,
  Restrooms qty 10 = $2,899.10. (Confirm this per-unit figure is identical
  across all three locations — it's a useful internal consistency check.)
- No quantity-mismatch flag expected here (13 = 13 = 13) — this case exists in
  the fixtures specifically to prove the pipeline doesn't over-flag when
  everything genuinely reconciles.

**Wall Pack — a real, expected mismatch:**
- Approved (work order): 2
- Ordered (Beacon, actual): 5 @ $75.00/unit
- Installed (Justin): 2 @ $60.00/unit billed
- Modeled (Detailed Cost, `modeledCosts[]`, grouped with its Photocell
  accessory): Outside, qty 2, materialCost $825.00 (= $770.00 fixture +
  $55.00 photocell, see `components[]`), laborCost $202.40, totalCost
  $1,027.40 → **$513.70/unit fully loaded**. `supplierLines[]` fallback:
  qty 2 @ $412.50/unit material-only (grouped).
- Expected: a `critical` flag on Wall Pack — 3 units ordered beyond both approved
  and installed quantities.
- Expected: a `warning` flag on Wall Pack's billed rate ($60) — wattage not
  stated on the contractor invoice, and the schedule's Wall Pack rate is
  tiered ($50 / $75).
- Expected: the Photocell accessory grouped into this line with
  `"groupingConfidence": "certain"` — no confirmation flag needed for the
  grouping itself (only for the wattage tier above).

**Flood Light — self-supplied material:**
- Approved (work order): 3
- Installed (Justin): 3 @ $110.00/unit billed, `"blended": true` (invoice note:
  "$60 install and $50 fixture price... provided by Let There Be Light")
- No `actual_invoice` supplier line exists for this type anywhere in the batch.
- Modeled (Detailed Cost, `modeledCosts[]`, grouped with its Photocell
  accessory): Outside, qty 3, materialCost $973.50 (= $808.50 fixture +
  $165.00 photocell), laborCost $303.60, totalCost $1,277.10 → **$425.70/unit
  fully loaded**. `supplierLines[]` fallback: qty 3 @ $324.50/unit
  material-only (grouped) — this single grouped line replaces what an earlier
  draft of this pipeline would have produced as two disconnected lines
  (`Flood Light` and `Photocell`), which would have wrongly triggered its own
  "0 approved / 0 installed" flag for the photocell.
- Expected: a `warning` flag that Flood Light has no actual-invoice material
  record in this batch, and a `warning` flag on the blended contractor rate.

**Sensors — size-class validation and tier disagreement:**
- Work order (Proposal Detail): 13, all tier "Sensor - Basic," `sizeClass`
  "4ft."
- Size-class validation (§8.6): the three `4ft`-class fixture rows on this same
  document (Pool Room 2 + Lifeguard Room 1 + Restrooms 10) sum to exactly 13 —
  matches the sensor row's qty 13. No `critical` flag expected here; this case
  exists to prove the validation passes cleanly when the document is internally
  consistent, the same way the Vapor Tight 4' case proves §8.8 doesn't
  over-flag a clean reconciliation.
- Detailed Cost Report (`modeledCosts[]`): two separate rows — Sensors Advance
  qty 6, materialCost $600.00, laborCost $345.00, totalCost $945.00 →
  $157.50/unit; Sensors Basic qty 7, materialCost $350.00, laborCost $241.50,
  totalCost $591.50 → $84.50/unit. Total 13, but tier split disagrees with the
  work order's "all 13 Basic."
- Expected: an `info` or `warning` flag citing both tier breakdowns (this is
  separate from, and in addition to, the size-class validation above — one
  checks total-quantity internal consistency, the other checks whether two
  documents agree on how that total splits by tier).

**Batch-level self-check on `modeledCosts[]`:**
- All 7 lines (Pool Room, Lifeguard Room, Restrooms, Outside Flood, Outside
  Wall Mount, Sensors Advance, Sensors Basic) sum to exactly **$7,609.83** —
  this matches the report's own "SubTotals" figure and is the single strongest
  correctness check for this whole extraction. If your pipeline's sum doesn't
  land on $7,609.83 to the penny, something in the material+labor summation or
  the accessory grouping is wrong.

**Non-fixture contractor line:**
- Justin's invoice includes "-Material pick up, scrap/trash removal" for $350,
  no quantity or unit price.
- Expected: this appears in `otherExpenses[]` (category e.g. "Disposal"), not in
  `contractorLines[]`, extracted from the same single read of the invoice that
  also produced its 3 fixture lines.
- Invoice total check: 13×75 + 2×60 + 3×110 + 350 = **$1,775.00**, matching the
  invoice's stated "Total Owed."

**Fee/tax lines from Detailed Cost Report:**
- Expected in `otherExpenses[]`: Recycling Fee $99.32, Sales Tax $321.02 (use the
  Price column, not Program Share or Customer Share). Confirmed by manual
  testing that this extraction already works correctly as scoped — no change
  needed to this part.

**Piece rate schedule parsing:**
- Recessed Can rate should parse as $30.00 despite the source PDF rendering it
  as "$30..00" — a real formatting defect the parser must handle gracefully.
- Wall Pack and Flood Light should each produce two rate rows (wattage tiers),
  not one.

**EM Battery Backup — not covered by this fixture set:**
- None of the 5 Steve's Pools documents contain an EM Battery Backup line, so
  there is no ground-truth number to check here. Implement per the rule table
  in §8.5 regardless, and verify the `needs_confirmation` flag fires correctly
  the next time a project's documents include one — do not skip implementing
  this rule just because this particular test batch can't exercise it.

---

## 10. Non-Goals / Out of Scope

- No UI is required for this task — a CLI tool or callable function that takes
  a folder path and returns/writes the JSON + report is sufficient.
- Do not attempt to algorithmically resolve any of the §8 flagged ambiguities —
  surfacing them clearly is the deliverable, not resolving them.
- Do not attempt full OCR/handling of illegible or severely degraded scans
  beyond what Claude's native document reading handles natively — reasonable
  failure (skip + flag the file) is acceptable for genuinely unreadable input.
- Do not build project types or fixture categories beyond LED lighting retrofit
  work for this pass.
- Do not integrate with HubSpot, DocuSign, or other KCE systems yet — output a
  local JSON file; integration is a separate future task.

---

## 11. Deliverables Checklist

- [ ] Classification step: routes each input file to one of the 5 document types
- [ ] Five type-specific extraction routines matching §4 schemas exactly
- [ ] `modeledCosts[]` extraction: every Detailed Cost Report line, material +
      labor summed per line, self-checked against the report's own SubTotals
- [ ] Sensor size-class validation (§8.6): `sizeClass` derived per fixture row,
      independent of canonical `fixtureType`, and every sensor row's quantity
      checked against the sum of matching-size-class fixture rows in the same
      document, raising `critical` on mismatch
- [ ] Accessory grouping (§8.5): Photocell auto-grouped with certainty; EM
      Battery Backup grouped with a mandatory confirmation flag; unknown
      accessories flagged for manual grouping — never left as free-floating
      independently-reconciled fixture types
- [ ] Canonical fixture-type vocabulary as an editable config file (§6.2)
- [ ] Project metadata auto-fill with the `revenue` exclusion enforced (§5)
- [ ] Merge step producing the schema in §6.1, with `source` on every line
- [ ] All nine behaviors in §8 implemented and individually testable
- [ ] MTX batch-consistency check (§8.9)
- [ ] Human-readable Markdown reconciliation report generated alongside the JSON
- [ ] Full run against `test_fixtures/steves_pools/` matches every expected value
      and flag in §9, including the `modeledCosts[]` $7,609.83 batch total
- [ ] Output JSON is a valid drop-in for the existing project-tracker's schema
      (confirm field names match §6.1 exactly)
