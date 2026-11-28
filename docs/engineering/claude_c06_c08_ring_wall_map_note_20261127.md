# Rooms from double-line walls and their wall identities (tasks C06/C08, 2026-11-27)

Architecture note before the change (AGENTS); asked by MAX 7219675205. No behaviour changes.

## Observed
- The source room-face authority abstains on every double-line layout (`source_room_face_component_ambiguous`).
- The existing layered doorway-ring builder (`build_layered_wall_doorway_room_rings`, `dark_painted_wall_source`) returns exactly
  the inside-face rings on the same synthetic layouts, closing a doorway with its jambs as topology only.
- Its ring edges are owned by native path indices (`layered_wall_strip:<path>`), the same paths the physical wall candidates'
  source primitives name (`d<path>i<item>`). Its edge owners are not physical wall candidate ids, so the live canonical
  composition and the floor-finish export cannot use ring rooms (`floor-finish bounding wall authority incomplete`).
- Maryborough sheet 7: 171 candidate rings (39 thinner than 12 pt, i.e. wall bodies or fixtures); Lot16 18; 3Laurel 54.

## Inference
C06 does not need a second engine. The missing piece for C08 is a proven mapping from each ring edge to the physical wall
candidate(s) drawn on that exact line by that exact source path, with each wall's equivalence state.

## Proposed (report only)
`pb_ring_wall_identity_map_shadow`: for each ring edge, the wall candidates whose source primitive is one of the edge's owner
paths AND whose centreline is parallel to the edge with a positive shared length, on the edge line or behind it (seen from
inside the room), no further than the builder can put a face from a stroked line (half the stroke width, or its 0.8 pt
face-cluster width when larger; this covers the 0.6 pt half width it gives thin merged strokes). Closure edges stay closures
(never walls). Report per ring: wall edges with a published wall, only ambiguous walls, no wall; every match is kept, no
nearest or longest choice. A first version that required the line ON the edge found almost nothing on real sheets.

## Measured (originals, local, candidate rings; counts only)
| sheet | candidate rings | non-closure edges linked | distinct walls linked | of them published |
|---|---|---|---|---|
| Maryborough 7 | 171 | 482 of 750 (was 3) | 168 | 0 |
| Lot16 3 | 18 | 58 of 212 (was 0) | 41 | 0 |
| 3Laurel 3 | 54 | 123 of 678 (was 28) | 135 | 3 |

Unlinked edges (Lot16 / 3Laurel): the face's line has no wall candidate 105 / 369; it has candidates but none along this
face 49 / 180; filled shape 0 / 6. Lot16: 1,899 of 2,094 wall candidates are raster-only and name no source line.
Maryborough has no figured-corroborated ring; which rings are its two floor rooms is not yet checked. What blocks C08
there is wall equivalence ambiguity (no scale), not room closure.

## Must not influence
Any expected area, count or room list. Nothing is published, promoted or wired.
