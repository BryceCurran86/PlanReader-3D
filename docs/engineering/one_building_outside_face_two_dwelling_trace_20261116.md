# One outside-facing building wall walk, not two dwelling perimeters

**PlanReader original source-first tracer — child of PR #4389, 16 Nov 2026.**

## What this fixes

A consistent clockwise/left-turn walk can follow a real physical wall and
close a legitimate **dwelling/room loop**, yet that ring is **not** necessarily
the outside-facing boundary of the BUILDING. This is the case in the original
3Laurel: two separate occupied dwellings within one attached footprint,
divided by a genuine 260 mm C.S.R party-wall system. Original source
classifies the dividing wall on a CAD layer called
`Enclosure_WallExternal`, but its physical role is **internal shared**.

`pb_source_unbounded_building_face_walk_shadow.py` introduces an explicit
unbounded-outside-face traversal with **NO guessed wall joins**:

- Receives actual original source-owned wall bar polygons and native
  source path IDs, plus the actual preflight's already-computed geometry
  union that includes independently native-hosted window, swing, sliding
  and garage-door continuity bridges. No new PDF decode, no OCR, no new
  opening detector, no synthetic doorway to inflate wall inventory.
- Extracts actual bounded *free-space* regions from that geometric wall
  network; requires identified occupied regions on **both sides** of any
  source candidate party wall. If either side leaks into the unbounded
  outside, the building's outside face is not authenticated.
- Walks the **exterior boundary** of the unique original wall network,
  normalised clockwise in PDF screen coordinates and closing at precisely
  its initial point. A PARTY wall may join outside wall edges at top/bottom,
  but cannot itself be a longitudinal outside-facing wall.
- Retains original outside wall-source IDs, explicitly excludes the
  internal party path IDs, and rejects competing closed components,
  additional uncontained structural wall bars, or any named outdoor
  ALFRESCO/PORCH inside the supposed enclosed footprint.
- Returns **CANDIDATE ONLY**. No real building footprint material or wall
  face, any door/window/ceiling/floor finish, customer row, frozen120 item,
  or quantified length/area is authorised.

The source-first preflight only runs this additional analysis when the
existing independent native source role detector has found a party wall.
It reuses the already-calculated wall union, so **no second expensive
physical PDF/31-page extraction** is introduced. The resulting
`source_outside_face_walk` is available in the original-app preview
JSON. When and only when both sides actually close as source geometry, it
can render the *candidate* blue outside contour; purple remains the
physical inter-dwelling wall. On the original incomplete source it draws
no invented building ring and records the exact remaining blocker.

## Verification

Eight new generic tests include one building/two occupied dwellings
with a real party wall, unique clockwise outer ring (party path NOT an
external owner); missing far dwelling outer wall; both source room labels
on one side; no source party; an outdoor ALFRESCO incorrectly in the
enclosure; a detached unexplained structural wall; and malformed owner
geometry. The pre-existing single-dwelling source path is preserved.
70 focused original-room/trace and new tests PASS locally with Ruff
F821/F823 and compile checks.

Unmodified original 3Laurel page index 2 on Bryce's PC: original native
PARTY-WALL source paths 1139,1027,1029,1031 found; outside-face walker
**ABSTAINS** `source_dwelling_region_still_open_to_outside`, observing
four closed geometric subregion candidates, but neither independently
owned complete dwelling zone can yet be source-proven on both sides.
The existing source preflight retains the explicit
`source_party_wall_is_internal_not_building_outer_boundary` and
**130 genuine source wall bands outside** the previously rejected loop.
No customer/benchmark score promotion is made.

Next: recover missing right-house/garage hosted wall junctions from
original source; a true complete shared outer face must be source-closed
before any approved customer billable footprint/room output. Avoid
faking an exterior perimeter by taking the first clockwise unit cycle
or drawing an inferred box around the two dwellings.
