# kce-prescriptive: the prescriptive project application bot

Drop in a lighting audit and get back the whole BGE Energy Solutions for Business package,
as drafts:

```
AUDIT ──► project.json ──► QA gate ──► BGE workbook (.xlsm) ──► open + save in Excel ──► readback
                                   ├─► customer proposal (.docx/.pdf: price − BGE incentive = net)
                                   ├─► Terms & Conditions, pre-filled (customer signs)
                                   ├─► cut-sheet bundle (+ Exterior Circuit form if pole/flood)
                                   ├─► portal cheat sheet (every BGE portal field, in order)
                                   └─► QA report (INTERNAL)
```

Claude does the judgment calls: reading the audit, space types, matching products, asking.
Python does everything that must be exact. The skill is
`skills/prescriptive-package/SKILL.md`.

## Quick start

```bash
cd kce-prescriptive
# one-time: put the blank BGE workbook here (not committed: ICF "do not distribute")
cp BGE_CI_Worksheet_Lighting_Fixtures_Controls_07212025.xlsm templates/bge/
# one-time: KCE-internal settings (not committed): submitter contact + prices
cat > config/kce.local.json <<'JSON'
{"workbook_submitter": {"contact": "...", "phone": "...", "email": "..."},
 "prices": {"VEKT2X4-8T": 0, "VEKT2X2-8XX": 0}}
JSON

python3 -m prescriptive.cli audit-to-project my_audit.xlsx --out fixtures-local/job.json
python3 -m prescriptive.cli check fixtures-local/job.json
python3 -m prescriptive.cli build fixtures-local/job.json --out out
#   ... open out/<job>/<job>_BGE_Worksheet.xlsm in Excel, save ...
python3 -m prescriptive.cli readback fixtures-local/job.json SAVED.xlsm --out out
```

Blank audit sheet: `templates/audit-template.xlsx` (regenerate with `audit-template --out`).

## Proven on real jobs

Tested against two real KCE jobs (their files stay local, never in git):

| Check | Result |
|---|---|
| Bot estimate vs the Excel-calculated, submitted BGE workbook | exact to the dollar, lighting and controls |
| Generated workbook inputs vs the submitted workbook | 786 / 786 line-input cells match |
| Both workbooks recalculated side by side | every formula output identical on every line, incentive and kWh |
| `readback` on the Excel-saved file | reads Excel's incentive and kWh, every line matches the estimate |
| A KCE quote rebuilt from its audit | incentive, subtotal, recycling, tax, total, net, maintenance and payback all reproduce |
| File integrity | VBA, dropdowns (incl. dependent x14 lists) and sheet protection byte-identical to BGE's template |

Golden test: `GOLDEN_PROJECT=... GOLDEN_WORKBOOK=... python3 -m unittest discover -s tests`.

## Why it's built this way

- **The workbook is patched at the XML level.** openpyxl would strip the dependent
  dropdowns. Only the input cells change, and the writer refuses to overwrite a formula,
  so a new BGE tool version fails loudly instead of writing into the wrong cells.
- **Excel is the calculator of record.** LibreOffice recalculates this workbook wrong
  (it undercounts the incentive, because of the occupancy-requirement formulas), so it's
  never used for the numbers. The bot keeps its own estimate, which follows the
  workbook's formulas, and `readback` checks the two agree line by line.
- **The QA gate** comes from real misses: a 29-fixture room left off the workbook, a strip
  entered on a high-bay code, a city/ZIP that differed between the workbook and the T&C,
  KCE's own email as the customer's signer, every fixture claimed as daylight zone. Rules are in `skills/prescriptive-package/references/qa-rules.md`.

## Files

| Path | What |
|---|---|
| `prescriptive/` | Python core (`cli.py` is the entry point) |
| `references/template_tables.json` | rates, measure codes, dropdown lists, rated wattages; built locally from the blank workbook on first run (not committed) |
| `references/measure_rules.json` | DLC category / primary use / lumen band per measure (BGE tech sheet 08-2025) |
| `references/existing_fixtures.json` | audit pick list → BGE existing device category + code |
| `catalog/products.json`, `catalog/cutsheets/` | KCE's products: DLC data, field wattage, price, cut sheet |
| `config/kce.json` | KCE company info, recycling/tax %, savings assumptions; `kce.local.json` (not committed) adds submitter contact and prices |
| `templates/` | blank T&C (202510, fillable), Exterior Circuit form (202307); `audit-template.xlsx` is generated locally |
| `tests/` | `python3 -m unittest discover -s tests` (golden tests run when local files exist) |

## Open items (need a person)

- **DLC data for the 2x2 kit** (VEKT2X2-8XX): ID, lumens, watts, efficacy. Until it's filled, QA blocks any job that uses it.
- **Cut sheets** for RCF6M9WCSTA, KT-MSLED90PS-8, KT-WPLED120PSHV, the high bay, Silvair, and Keystone SmartLoop.
- **DLC primary use** for the two Keystone fixtures, and NLC listings for the networked controls.
- **Maintenance assumptions** in `config/kce.json` (lamp/ballast part cost and life) were back-solved from a past quote. Confirm them.
- **Payee**: past jobs used both "Third-Party" and "Service Provider". Pick a default (`payee_default`).
- **T&C edition**: BGE's newest is 202601. The fillable copy here is 202510, so a fillable 202601 copy would replace it.

## What stays out of git (this repo is public)

Customer projects and packages (`fixtures-local/`, `out/`), KCE prices and the submitter's
contact (`config/kce.local.json`), BGE's workbook and everything derived from it
(`templates/bge/`, `references/template_tables.json`, `templates/audit-template.xlsx`).
