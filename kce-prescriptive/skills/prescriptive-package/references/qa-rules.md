# QA rules

Levels: **BLOCKER** = don't submit · **ASK** = only the user can answer · **WARN** = look at it · **INFO** = for the file.

| # | Rule | Level | Where it came from |
|---|---|---|---|
| 1 | Audit total = project total; new qty ≤ existing (one-for-one) | BLOCKER | A past job: a 29-troffer room missing from the workbook (fixture and control incentive lost) |
| 2 | Product's DLC category / primary use fits the measure code | BLOCKER | A past job: 8 ft strip model entered on a high-bay measure (RL 142) |
| 3 | DLC lumens inside the measure's band; high bays mounted 15 ft or higher | BLOCKER / ASK | Tech sheet section V |
| 4 | Watts reduced ≥ minimum, efficacy ≥ minimum (per the workbook's formulas) | BLOCKER | Workbook columns BB-BD, AI-AJ |
| 5 | Existing code is on BGE's Wattage Table and in its category dropdown | BLOCKER | Workbook columns K-L |
| 6 | DLC ID, lumens, watts, efficacy known; cut sheet on file for every product and control | BLOCKER | A past job: "MODEL # TBD" kits; tech sheet checklist |
| 7 | One project identity: customer of record, address, city, ZIP, BGE account #, building type, heating fuel, submitter; customer (not KCE) signs the T&C; payee matches | BLOCKER | Past jobs: city/ZIP differed between workbook and T&C; KCE email as the customer's signer; heating fuel blank; T&C paid to Customer while the quote said KCE |
| 9 | Interior/exterior, space type, zone and >300 sq ft use BGE's lists; docks/canopies/garages confirmed | BLOCKER / ASK | A past job: loading-dock high bays entered as exterior wall packs |
| 10 | Controls: occupancy sensor where BGE requires one; exterior has a time clock/photocell; daylight-zone quantity confirmed; NLC details for networked controls | BLOCKER / ASK | Workbook AV/AW/AX; NLC Details tab; a past quote claimed every fixture in the daylight zone |
| 11 | After the Excel save: Excel total = bot estimate, line by line | BLOCKER | Excel is the calculator of record |
| 12 | Every line has a unit price (proposal) | BLOCKER | — |
| 13 | Pole/flood lighting → Exterior Circuit Verification Form attached | INFO | BGE form 202307 |

Also recorded: the workbook's Utility cell is set to BGE (the blank template ships as "Pepco"),
and where the proposal's field wattage differs from the DLC-listed wattage the BGE math uses.
