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

## Original plan section-cut to section-height scope

The cross-sheet section-height route now supports an explicit, create-only
source-geometry probe:

    python -m planreader_next heights --drawing-type section --pdf original.pdf --page 6 --with-plan-section-cut-page 2 --output section-cut-candidates.json

This does NOT run during ordinary plan tracing or ordinary height extraction.
It opens the authenticated original drawing for the plan and section sheet,
requires two **same-source text-block** A/A0.7 plan markers, an A-A section
title and twenty original native dashed line segments forming a continuous
source cut. The cut must extend between the original marker endpoints;
missing dashes, wrong section name, nonmatching PDF SHA or multiple markers
ABSTAIN. The extra matching of candidate room-ring polygons to this cut
outputs source-native nonmetric geometry intersections for manual review.

Original pinned 3Laurel PDF plan page 3 / section page 7: A-A markers
and 20 native dashed segments source-match the 2700mm FFL-to-FCL figure.
This cut intersects THREE proposed region geometries: a BED candidate, a
ROBE candidate and a larger abstained connected DINING/ENTRY/KIT/LIVING/WC/
LAUNDRY region. The last is NOT a proven physical single room and neither
BED nor ROBE is automatically assigned 2700mm. There is no proof of an
applicable RCP zone, bulkhead, wall lining extent or finished face yet.

Room scope remains physical_room_height_authenticated=false,
height_applied_to_any_room=false and commercial_publishable=false.
No source drawing geometry, private PDF or original plan screenshot is
included in this public repository. Frozen120 and customer issuers are
unchanged.

## GPT1 completed source height-to-wall-face handoff

Optional, create-only original PDF invocation:

    python -m planreader_next heights --drawing-type section --pdf original.pdf --page 6 --with-plan-section-cut-page 2 --with-plan-wall-face-candidates --output section-to-wall-scopes.json

This runs the original section FFL/FCL receipt through authenticated A-A
plan markers + native dashed line, actual room-region geometry, Cursor's
existing source_wall_inventory region and wall-face IDs, then delivers the
original ceiling-height reference to each matching native wall-face candidate.
Every result carries region_id, single original room label word ref, wall
face item ID, original wall source segment, section source word/segment refs,
topology-only opening interruption candidates and the source FFL-to-FCL figure.
Separate boolean fields distinguish a section passing through the room from
the section line actually crossing that specific wall. Neither proves that
the entire room has the same ceiling height or that the wall lining reaches
the FCL. Both remain source-review candidates with quantity disabled.

Original 3Laurel page 3 / Section A-A page 7: section intersects 3 proposed
regions; two eligible single-label region locators (BED and ROBE) yield
7 source-native wall face reference candidates; one of those seven actual
source face segments intersects the drawn section line itself. The broader
multi-label open region does NOT have a valid single reviewed wall locator
and ABSTAINS. All 7 remain wall_finish_area_eligible=false.

Reviewer-selected RCP cross-sheet option uses:

    python -m planreader_next heights --drawing-type rcp --pdf original.pdf --page 8 --rcp-plan-page 6 --rcp-reviewed-face-selections selected-links.json --output rcp-to-wall-scopes.json

For dense plans, provide source-native --rcp-plan-viewport X0 Y0 X1 Y1
so each bounded tracing pass remains under the 20,000 primitive safety limit.
Selection JSON must be source-owned, for example:

    {
      "source_sha256": "<SHA-256 of original PDF>",
      "plan_page_index": 6,
      "rcp_page_index": 8,
      "links": [
        {
          "region_id": "<region locator ID from walls output>",
          "face_item_id": "<face ID within this region>",
          "room_label_word_ref": "<original label word ref>",
          "rcp_source_rectangle_ref": "<unambiguous RCP rectangle ref>",
          "rcp_height_word_ref": "<original same-bubble height word ref>",
          "cross_sheet_correspondence_reviewed": true
        }
      ]
    }

The programmatic APIs are
section_height_to_plan_face_candidates,
reviewed_rcp_height_to_plan_face_candidates and
reconcile_face_height_sources. They check exact native source refs, region,
face, material/height callout and cross-sheet review. Two height lanes
competing for the SAME wall face (e.g. 2700 section vs 2400 GRID RCP)
ABSTAIN until the correct ceiling zone and any bulkheads or soffits are
physically authenticated. The numeric RCP value never becomes a global
project height.

### Remaining dependency, outside GPT1 source-height lane

These candidates cannot issue wall m2 or opening deductions until
independently authenticated physical wall/finished-face and hosted opening
geometry are available from the geometry lane, including the correct inner
lining face length, complete opening universe and confirmation lining reaches
the relevant FCL. No REVIEW checkbox, geometry proposal, one source word or
one ambiguous room polygon promotes a new customer quantity. The existing
building draft issuer remains default-off and does not ingest candidate
height-face packets as FIRM or official benchmark credit.

Private original PDFs and source-specific diagnostics remain on owner's
machine. Frozen120 and original production customer outputs are unchanged.


## Owner-directed STANDARD height rule: 3Laurel, confirmed 2026-11-12

The owner explicitly settled the height-application question: the **2700 mm
FFL-to-FCL Section A-A height** is the standard height for **ALL ceilings
and wall linings on this project unless an explicit different height is
stated**. We previously over-constrained this by requiring each room to
intersect Section A-A and by treating a local RCP override as a conflict.
That was wrong. A section cut authenticates where the detail was taken;
the owner's project-wide instruction establishes the default application
scope. They are distinct evidence sources.

The project_standard_height_policy selection at the project root must
be tied to the SAME PDF SHA and project_id, carry exactly the source
FFL/FCL section receipt and have owner_authorized=true with the rule
all_walls_and_ceilings_unless_otherwise_stated.

Example (merge this object at the top level of the selection):

    {
      "project_standard_height_policy": {
        "rule": "all_walls_and_ceilings_unless_otherwise_stated",
        "owner_authorized": true,
        "project_id": "3Laurel",
        "source_sha256": "<original file SHA-256>",
        "section_page_index": 6,
        "source_height_receipt": "<exact JSON receipt from heights --drawing-type section>"
      }
    }

The actual source_height_receipt value is a JSON object, not a string.

With this policy, the existing building draft issuer applies the section
height to ALL reviewed wall and ceiling rows without per-room section cuts
or extra height_applies_to_wall_reviewed flags. An explicit reviewed RCP
material-and-height receipt for a local zone overrides 2700 only on that
zone's reviewed wall/ceiling rows; it never changes other rooms.
Invalid or ambiguous local overrides ABSTAIN for that height.

This changes height authority, NOT area authority. Floor/ceiling-area
geometry, internal finished wall-face lengths, true hosted openings and
deductions, bulkheads and lining extents still need independent sources.
The user-directed 2700 default must not leak to Maryborough, Lot16 or
other jobs.


### Automatic project standard extraction and explicit local RCP priority

On the source Section A-A page for 3Laurel, the owner-approved height
selection can be GENERATED FROM THE ORIGINAL PDF, with a create-only output:

    python -m planreader_next heights --drawing-type section --pdf original.pdf --page 6 --owner-standard-for-project 3Laurel --output 3laurel-standard-height.json

Copy the JSON object project_standard_height_policy into the existing
project-level reviewed building selection. On original pinned 3Laurel,
the produced receipt is 2700 mm with original FFL/FCL and dimension-line
source references, and the scope is ALL PROJECT WALLS AND CEILINGS
UNLESS OTHERWISE STATED. The default does not depend on the room
intersecting a section cut. It does not fabricate any wall lengths or area.

When the original source RCP has a material and height printed in the
SAME text bubble, and that material word is exactly the finish-word
already owned by a reviewed ceiling zone, the ceiling draft automatically
chooses that explicit local RCP height over the project standard. Its
original source word/line witnesses remain in the quantity metadata.
When a wall's reviewed height_ceiling_zone_id matches that ceiling zone
and height_applies_to_wall_reviewed is true, the same local height
overrides the standard for that wall. Without a proved wall-to-zone
relation the wall ABSTAINS rather than claiming an unsupported height.
Invalid explicit ceiling height receipts also block linked wall heights
from silently falling back to the standard. The ceiling area, if
independently authenticated, survives a height-only abstention.

If no local RCP height is stated, the 2700mm owner-authorised default
applies. A 2740mm top-plate or 2100mm joinery measurement cannot override
the standard. Height policy is project-specific and cannot apply to
Maryborough/Lot16/Q5446 by inference. All new quantity packets remain
draft-only and do not touch frozen120/customer production scores.
