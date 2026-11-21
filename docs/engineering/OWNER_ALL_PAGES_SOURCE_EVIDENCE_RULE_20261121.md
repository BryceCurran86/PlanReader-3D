# OWNER RULE — Every page is potential source evidence (21 November 2026)

**Authority:** owner directive. Applies to the ORIGINAL PlanReader app and to
**every plan set and document package**, not to a named benchmark project. The
rule must be enforced before declaring an object absent, unresolved, or ready
for commercial customer output.

## Principle

**Never silently ignore any source page.** Each page, and each independently
bounded view on that page, must be discoverable as potential evidence for the
whole building. A title or sheet category does not mean its contents are
irrelevant. A page may contribute location, dimensions, identity, geometry,
material, height, exclusions, authority, revision or a conflict; a page that
truly supplies no relevant evidence must be explicitly recorded as reviewed,
not assumed absent or discarded. Source pages are evidence, not benchmark
answers.

Many sheets have **mixed roles**: an "internal elevations" page can contain an
enlarged floor PLAN inset, four ELEVATIONS, notes, dimensions and a finish
schedule simultaneously. The role is attached to each bounded viewport,
not assigned once to the whole page and then used to suppress all remaining
views.

## Required pipeline

1. **Full-document source census before a final verdict.** Establish the
   authenticated document bytes/SHA/revision and complete page count; record
   every page's source index, visible title, available source text/vector/
   raster/annotation/legend and recognized viewports. An unknown or
   unprocessed page must be a visible coverage gap, never a silent success.
   PDFs, engineering drawings, specifications and schedules in the accepted
   package require the same provenance discipline. Scan/index once and reuse
   scoped evidence; do not rerun all geometry/OCR for every opening.
2. **Per-viewport source roles.** The same page can contain plans, detailed
   plans, elevations, sections, door/window schedules, finish/ceiling
   schedules, legends, structural details, setouts, notes, material
   specifications, revisions and exclusions. Store **all** supported roles,
   source observation IDs and native path/word references. Unknown roles
   remain discoverable, with an explicit first unknown/unreadable gate.
3. **Canonical physical topology once.** Derive original building and room
   wall traces, openings, window/door locations and wall junctions from
   authenticated physical plan viewports. A detail, repeated elevation,
   door schedule or legend is not another installed door/wall/room.
4. **Cross-sheet evidence reconciliation before object is declared missing.**
   For each physical opening, follow its plan mark/callout through uniquely
   registered enlarged plan insets, elevations, sections, detail/legend and
   relevant door/window schedule. Transfer its source-proven wall section
   ends, jamb geometry, orientation, width, frame/head, type and special
   exceptions only after verifying scale, orientation, transform,
   page/viewport, original source identity and unique physical instance.
   The same two wall sections may be collinear across an interruption or
   meet at an angled/perpendicular corner. Record competing references.
5. **Separate evidence from commercial promotion.** A cross-sheet detail is
   an additional witness, not permission to invent a wall, select a nearest
   host, assign a missing dimension, use a blanket height default, duplicate
   an opening or bypass canonical physical host/frame/quantity issuers.
   Confirmed source-specific measurements override provisional assumptions.
   Preserve wall above a real frame, and close a doorway for room topology
   only, never as an actual full-height wall.
6. **Visible failure and review report.** For each page, record status
   `REVIEWED_USED`, `REVIEWED_NO_RELEVANT_EVIDENCE`,
   `UNREADABLE`, `NOT_YET_REVIEWED` or `CONFLICT`, with exact source
   scope and reason. For each opening/room/wall/finish, report the contributing
   pages and viewports, matched or competing source IDs and the first
   missing authority gate. Never report complete source coverage if any
   page is unreviewed or unreadable. Keep one physical opening identity
   even when referenced on multiple sheets.

## Cross-plan acceptance tests

- Mixed-sheet positive: an "internal elevations" sheet with an enlarged
  floor-plan inset contributes two source-proven wall ends to an opening
  on the main plan; it does **not** mint a second installed opening.
- Other positive: the same opening receives a real scheduled width and
  height, section/elevation frame datum and source-verified room boundary.
- Junction positive: two source-proven wall sections may meet at 90° or
  another angle. A rule demanding only collinear opposite wall segments is
  invalid.
- Negative: duplicate marks on multiple views, changed revision/source SHA,
  competing geometric registrations, incorrect scale/rotation, misleading
  nearest room labels, wrong door schedule, unrelated legend symbols and
  unreadable pages cannot silently promote quantity.
- Provenance/inventory: the exact authenticated document page count equals
  the recorded page census with no silent drops. Output every no-evidence/
  conflict/unknown decision with a reason, without multiplying canonical
  installed doors.
- Release: verify unchanged benchmark source and independent original
  physical, metric, signed customer and regression retention outputs on
  the existing exact-head original engine; no source PDFs in public CI.

## What already exists versus work still required

- Existing `pb_source_floor_plan_page_scope.py` deliberately separates
  plan-topology pages from supporting evidence pages to prevent false extra
  walls and openings. **Keep that distinction**. Its positively non-plan
  classification must NEVER be interpreted as "ignore every viewport".
- Existing `pb_live_wall_opening_authority_composition.py` has
  `evidence_page_ids` and native opening-to-host scopes; existing
  cross-sheet registration and original visibility producers provide part
  of the architecture. Reuse them instead of creating a second quantity
  pipeline or a competing trace.
- Complete all-viewport census, general source-to-parent opening/room
  registration and downstream issuer consumption still need verified
  implementation. A review-only check or this written rule is **not**
  evidence of full commercial implementation.

**Concrete source illustration, not a production selector:** The authenticated
31-page Maryborough architectural PDF has main floor plan A110 on PDF page 7,
amenities A500–A503 on PDF pages 24–27 containing enlarged plan insets as
well as elevations, and A600 door schedule on PDF page 28. D07–D13 labels
repeat across these views; the repeated witnesses must enrich the **same**
installed door, not manufacture duplicates. All production algorithms remain
drawing-agnostic and treat the same types of viewports on any other project.
