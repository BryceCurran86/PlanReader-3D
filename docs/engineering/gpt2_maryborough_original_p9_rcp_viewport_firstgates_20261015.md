# GPT2 original Maryborough RCP: source-positive viewport and ceiling-finish first gates

**Architecture proposal only — AGENTS.md first deliverable.** Tracking #2009.
Exact immutable original SHA: `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.
Never treat a resolved schedule, proposed RCP, raw ceiling code, label/area match or title alone as an authenticated physical RCP view.

## Repository files read and real functions traced

Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`,
`docs/wall_topology_observability_architecture.md`,
`docs/planreader_wall_room_topology_spec.md`,
`docs/planreader_public_tender_benchmarks.md` (retired), and `.github/workflows/ci.yml`.

Source path:
`pb_viewport_segmentation.segment_page_viewports`
→ `extract_view_title_anchors`, `extract_vector_frames`,
`_frame_resolved_viewports`, `_rotated_semantic_frame_band_partitions`,
`validate_non_overlapping_viewports` →
`pb_cross_view_ceiling_finish_authority._rcp_viewports` →
`CrossViewCeilingFinishProducer.publish` →
`pb_source_material_semantic_authority.SourceMaterialSemanticProducer.publish` /
`SourceMaterialSemanticAuthority.resolve_occurrences` →
source-owned native ceiling label/occurrence block and canonical room →
separate ceiling metric/quantity publication → independent customer seal.
The producer requires resolved or authenticated derived RCP, authenticated
source material definition and occurrence on its exact RCP viewport, source
snapshot parity, same source native block/partition ownership, one exact
room label and unique canonical source face. Bounding boxes do not supply
physical room correspondence between plans.

## OBSERVED original SHA-pinned source (not invented plan geometry)

Original [Actions 38083246582](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38083246582),
artifact **11681033550**, independently downloaded and inspected:
- Original page **9**, native 90-degree rotated PDF, **8** original native
  vector frame candidates.
- Original `view_p9_2`, title `REFLECTED CEILING PLAN`, native title
  bbox `(1265.630493,197.572418,1277.555176,309.558594)`,
  direction `(0,-1)`: ZERO source title-owned qualifying frame candidates,
  status **UNSUPPORTED**, `bounding_box=None`,
  `first_gate=missing_source_viewport_boundary`.
- Independent `view_p9_4`: `CEILING FINISHES SCHEDULE`,
  status **RESOLVED**, authentic native source-closed table frame
  `(279.839996,471.200073,1217.039917,1376.719971)`.
  A valid schedule/definition is NOT occurrence placement.
- Distinct `view_p9_5` title `PROP. REFLECTED CEILING PLAN`: original
  `DERIVED` viewport native bbox
  `(0,1379.682617,1684,2384)`, source `title_partition`.
  The derived *proposed* region must NOT be lent to original view_p9_2.
- Original `view_p9_1`, `view_p9_3` LEGEND unsupported. Page 11
  original INTERNAL FINISHES SCHEDULE is unsupported separately from the
  actual floor-finish plan. Keep the negatives.

Current source partitioner `_rotated_semantic_frame_band_partitions` only
promotes a side band if the source-owned resolved semantic-frame separator has
EXACTLY one original plan title in it, zero competing title of any drawing
kind, no other framed viewport overlap, a genuine native bounding region and
positive drawing primitives. In the original p9 source it has not established
those conditions for **the original RCP view**. DO NOT choose the nearest one
of eight frames; `_nearest_native_frames_to_title` is already diagnostic only.

The existing full original room handoff [38253592536](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38253592536),
artifact 11750297601: zero independently source-closed actual
ceiling-lining quantities and zero source finish floor quantities. Existing
Food Prep/Office/Cold Room area rows do NOT imply ceiling areas.

## INFERENCE only

The original RCP might be physically bounded by native painted drawing
geometry that current vector-frame extraction or title partitioning fails to
bind. It may alternatively share source regions with other title/legend
cells such that authentic unique viewport proof genuinely does not exist.
The existing result is NOT evidence that its extent equals the proposed RCP,
all-page printable bounds or the ceiling schedule frame. The original may
have no independently provable source-native physical room finish placement.

## PROPOSED smallest investigation after independent review

1. Replay exact original PDF with its original SHA/revision and source page-9
   producer; capture all vector frames, their path/item/ink producer IDs,
   explicit titles/90-degree directions, calibrated visual/native coordinate
   transforms and **all** independent sibling regions. Treat candidate
   discovery only; do not derive bounds from labels or nearest frames.
2. For view_p9_2, test each structural frame / separator candidate for
   complete original native source ancestry, exact title-to-frame ownership,
   all competing original LEGEND/schedule/proposed-RCP title rivals, duplicate
   enclosed titles, overlap, orientation and nonzero actual drawing contents.
   Every surviving alternative is reported and causes ABSTAIN if nonunique.
3. If no complete producer-owned frame exists, test independent typed
   source primitive connected-component enclosure or raster physical ink
   source ownership, **without** automatic whole-page bounding fallback or
   raising low-confidence segmentation to RESOLVED. Retain absolute path/item
   identity and source snapshot; never choose largest/nearest geometric shape.
4. Positive tests: unique genuine title/frame and distinct resolved schedule;
   metamorphic translations, rotations (0/90/180/270) and uniform scale;
   content-preserving input reorder/fragment splitting. Negative tests:
   source text title-only, three competing frames, merely white-filled mask,
   structural GRID look-alike, native schedule cell as source RCP wall,
   overlapping current derived proposed view, two repeated RCP titles,
   clip loss, foreign view snapshot, stale producer seal and target expansion.
5. Only independent F07 source-producer approval permits a *separate*
   production change for an authentic unique original RCP. Then test
   `SourceMaterialSemanticAuthority` definition and original RCP *occurrence*
   with exact word/block/partition, source line/glyph/clip/ink and publisher
   records. The ceiling quantity still requires canonical physical room
   uniqueness and independently authenticated metric floor/ceiling area:
   no bare ceiling material code, label matching, wall height default, title
   scale or page-points² conversion.
6. Run unchanged real p9 ceiling schedule/proposed RCP positive controls and
   page11 false schedule/FT3 GRID negatives in original SHA CI; check original
   Food Prep/Office/Cold Room, 8 Lot16 sealed openings, and all V2 truth.

## Explicit excluded inputs / release boundary

No project-specific coordinates, source-title literal or frozen benchmark
values enter a production classifier. Original data above are diagnostic
witness fixtures only; any correction must be generic source-role evidence.
Do not edit producer, source PDF, W2 global 2.5pt tolerance, GRID opposition,
RCP material mappings, canonical floor authority, customer-output seals,
legacy signed fingerprints, evaluator or frozen original 24/27 denominator.
No FIRM, ceiling quantity, source-defined material occurrence or newly matched
benchmark item was produced. **Stop at architecture-only PR for review,
then continue other independent tasks in GPT2.**
