# Floor-grid linework as typed negative evidence (report only; MAX 7239832358)

## Observed
- On one original plan sheet the floor-tile grid (light grey, 0.24 pt) is in the W4 wall set. The Office and Sales
  labels sit in single tile cells and the Office floor row's printed area is bound to one such cell
  (`claude_office_ring_handoff_note_20261128.md`). No stage records that these lines are a floor pattern.

## Inference
- A floor grid is a lattice: four or more equally spaced parallel rules, in both axis directions, in one light pen,
  crossing each other. Walls drawn as two faces alternate narrow and wide spacing, so they are never constant pitch.

## Proposed (this change: report only)
`pb_floor_grid_linework_shadow.floor_grid_lattices(drawings)` returns lattice records (pen, pitches, rule counts,
source (path, item) ids). A wall candidate whose source primitives are all lattice items is grid-only. Nothing is
removed, withheld or published; no live path imports it. A publication guard, if wanted, is a separate default-off
change with its own retention replay.

## Limits
- Light pens only (mean colour at least 0.25): a black grid is not flagged, so walls drawn as single black lines at a
  regular spacing are not at risk.
- A grey table is also a lattice; tables are not walls, so flagging them is correct for wall evidence.
- Pitch below 8 pt is left to the existing hatch handling.

## Original plan sheets (local, counts only)
- Maryborough: 2 lattices (228 line items, 0.6 s). Of 683 rooms the centreline route publishes on that sheet, 241 have
  at least 90% of their outline on lattice lines alone (tile cells) and 182 more have 50 to 90%. Of 3,797 saved wall
  candidates 243 lie wholly on lattice lines (geometric match, not source ids) and 1,546 of 7,681 wall edges do.
- 3Laurel: 9 small lattices; checked locally on the sheet, each is a tiled area and no wall is flagged.
- Lot16 (raster walls): none.

## Synthetic proof
17 tests: square, rectangular and split grids, two offset rooms, shuffled and shifted inputs, black grid, double-line
walls, stairs, diagonal hatch, irregular and short grids, hatch pitch, filled shapes, stepped lines, dark walls over
grid lines, tile-cell shares, and grid-only wall ids. Mutants: all caught but an early-exit duplicate and the second
half of the crossing test (equivalent results).

## Must not influence implementation
Room areas, floor rows, benchmark values.
