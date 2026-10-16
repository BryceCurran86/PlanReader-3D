# Source-owned physical plan view: architecture and authority review

## Observed behavior

Read: AGENTS.md, AI_ENGINEERING_PLAYBOOK.md, adopted W1-W10 architecture,
wall/room spec, retired public-tender notice and ci.yml. Traced
`extract_view_title_anchors` -> `_frame_resolved_viewports` ->
`_derived_partitions` -> `segment_page_viewports`, and the F.07 product token,
fingerprint and `is_authoritative_derived_viewport` gates.

`pb_page_title_authority.analyse_cells` independently binds the original
Maryborough split FLOOR FINISHES & PARTITIONS PLAN value to its explicit
Drawing Title field. It also binds Lot16 FLOOR PLAN. These are sheet metadata,
correctly excluded by `_title_field_owned_regions` from local title anchors.
Maryborough page11 consequently has only unsupported LEGEND and SCHEDULE
views; Lot16 page3 only an unsupported LEGEND. Neither has a plan viewport.

Original rendering and native paths show that Maryborough's five extracted
rectangle frames include hatch/building interiors, not five independent views.
They overlap into one source geometry family. Lot16's only ordinary extracted
frame is in its title block; its physical building is primarily raster.
No largest/first/nearest frame or source image tile can be elected as a view.

The existing figured-dimension binder retains source axis and witness geometry.
Its output is candidate geometry, not metric-plane or wall authority. Bare
numeric cells can produce witness-looking alternatives, so metadata/table
geometry must remain excluded and ambiguous bindings must not supply extents.

## Inference

The missing seam is between a source-explicit SHEET drawing role and an
independently source-defined drawing extent. Reclassifying a title-field value
as a local anchor would destroy the correct title-block negative and is rejected.
Source native frames, independently complete orthogonal witness spans and
source room-label structure can instead corroborate a bounded drawing region.
That proposition must remain separate from physical room, scale and quantity.

## Proposed change

Implement an opt-in F.07 source-view proof first. Require one explicit native
metadata plan role; preserve existing local anchors and all competing extents.
Candidate native frame families must be corroborated by complete independent
orthogonal figured witness spans and contained native room-label structure.
Metadata, semantic tables, source borders alone, unrelated numbers, incomplete
witnesses, competing planes and copied producer records must fail closed.
Investigate the raster source seam separately on Lot16; neither image placement
nor page-wide raster coverage may substitute for a physical drawing region.

Synthetic proof and source replay precede promotion. A successful extent must
use the existing SegmentedViewport, private product stamp and derived-authority
gate. A source view never supplies scale, surface ownership, floor finish,
cross-view registration, a customer quantity or a benchmark identity.

## Review and expected abstentions

User explicitly assigned this authority correction and original-source validation.
This authorizes carrying the report through implementation and review. Shadow
geometry remains unavailable to commercial writers until original ownership and
negative proofs pass. Any unresolved original extent is reported as a typed
blocker, not patched with source coordinates or benchmark-specific inputs.

## Benchmark observations excluded from prediction

Source SHA checks, Maryborough's five versus sixth FT3 word and retained three
measured floors, Lot16's 61 room candidates/eight sealed areas are validation
controls. They must not choose a frame, role, threshold or predicted quantity.

## Untouched

Frozen source PDFs/truth/evaluator/tolerances/denominators, source snapshots,
global W2 snap, 20,000 topology safety bound, W10 eligibility and all commercial
quantity/publisher behavior. Claude retains cross-view floor-identity ownership;
GPT1 retains measurement and GPT3 sealing/reconciliation.

## Implemented source proof

`segment_source_page_viewports(source, revision_id=..., page_id=...,
physical_plan_view_shadow=True)` reads only the actual current
`SourceVisibilityProducer` revision bytes. Ordinary `segment_page_viewports`
and the source factory's default behavior remain unchanged.

The reader reuses the original-word text-integrity receipts, source-visible
geometry and `compile_native_dimension_cap_components`. Dimension ink must be
actually stroked, opaque, nonwhite original paint. Two terminated tick/witness
systems establish orthogonal source geometry; numeric values never measure a
room or supply scale. Exact contiguous axes retain all supporting word/cap
alternatives as one geometric component, avoiding duplicate plane enumeration.

Native extent uses every overlapping source frame in the unique room-bearing
family. Raster extent projects all admissible orthogonal native axis components,
requires independently G17-proved original raster supports, and retains source
room/support membership to distinguish connected planes from competing views.
No source image placement, tile, page crop, longest axis or ranked frame owns it.
Metadata/table frames and local competing captions remain excluded. An
incomplete second room-bearing family still blocks election.

The explicit title FIELD and its entire bound VALUE must authenticate. A
separate `RasterTextCorroborationProducer.for_physical_plan_view_shadow` seam
admits a sole unresolved-clip reason only after both original post-clip
300/450-DPI readings agree exactly. It also resolves overlapping OCR fragments
only when every reading matches its unique contiguous original glyph positions
and their union covers EVERY glyph. All readings and source-glyph ownership
are retained. There is no largest/first reading election, fuzzy correction,
case relaxation, alternate engine retry, or changed crop. Registration reuses
the existing two-pixel OCR rounding bound.

Original word ordinals are decoded with `TEXTFLAGS_WORDS`; default rawdict
profiles regroup blocks and include images. Borrowing those ordinals prevented
the source-owned PARTITIONS run from resolving. The correction is isolated to
the new shadow glyph proof; ordinary text/word corroboration is unchanged.

The existing private F.07 product token and complete-payload fingerprint seal
the result. `adapt_f07_viewport_to_migration` additionally rejects relabeling
its immutable document/revision/SHA/snapshot through a caller context. The
source view is a bounded component; `whole_sheet_plan_universe_proven=False`
and `metric_authority_granted=False` are explicit.

## Original-source validation

Maryborough page 11, original SHA
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`,
produces one authenticated `floor_finish_plan` in native PDF points:
`(251.519989, 471.200073, 1195.439941, 1946.479980)`.
All five native frames remain in its proof. LEGEND and INTERNAL FINISHES
SCHEDULE remain unsupported. This does not restore the rejected schedule
association from #2689. Source Drawing and PARTITIONS typography produces
overlapping OCR readings; exact original glyph ownership resolves them.
M-AMB/F-AMB trace-unavailable labels remain untrusted and own no room.

Lot16 page 3, original SHA
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`,
produces one authenticated `floor_plan` in native PDF points:
`(186.600006, 98.520004, 1128.719971, 624.839966)`.
Its title-block rectangle never supplies the extent. The source proof retains
224 plane alternatives and 21 independently producer-proved raster support
records. Source raster augmentation is explicit audit preparation, not a
mutation by the viewport reader.

Both results pass the existing downstream migration ownership boundary and
retain original published snapshots and default segmentation. Replay code:
`tools/diag_source_owned_physical_plan_view.py`. JSON receipts and source overlays
are produced from the original PDFs; serialized artifacts are review evidence,
not substitutes for in-process producer seals.

## Authority review

Synthetic positives, real source replays, table/metadata/hidden-title negatives,
incomplete/competing families, supported rotation/translation/scaling,
splitting/order/page-expansion controls, deterministic replay, mutation/stale
source, copied products and cross-document context tests cover the new seam.
Existing floor seal, publication, F.07, source semantic and native dimension
tests remain required. Frozen sources/truth/evaluator and commercial production
wiring are not modified. Downstream work must explicitly consume the new
source-addressed shadow API; view authentication alone never closes cross-view
floor ownership or metric registration.
