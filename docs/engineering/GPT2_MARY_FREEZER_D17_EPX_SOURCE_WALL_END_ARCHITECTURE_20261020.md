# GPT2 — Original Maryborough FREEZER D17 + EPX finish source gate

**Architecture first / original-source review, 20 October 2026. Do not promote to FIRM or merge without independent reviewer and owner.**

## Observed repository
- Read AGENTS.md / playbook and traced `pb_source_maryborough_physical_room_boundary_shadow`, `pb_source_cold_room_insulated_panel_shadow.SourceColdRoomInsulatedPanelProducer.register_cold_room/authority`, `pb_cross_view_floor_finish_authority.CrossViewFloorFinishProducer.publish`, and `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow`.
- Existing insulated-panel PR #3460 is **not** original W4 authority: it resolves a CORROBORATED room and door-rebate flag from caller polygon, thickness, door IDs, scale and height; competing same-key polygons silently overwrite. GPT2 peer review on #3460 requests fail-closed producer source root/door/W4 verification. Newly merged #3472/#3473 shadows are not downstream FIRM consumers.
- Immutable **original** 31-page Maryborough PDF SHA256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`. Native source coordinates are PDF unrotated pt even though sheet displays 90°.

## Observed original page7 to page11 source
- Original page7 room word `FREEZER` address (7,28,0,0), label `D17` address (7,185,0,0), source D17 native text bbox ≈(494.19,1170.17,506.06,1184.48) pt. Label is **not** physical opening proof.
- Original page11 `FREEZER` address (11,81,0,0); `WA06` address (11,84,0,0) and `WA07` (11,82,0,0) are independent wall system labels. Finish `EPX` at source (11,94,1,0) centred x572.82 y1227.72 pt; another `EPX` plan occurrence is (11,94,0,0). Both must remain distinct physical floor candidates until cross-view region ownership is proven.
- Actual original printed FINISH SCHEDULE EPX line at source page11 (11,241,0,0) (`get_text('words')` block indexing) and `get_text('dict')` table block 242: **ALLNEX / NUTHANE SB POLYURETHANE: MID GREY / MIN. R12 SLIP RATING. 100mm HIGH COVING TO WALL.** Not FT2/FT3 ceramic tiling.
- Original BLACK 0.96pt structural-looking north wall face p7 y=1175.12/1179.44 ends at x476.16 and resumes x521.52. Original p11 at exactly the same two y coordinates: x553.92 and 599.28. Source-local shift x77.76pt maps **both** thick-ink wall ends exactly; nominal x78.00 produces −0.24pt residuals both; rival x43.92 produces +33.84pt residuals both.
- Original D17 gap is approximately 45.36 PDF pt in both views, **but that is NOT scale-authorized opening width**. Thin black 0.48pt interior/filling strokes bridge the gap x476.16–521.28 (p7) and x553.92–599.28 (p11), so an undifferentiated horizontal-line detector could wrongly call the door *structural wall continuity*. Original source path IDs: p7 thick left 53737/53738, right 53734/53736; thin bridge 69318/69326/53740/53741; p11 thick left 2943/2944, right 2940/2942; thin bridge 2946/2949. No source parent/jamb/door semantic is issued by these path numbers alone.

## Inference / blocking gates
- Candidate cross-view **wall-end/source-ink** registration has significant positive support at D17, but does not prove complete W4 inside-face closed physical FREEZER floor, paired WA06/WA07 panel-face owner, finite physical door D17 threshold stroke, scale/figured dimension, source mark ownership vs other EPX floor, or original published page7↔11 same-floor identity.
- A caller-created inner floor polygon plus EPX word is not FIRM. Do not label Freezer as FT2/FT3 or borrow the existing signed Cold Room plain-floor area.

## Proposed source-only next implementation **AFTER architecture approval**
Issue a typed shadow **original D17 structural wall-end/filling-role discriminator** using existing `SourceVisibilityAuthority` original stroke receipts and W4 room face producer; proof must establish two independently published original face ends, 0.96 vs 0.48 source ink roles from original paint/source ancestry, original D17 physical opening identity and parent-owned finite threshold, full p7/p11 source original scope including competing source floor owners. Preserve BOTH EPX occurrences (and any conflicting plan marks), do not infer source closure from fill stroke or physical opening kind from D17 text. Source-only `CANDIDATE` until whole W4 perimeter, original material and physical floor established.

## Required tests and noninfluence
SHA-pinned private original positive thin door crossing vs solid thick wall candidates; synthetic false continuous thick wall, door panel counted as wall, absent/foreign D17 original source, wrong page/revision/snapshot, moved jamb, missing panel face, crossed EPX competing mark, plan EPX vs schedule table EPX, reversed line direction, 0.24 source sampling vs global 2.5pt snap, translation/rotation/order/split invariance, original input unchanged, commercial archive eight unchanged. No frozen truth, expected BOQ, historic m², source file modification, customer release or takeoff in this PR.
