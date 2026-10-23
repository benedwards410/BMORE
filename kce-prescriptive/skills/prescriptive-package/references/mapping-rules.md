# Mapping rules: audit to BGE workbook (judgment guide)

The script needs exact BGE strings. These are the calls only you can make. When in doubt, ask.

## Existing fixture → `existing`
Pick from `references/existing_fixtures.json` by lamp count, length and wattage:
- "2x4 troffer 3L 32W T8" → `2x4-3L-F32T8` (3F32T8NBF, 88 W)
- "2x2 3-lamp F17" → `2x2-3L-F17T8` (3F17T8NBF-HE, 53 W). BGE rates it at 53 W, not 46 W.
- "8ft 2L 86W strip" → `8ft-2L-F96T8HO` (2F86T8NBF, 160 W)
- "6 in can" with an incandescent lamp → `can-75W-INC`. Ask the lamp wattage if it isn't given.
- "400W MH" → `MH-400W` (1MH0400S, 455 W)
Not on the list: find the code on the workbook's *Wattage Table* tab, add an entry, and show the user.

## Interior / Exterior and space type
- Use BGE's exact space-type strings (dropdowns in the audit sheet). Common: `Office - Open Plan`,
  `Office - Enclosed`, `Lobby - Otherwise`, `Corridor / - Otherwise`, `Restrooms - Otherwise`,
  `Storage room`, `Lounge/breakroom - Otherwise`, `Conference / Meeting Room / Multipurpose`.
- **Docks, canopies, garages, parking**: ask. "Loading dock , interior" and "Parking area , interior"
  are interior space types. Exterior lines need an exterior space type, a lighting zone, and a
  time clock or photocell.
- `over_300`: enclosed rooms of 300 sq ft or less need an occupancy/vacancy sensor, or BGE pays $0
  for their fixtures.

## New product → `product`
- Match to a `catalog/products.json` id. The catalog's measure code follows the product.
- Fixture vs kit: a kit that stays in the old housing is a retrofit-kit code (RL 16x). A new
  fixture that replaces the housing is RL 10x/14x/15x. Must match the product's DLC primary use.
- High bays: get the mounting height (must be 15 ft or more for RL 141-145).
- Strips: `ft_per_fixture` (8 for 8 ft) because RL 111A/111B pay per foot.
- A product that isn't in the catalog: add it **only** with values from its DLC listing or spec
  sheet, set `source`, and put the cut sheet in `catalog/cutsheets/`.

## Sensors → `control`
- Integrated occupancy + daylight (IFS108) → LC 111. It pays only on fixtures inside the daylight
  zone, so set `daylight_qty` per line from the audit. Never assume every fixture is near a window.
- Networked systems (Silvair, Keystone SmartLoop) → LC 101. They need NLC details in the catalog
  (`nlc.occupancy` = "Yes", `nlc.secondary` = Trim / Daylight Harvesting / Zoning / Peak Demand Control / Other).
- Fixtures under 20 W controlled switch automatically to the lower-wattage code (LC 102/112).
- A room that already has controls: set `existing_controls: true`. BGE pays no control incentive there.
- Exterior: `PHOTOCELL` (no incentive) satisfies the time clock/photocell rule.

## Prices
`unit_price` = installed price per fixture **including its sensor**. The catalog holds the default;
put a per-line `unit_price` in the project when this job is priced differently. Recycling (1%)
and tax (3%) come from `config/kce.json`.
