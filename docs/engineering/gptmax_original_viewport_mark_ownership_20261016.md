# GPT MAX — original F.07 ownership of native STACKER/datum words

Tracking #2396. **Read-only diagnostic, no measurement or authority promotion.**

## Observed repository architecture

Files read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, and `.github/workflows/ci.yml`. Traced functions:

- `pb_page_title_authority.analyse_page` → `resolve_document`: actual sheet identity comes from original title-block authority, never PDF index or marker.
- `pb_viewport_segmentation.segment_page_viewports` → `is_segment_page_viewports_product`: original F.07 publisher and token; only a unique RESOLVED vector-framed viewport supports candidate source word ownership.
- `pb_viewport_dimension_binding.extract_dimension_evidence_by_viewport`: independently scopes all native word bboxes and both segment endpoints before F.13 figures are anchor-bound; NOT called as authority here.
- `pb_opening_elevation_frame_area_authority`: requires two independent orthogonal native-figured spans around one closed frame and exactly one type mark; not a duplicated label or height convention.
- `pb_opening_host_binding_authority._resolve_raster_source_band_host_from_records`: physically source-owned ends, flanks, local W4 chain and competitor equivalence required before host.
- Previously merged `tools/diag_gptmax_cross_view_native_marks.py`: original SHA pinned Lot16 index 2 FLOOR PLAN and index 4 ELEVATIONS each contain one native `2127 STACKER` mark. Native elevation has TWO distinct `2100`, TWO distinct `2590` and repeated FSL/JL datums.

## Inference — unproved

The lower view of original elevation sheet may own both `2127 STACKER` and the lower `2100` word. Even one F.07 viewport containing both only proves **view membership**, not that the figure measures the stacker's exact vertical opening. `2127` is an unproven ordered height/width grammar. `5.67 m²` STACKER is an unsigned hypothesis, not a ninth accepted quantity. A separate upper `2100` cannot be selected by proximity or first-match.

## Implemented read-only hypothesis

`tools/diag_gptmax_original_viewport_mark_ownership.py` runs the original SHA-checked PDF through the existing page-title reader and F.07 segmentation. It records complete native words, ALL containing original F.07 viewports (including invalid, unsupported or competing views), original title-block field data, and uniquely complete RESOLVED-vector-frame membership if and only if the token is valid and no competing RESOLVED/DERIVED frame owns the whole text box. The tool neither manufactures an authenticated viewport nor calls F.13 or a producer authority. Physical cross-view identity, kind, host, per-opening width/height, counts and FIRM always remain false.

18 synthetic tests cover valid containment, clipping, competing scopes, derived/untrusted viewports, duplicated native labels, datum on a different view, source word/input-order metamorphism, independent title metadata, invalid pages and duplicate F.07 IDs. Original SHA-pinned GitHub Actions replay checks PDF index 2 and 4 and publishes a candidate-only evidence artifact.

## Next source-first gate

Check whether index 4's `2127 STACKER` and lower `2100` have the same **positively authenticated** F.07 elevation-subview membership. If not, abstain and audit vector-frame ownership. If yes, F.13 must prove the figure's OWN endpoints and opening-frame top/base; a separate credible horizontal dimension and instance-specific p3↔p5 identity must still be established. No blanket `2100` door height.

Source PDFs, historical signed receipts, original 21/15/9/8, default 2.5 pt snap, 4 pt structural rule, 20,000 raster cap, commercial output and frozen Full Plan V2 are unchanged. Expected benchmark values played no role.
