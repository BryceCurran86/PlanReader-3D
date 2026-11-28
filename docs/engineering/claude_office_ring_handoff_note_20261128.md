# Maryborough Office room outline (P0, MAX 7236315096): handoff and findings

Hub report 7236464810. Local overlays were checked against the original plan sheet and stay on the owner machine.

## Observed (code and original, 28 Nov)
- The centreline face route (`pb_source_room_face_authority`) builds faces from the W4 wall set. That set includes
  floor-tile grid linework and equipment ink, so the Office and Sales labels sit in single tile cells. The Office
  floor row binds its printed explicit area to one such cell: the value does not come from the polygon, the surface
  binding is what is wrong.
- Under the face-aware snap (default off) the scope abstains on the pollution guard. Of the 869 faces under 1% of the
  largest: 207 run along grid ink, 261 along equipment ink, 198 are black only, 203 mixed. About 187 lie inside wall
  strips the layered builder proves from paint; 212 would be needed to pass. With the grid edges removed (offline), the
  plan becomes one open face because doorways are not closed in the wall graph.
- The layered builder closes the Office. Reproduce on the same source and page with
  `build_layered_wall_doorway_room_rings(drawings, source_sha256=..., page_index=..., dark_painted_wall_source=True)`
  and the same call with `door_jamb_returns=True`, combine with `union_room_ring_candidates`, and assign by label with
  `labelled_ring_ownership`. Result: union entry `layered_wall_doorway_room_ring_cb4a83c107bdfd940a26cda54b2ec211`
  (jamb-returns run only), 11 corners, one doorway closure `layered_doorway_closure_1dd9ea1c7ec717a3ab220c29`,
  99.6% of the outline on wall evidence with that closure (92% without). Two small artefacts: a notch at the wall
  switchboards and one black equipment rectangle read as wall paint (a small hole). No metric, finish or quantity
  authority.
- Food Prep is a zone label inside an open kitchen shared with Wash Up; nothing drawn separates them.
- Reachability: no quantity or customer path reads these rings. The app's source-trace preview calls the layered
  builder without `dark_painted_wall_source` or `door_jamb_returns`.

## Inference
- Option (a) (leave proven wall strips out of the pollution ratio) would not fix the Office: even past the guard, its
  face is a tile cell, which the authority would then publish as a room.
- The face route would need both a typed floor-grid exclusion and doorway closures; the ring route has both.

## Proposed (not built; needs MAX)
- AG binds the Office printed area to the ring record above and keeps the false-cell veto; Food Prep stays withheld.
- If the face route is to be fixed as well: a typed floor-grid negative, default off, with its own synthetic proof.

## Must not influence implementation
- The printed room areas, floor rows and any benchmark values. No area-plausibility promotion.

## Tests
`tests/test_floor_grid_room_ring_guard_v1.py` (synthetic): a tile grid leaves the doorway-closed room whole, one tile
cell is not wall supported, narrow dark-walled rooms close, ruled drafting cells give no rooms.
