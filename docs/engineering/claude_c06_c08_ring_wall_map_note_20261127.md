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
paths AND whose centreline lies on the edge line with a positive shared length; closure edges stay closures (never walls).
Report per ring: wall edges with a published wall, only ambiguous walls, no wall; no nearest or longest choice.

## Must not influence
Any expected area, count or room list. Nothing is published, promoted or wired.
