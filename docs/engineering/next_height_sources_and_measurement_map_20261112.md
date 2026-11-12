# Dimension-first footprint, walls, openings and ceiling heights

GPT1 ? 12 November 2026. Experimental Next engine only.

## Source-first sequence

1. Source-native footprint and walls: identify actual outside walls, interior
   faces and partitions, with native PDF path/segment references. A region ring
   is a topology candidate, never a finished-wall/physical-host authority.
2. External dimension chain: associate each outside wall end with the
   dimension's hash/extension station and authentic figure words. A span may
   contain several figured intervals, and an opening-width figure such as
   870 must not steal the whole wall. Missing or conflicting chain: ABSTAIN.
3. Openings: retain the plan's door, window, stacker and panel-lift ink,
   schedule/elevation refs and their physical jamb/host relationships.
   Temporary topology fills are NOT construction walls or deductions.
4. Ceiling height: select either a true FFL-to-FCL vertical section figure,
   or a height and ceiling material in one RCP callout bubble. Multiple
   heights on one plan remain separate by zone, not global defaults.
5. Quantities: wall area = each authenticated finished face length times
   its applicable lining height, minus independently proven actual openings.
   Internal finished face dimensions, not outside footprint measurements, own
   floor finishes; ceiling areas require independently owned RCP zones.

## Height source contracts

python -m planreader_next heights --drawing-type section --pdf source.pdf --page 6 --output heights.json

python -m planreader_next heights --drawing-type rcp --pdf source.pdf --page 8 --output rcp-heights.json

The RCP command supports --rcp-viewport X0 Y0 X1 Y1 to isolate
the actual plan and exclude legend examples. Coordinates are native PDF points;
on a rotated page convert display coordinates via its derotation matrix.
Output is create-only and review-only.

- Section source: one figured height and one original vertical dimension
  segment, with the actual FFL and FCL witnesses at its ends. TP/top plate
  and joinery do not qualify as finished ceiling height.
- RCP source: one unique millimetre figure immediately next to one ceiling
  material code on consecutive lines of the same source PDF text block.
  This catches rotated Maryborough 2400/GRID and 3000/FPB callouts.
  A physically close 1980 fitting dimension and IPF1 on different source
  lines are NOT one ceiling material/height bubble.
- Pairing is source text evidence, not a verified ceiling zone; zone geometry,
  material definition, wall lining extent and physical scope need separate
  source-backed review before heights are used for wall quantities.

Optional building draft review accepts height_source_receipt on a wall plus
height_applies_to_wall_reviewed=true. For RCP-based wall heights, also require
height_ceiling_zone_id. The original source receipt is revalidated and its
figure must match the selected wall height; refs pass into a draft wall row.
A ceiling-zone row may separately attach an RCP height receipt. Invalid
height ABSTAINS while independently verified ceiling area is not removed.

## Verified original-source smoke

- 3Laurel original SHA256 014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e,
  PDF page 7 / index 6, section A-A: 2700 mm FFL-to-FCL. Source word and
  vertical dimension segment refs observed. Nearby 2740 mm TP and 2100 mm
  joinery not promoted as ceiling height.
- Maryborough original SHA256 b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007,
  PDF page 9 / index 8, RCP: 18 height/material pairs found using
  same-text-bubble constraints. Includes 2400/GRID and 3000/FPB; excludes
  false 1980/IPF1 and 2700/WPB legend-style near-pairs. Zone ownership
  still requires review.

The private PDF originals and diagnostics stay on the owner's PC.
Frozen 120, original customer outputs and signed quantities are unchanged.
There is no new official score or customer release claim.

## Optional source RCP rectangle proposals

The --with-source-zone-rectangles option on heights --drawing-type rcp
links each source-owned same-callout material/height text pair to the smallest
uniquely containing source-native original PDF rectangle. If the nearest
two candidate rectangles are within 10 percent of each other, the bubble
ABSTAINS. Multiple same-value bubbles in a rectangle consolidate;
conflicting material or height pairs ABSTAIN. A sheet-wide box alone does
not authenticate a ceiling zone, room, wall or customer quantity.

    python -m planreader_next heights --drawing-type rcp --page 8 --pdf original.pdf --with-source-zone-rectangles --output source-rectangles.json

On real Maryborough page 9 RCP, 18 source height/material pairs produced
13 rectangle candidates and one ambiguity. This is NOT 13 authenticated
ceiling zones, and no m2 customer measure is added.

associate_reviewed_rcp_zone_with_plan_face accepts only exact source refs
and an explicit cross-sheet reviewer-approved relation. The result still has
physical_ceiling_zone_authenticated, wall_finish_to_fcl_authenticated and
commercial_publishable set to false. Applying RCP height to walls additionally
requires proof the lining reaches that ceiling. A source-documented document-
wide FFL/FCL figure does not prove applicability to every room;
room_height_from_ffl_fcl now explicitly marks the room and ceiling-zone scope
unresolved and height_applied_to_any_room false.

## Keep room detection fast and cross-sheet height explicit

The ordinary boundaries / suggest with-boundaries geometry path does NOT
scan every elevation/section for FFL/FCL heights. It reports
CROSS_SHEET_HEIGHT_SOURCE_SCAN_DEFERRED, length_mm=None and
height_applied_to_any_room=false. The old eager cross-sheet scan parsed
three large 3Laurel drawing pages and made a room-boundary regression
take several minutes. The source document height remains extractable
independently via the explicit heights --drawing-type section command.
To attach a section preview during room detection, opt in using
boundaries --with-cross-sheet-height or suggest --with-boundaries
--with-cross-sheet-height, preserving the same source SHA and FFL/FCL
scope-review flag. A document-wide unique FFL-to-FCL result must not
become every room's height or a substitute for the missing plan axis.
