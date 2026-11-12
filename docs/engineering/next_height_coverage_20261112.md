# Source-first ceiling height coverage (GPT1, 12 November 2026)

## Owner-approved rule

For 3Laurel, the printed 2700 mm FFL-to-FCL Section A-A figure (original
PDF zero-based page 6) is the standard ceiling and wall-lining height
throughout THIS project unless a different height is explicitly stated.
The section cutting line need not cross every room. Top plate 2740 mm
and joinery 2100 mm are NOT ceiling heights. This authorises nominal
height only, not the existence or area of a physical ceiling plane.

## Read-only original-source height coverage

    python -m planreader_next.ceiling_height_coverage --pdf original.pdf --plan-page 2 --section-page 6 --project-id 3Laurel --owner-authorized --output new-result.json

Creates a JSON result and refuses to overwrite existing files. Every
detected non-cavity region gets the project-standard nominal height,
even if its topology remains ambiguous. Region labels and original
source SHA are retained. Every row carries:
physical_ceiling_zone_authenticated=false,
actual_ceiling_exists_authenticated=false,
measured_ceiling_area_m2=null,
wall_finish_area_eligible=false,
commercial_publishable=false.

An explicit reviewed RCP material+height callout overrides the owner
standard ONLY in its relevant zone. It needs a source-owned figure,
material code, unique containing native rectangle, matching plan label
word ref and a reviewer-attested plan/RCP correspondence. An invalid
or competing local override ABSTAINS, never silently falling back to
the standard.

For Maryborough, there is no validated global FFL/FCL standard, so
the source-RCP case can operate without the 3Laurel 2700 fallback:

    python -m planreader_next.ceiling_height_coverage --pdf original.pdf --plan-page 6 --rcp-page 8 --project-id Maryborough --stroke-pair-wall-faces --output new-rcp-result.json

A dense page may be processed using bounded source-neighbourhood
stroke pairing, or source-native --plan-viewport X0 Y0 X1 Y1. The
20,000 native primitive safety cap is unchanged. For reviewed local
correspondences also pass --reviewed-local-overrides selection.json.
The JSON selection has exact source_sha256, project_id, plan_page_index,
rcp_page_index and a links array. Each link needs region_id,
plan_room_label_word_ref, rcp_page_index, rcp_source_rectangle_ref,
the COMPLETE original height_source_receipt JSON object,
ceiling_zone_id and cross_sheet_correspondence_reviewed=true.
Review alone does not authenticate room geometry or ceiling area.

## Original source verification (private plans stay on owner's computer)

- 3Laurel source SHA 014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e:
  PDF page 3, 15 topology region candidates; 13 nominal 2700mm
  height applications and 2 cavity pockets excluded; 0 metric areas.
  Private result: 3laurel_owner_2700_region_height_coverage_20261112.json.
- Maryborough source SHA b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007:
  PDF page 7 source-neighbourhood trace returned 0 physical room rings.
  PDF page 9 RCP yielded 18 source height/material pairs; all 18 remain
  unassociated with room geometry. A separate RCP pass found 13 candidate
  source rectangles, which ARE NOT finished ceiling-zone boundaries.
  Private result: maryborough_source_rcp_region_height_coverage_gpt1_20261112.json.

## Remaining dependency and separation of work

Cursor must physically reconstruct the Maryborough rooms and connect
plan walls/hosted openings to their ceiling-zone sources, preserving
the 20k cap. GPT MAX owns ORIGINAL PlanReader production outputs and
the frozen 120-item benchmark. This Next-engine height report does not
produce any ceiling m2 or wall-finish m2 from topology-only regions.
No private original plans or benchmark answer files are committed.
