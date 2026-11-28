# Wall corners depend on segment order: W2 endpoint snap (2026-11-28)

Architecture note (AGENTS) for the unrelated-content invariance claim under MAX 7231566401 (triggered by 7231456850).

## Observed
- Picture-only detection (`raster_picture_detection_shadow`) left the segments around two lost rooms on Lot16 sheet 3
  identical, yet a 38.5 pt picture segment present in both runs stopped becoming a wall.
- It survives the motif and wall-strip filters and W2 graph edges in both runs. It first diverges in the snapped node:
  one end lands on the drawn corner in one run and 1.25 pt away in the other, so the wall edge is tilted.
- The ordinary W2 snap (`_snap_geometry_indexed`, 2.5 pt tolerance) walks endpoints in input order and moves each node to
  the running mean of what joined it. Two 2 pt stubs processed after the corner joined it and dragged it; processed before
  it, they formed their own node. Shuffling the same segments moves about 4% of node positions on that sheet.
- Raster geometry sits on a half-point grid, so endpoints exactly one tolerance apart are common.

## Inference
The divergence is order and neighbouring-stub dependence in W2 snapping, not detection, pairing, budgets or tie-breaks
later in W4.

## Built (shadow, default off)
`build_wall_graph_for_viewport(..., order_free_snap_shadow=True)` uses
`pb_wall_room_topology_order_free_snap_shadow.order_free_snap_geometry` with the same tolerance:
- only endpoints of pieces longer than the tolerance place a node, grouped by complete linkage; equally close groupings
  merge only if the whole union fits, otherwise they stay apart;
- shorter pieces' endpoints join the single nearest such node without moving it (an exact tie is not joined), else group
  among themselves the same way;
- node position is the mean of the placing endpoints (exact when they coincide).
No live route: the ordinary producer and every default call are unchanged.

## Proof
- `tests/test_wall_room_topology_order_free_snap_shadow.py`: the tilted-corner case; order and direction shuffles;
  unrelated content including a far crossing; short stubs beside a corner; drafting gap and over-wide gap; chains and
  equidistant ties (abstain); exactly-one-tolerance pairs after rotation; translation and rotation; segment splitting;
  determinism, no mutation, default unchanged, refused option combinations. Mutants of the rules are caught (the one that
  survives differs only by float noise).
- Existing tests that use the W2 graph: pass.

## Lot16 sheet 3 gate (live claim, local; picture-only detection = `raster_picture_detection_shadow`)
| setting | rooms | named rooms |
|---|---|---|
| today | 61 | 2 (WC, LINEN) |
| order-free snap only | 65 | 2 |
| picture detection only | 53 | 1 (WC and LINEN lost, BED 3 gained) |
| both | 58 | 3 (WC, LINEN, BED 3) |

With both, every named room is kept. The 8 outlines lost against today are boxes between dimension lines in the margins
(dimension text inside, no metric floor; checked on a local overlay). Gained: BED 3, the pantry, one small outline beside
the WC (not verified) and two small margin dimension boxes (false; the order-free snap alone also closes them).

## Four-original off/on replay (2026-11-28): NOT SAFE, stays off
Picture detection plus this option, through the all-source-role handoff, off then on:
- 139 customer rows keep every value, element, page and status, but Lot16's nine rows and 58 3Laurel rows change evidence
  ids: both settings rename host walls. The snap alone gives 13 of 22 Lot16 sheet-3 openings new host-wall ids (member
  walls moving at most 0.5 pt) and one opening loses its host.
- Maryborough floor areas (live claim): the snap alone drops the cold room's area, and an area appears on a single
  floor-grid cell.
So the snap changes outlines well beyond the sheet-3 gate, and wall identity by exact coordinates cannot survive it.

### Cold room trace (correction)
The outline is not lost: it still forms (97% the same) but the ring crosses itself, so `geometry_complete` is False and no
area route can use it. First divergent stage is the W2 snap at a corner of thin double-line walls (faces 2.2–2.4 pt apart,
inside the 2.5 pt tolerance): the option joins the closest pair first, across one wall; today's order joined the other
way. Today's node there also depends on order (6 positions over 12 shuffles of the same pieces). Where the tolerance
exceeds a wall's thickness, any endpoint snap decides which faces to join; a design candidate is to never join
endpoints across parallel offset faces. Identity by source-primitive lineage: see
`claude_wall_lineage_identity_design_20261128.md`.

## Not authority
Changes node positions and joins on every page it is switched on for (about one node in ten on Lot16 sheet 3 versus the
ordinary snap), so it needs the signed-row replay before any switch-on. It grants no wall, room, measurement or quantity
authority.

## Benchmark observations that must not influence the rule
Room counts and signed rows are checks only; the rule has no threshold other than the existing snap tolerance.
