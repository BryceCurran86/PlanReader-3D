# Source-authenticated FT3 occurrence: original page-11 viewport first failure

**Read-only architecture report; no material occurrence, physical floor, signed quantity or benchmark identity is published.**

## Observed repository behavior (exact original source)

- Verified original 31-page Maryborough PDF SHA-256: `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, original page 11, /Rotate=90.
- Original SHA-pinned source census: [Action 38495608233](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38495608233), artifact `11863534943`. Enhanced title/frame ancestry: [Action 38496094529](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38496094529), artifact `11863338719`.
- The producer created **six distinct native FT3 word observation IDs**. Every word independently cleared source-owned native 300/450-DPI raster corroboration. FIVE are physical plan marks; the sixth is a schedule/legend mark and cannot be assigned as a room finish. This is a source *text* proof, not spatial scope or complete material-occurrence-universe authority.
- `segment_page_viewports` presently publishes only two source views: `view_p11_1` LEGEND, status unsupported, no bbox; `view_p11_2` SCHEDULE, status resolved, frame `[438.000000,646.400024,1195.439941,1946.479980]` native PDF pts. **No authenticated FLOOR_FINISH_PLAN viewport exists.**
- Viewing the original rotated source render confirms that purported SCHEDULE rectangle is actually the central physical building/room floor-plan region, not the small source schedule in the lower printing band. It is an incorrect semantic title-to-vector-frame association, not positive evidence that physical rooms are schedule data.
- The source title anchors enumerated by `extract_view_title_anchors` are only `LEGEND`, bbox `[153.672897,197.304001,172.042130,241.398438]`, and `INTERNAL FINISHES SCHEDULE`, bbox `[1274.713745,1621.494629,1293.083008,1799.959595]`. Both original text advances are native vertical `(0,-1)`.
- The visible sheet drawing title in the title block is split across two **different** original native text blocks: `PROP. FLOOR FINISHES &` and `PARTITIONS PLAN`. No independent combined plan-title anchor or source-local physical plan frame is published. Do not promote the sheet title just because it contains `FLOOR FINISHES`.
- Five producer-seen vector frame candidates (native PDF points): `[916.559998,471.200073,1188.719971,646.400024]`, `[251.519989,1591.280029,536.399963,1946.000000]`, `[442.319977,811.040039,666.239990,1275.920044]`, `[251.519989,471.200073,916.559998,1584.560059]`, `[438.000000,646.400024,1195.439941,1946.479980]`. There is NO one uniquely source-certified plan-boundary frame. Largest/nearest/first would be an unsupported tie break.
- Original FT3 plan mark source text blocks are 112 (three), 113 (one), 114 (one). The schedule or legend FT3 mark is separately in source block 262 in the one-page source observation indexing (whole document fitz extraction numbering differs). The source room labels live in different native blocks.
- `pb_source_material_semantic_authority.SourceMaterialSemanticProducer.publish` currently rejects a whole drawing viewport whose *other* text is untrusted, with `SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED`; it cannot publish a commercial occurrence just because a few FT3 words independently corroborate.
- `pb_cross_view_floor_finish_authority.CrossViewFloorFinishProducer.publish` also requires an authenticated material occurrence *plus* one authentic metric floor: same independently proven figured-dimension box, or same-native-block unique source room label and finish occurrence in an authenticated FLOOR_FINISH_PLAN viewport. The visually plausible FT3 marks do **not** satisfy that fallback by their block IDs alone.

## Inferences (not production authority)

1. **First blocker is spatial source scope**, not text recognition: the FT3 occurrence mark texts themselves are original-source corroborated, but no authentic FLOOR_FINISH_PLAN boundary owns them.
2. A candidate generic fix would need an independently verified rotation-aware multi-line title/physical-plan region association, while rejecting adjacent schedules, legends, notes, title block furniture, and CAD table/grid lookalikes. Any overlapping/competing vector frames must abstain.
3. Only after viewport scope closes may independently source-proven physical room face/label and measured floor lineage attach a specific finish occurrence. A 2D native-word position, room label similarity, or bare across-sheet affine transform cannot grant that association.
4. The existing FT3 native schedule-word proof of 24/24 and the upstream semantic fix in GPT3 #2668 are separate from, and insufficient for, occurrence or floor-area authority.

## Proposed source-safe work, ordered

1. Trace `extract_view_title_anchors`, `_wrapped_title_fragments`, `_title_field_owned_regions`, `_frame_candidates_for_title`, `_frame_looks_like_table`, `_frame_resolved_viewports`, `_rotated_semantic_frame_band_partitions` on this page. Record original source title, frame and text-block receipts before changes.
2. Write synthetic positives and adversarial tests: valid rotated single plan and separate schedule; competing plan frames; falsely schedule-shaped wall grids; a real title-block *without* physical plan boundary (must abstain); duplicated or altered title; title split across different source blocks; room face/building rectangle pretending to be schedule frame; rotated 90/270 and input-order/stable-id invariance.
3. In a shadow-only branch, produce a candidate plan viewport **only** when generic original vector + title + partition evidence uniquely proves it; add no artificial bbox on partial evidence. Verify original page11 plus unrelated original Lot16 and Maryborough PWD/FIRM controls.
4. Independently close source-owned *local* material occurrence and exact room/floor membership. Source positive FT3 label alone does not prove a complete finish occurrence universe or attachment to a quantified room. Only then cross existing authority and customer sealing.
5. Run source-closed production with verified PDF SHA, proof of unique signed `floor_finish_area` and complete customer-output bijection. Pass to GPT3 independent frozen identity reconciliation without changing benchmark truth.

## Untouched authority boundaries

Never change the frozen benchmark `full_plan_takeoff_reconciliation_v2` reference, object universe, expected quantities, tolerances, scoring or denominators. Never treat raw FT3 abbreviation as an assumed tile trade without its independently authenticated schedule definition. Do not lower W4 physical room existence guards, fake a second wall face, change source bytes, assume metric scale, bypass material text verification, set a default finish count, or weaken the 20,000-primitive safety bound. Preserve existing FOOD PREP, OFFICE, COLD ROOM FIRM areas and native PWD source label.

## Benchmark observation (evaluation only)

The accepted combined 24 Maryborough + 27 Lot16 development baseline before a new verified customer quantity remains 8/51 matched; a pending source scope repair is not a benchmark match. This benchmark fact did not select any algorithm, threshold or predicted occurrence.
