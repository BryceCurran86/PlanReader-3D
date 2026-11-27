# A wall crossing drawn through is read as a door (task C12, 2026-11-27)

Architecture note before the change (AGENTS); asked by MAX 7219675205 ("generic continuation witness").

## Observed (synthetic)
A cross junction whose stem faces are drawn straight through the crossing wall yields one corroborated, hosted
`jamb_bounded_two_face_interruption`: the two stem pieces inside the wall satisfy the jamb test. Eight real-door cases
(including a door touching a T stem on one side) are found correctly.

## Inference
A jamb ends at the wall faces. When BOTH "jambs" continue collinearly outward beyond BOTH faces, they are the faces of a wall
passing through, not jambs.

## Proposed (opt-in, default off)
`SourceVisibilityProducer(crossing_wall_negative_shadow=True)`: in `_visible_structural_candidates`, drop a support whose
left and right jamb each have a collinear source segment continuing from both of their ends away from the wall. A door beside
a stem (continuation on one side, or on one jamb only) is kept. It can only remove candidates.

## Must not influence
Any drawing count or expected opening number. Originals before/after are required before any default change.
