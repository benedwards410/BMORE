---
name: prescriptive-package
description: >
  Turn a completed lighting audit into a BGE Energy Solutions for Business prescriptive
  application package: the BGE Retrofit Lighting Worksheet (.xlsm), a customer proposal
  (price - BGE incentive = net), the pre-filled Terms and Conditions, the cut-sheet bundle,
  a portal cheat sheet, and an INTERNAL QA report. Use when the user says "build the BGE
  package", "prescriptive application", "fill the BGE workbook", "BGE lighting worksheet",
  "rebate workbook from this audit", "quote this audit for BGE", "C&I prescriptive",
  "Energy Solutions for Business", or drops a lighting audit and asks for the rebate paperwork.
  Not for BGE Small Business (SBES / Matrix / MTX) jobs: those use kce-mtx-control.
---

# Prescriptive package

The Python core in `${CLAUDE_PLUGIN_ROOT}/prescriptive/` does everything that must be exact:
cell writing, rebate math, QA rules, PDF forms. **You do the judgment calls**: reading the
audit, choosing space types, matching fixtures to catalog products, and asking when a
fact is missing. Never re-derive incentive math by hand. Run the script.

Run every command from `${CLAUDE_PLUGIN_ROOT}`:
`python3 -m prescriptive.cli <command> ...`

## Rules that never bend

1. **Draft only.** Nothing is submitted to the BGE portal, emailed, or sent to the customer
   without the user's explicit go. The proposal stays `_DRAFT` until Ben approves its dollars.
2. **Never invent DLC data.** DLC ID, lumens, watts and efficacy are copied exactly from the
   DLC/ENERGY STAR listing or the spec sheet the user gives you. Unknown stays `null`; QA blocks.
3. **Flag, don't overwrite.** Never edit the user's audit, an old workbook, or a signed form.
   Differences between documents are findings to report.
4. **The customer signs the T&C.** `customer_contact` is the BGE customer of record, never KCE.
5. **No customer data in git.** Projects and outputs live in `fixtures-local/` or `out/` (ignored).

## Steps

1. **Intake the audit.**
   - On the standard sheet (`templates/audit-template.xlsx`): `audit-to-project AUDIT.xlsx --out <job>.json`.
   - In any other form (photos, PDF, another spreadsheet): copy it onto the standard sheet
     yourself, then show the user the room-by-room table (area, int/ext, space type, existing
     fixture, qty, new product, sensor) **and wait for a yes** before converting.
   - An existing BGE workbook someone started: `import-workbook FILE.xlsm --out <job>.json`
     (add `--model-map` for placeholder models like "MODEL # TBD").
   - Use `references/mapping-rules.md` for every judgment call. Ask; don't guess.
2. **Fill the project facts** the audit doesn't carry. Ask once, together: customer of record
   (the name on the BGE account), BGE account number, the customer's signer (name, title,
   email, phone), building type, heating fuel, square footage, business sector and type, and
   who BGE pays (`payee`: contractor / third_party / customer).
3. **Check.** `check <job>.json [--against OLD.xlsm SIGNED_TC.pdf]`. Present the result as
   BLOCKERs, then ASKs, then WARNs, grouped, in plain words (`references/qa-rules.md` explains
   each). Resolve ASKs with the user. Missing product data goes into `catalog/products.json`
   (with the source noted), and cut sheets go into `catalog/cutsheets/`.
4. **Build.** `build <job>.json --out out` (add `--force` only to make review drafts while
   blocked, and say so). Outputs land in `out/<job>/`.
5. **Look at what you built.** Render the proposal PDF and T&C page 3
   (`pdftoppm -r 60 -png ...`) and check every page: totals, area table, payee box, assignee.
6. **Excel step (the user).** The workbook's math runs only in Excel (LibreOffice computes it
   wrong). Ask the user to open `<job>_BGE_Worksheet.xlsm` in Excel, check that the dropdowns
   work, and **save**. Then: `readback <job>.json SAVED.xlsm --out out`. It must say "Excel
   matches the bot's estimate"; if it doesn't, report the lines that differ and stop.
7. **Hand off.** Tell the user what's ready, the incentive and kWh (from Excel), what is still
   open, and that the portal cheat sheet lists every field in screen order. Upload the
   Excel-saved workbook, not the bot's original.

## Output (in `out/<job>/`)

| File | For |
|---|---|
| `_BGE_Worksheet.xlsm` | BGE upload ("Retrofit Lighting Worksheet") after the Excel save |
| `_Cut_Sheets.pdf` | BGE upload ("Manufacturer's Cut Sheets") |
| `_Terms_Acknowledgement.pdf` | Customer signs; BGE needs it |
| `_Exterior_Circuit_Verification.pdf` | Only when pole/flood lighting is on the job |
| `_Proposal_DRAFT.docx` / `.pdf` | Customer, after Ben approves |
| `_Portal_Cheat_Sheet.html` | Whoever types the application into BGE's portal |
| `_QA_INTERNAL.xlsx`, `_package.json` | INTERNAL: findings, per-line estimate |

## When BGE changes the workbook

If `build` stops with "doesn't match the pinned BGE tool version", BGE has issued a new
worksheet. Don't work around it. Tell the user, get the new blank workbook, and update
`prescriptive/template_map.py` (cell map + header checks). Then run
`extract-template --template NEW.xlsm` and the test suite.
