# Maryborough original role runtime: source-owned OCR proof lifetime

**Date:** 7 November 2026 | **Owner:** GPT MAX | **Status:** bounded runtime implementation (no FIRM or scoring change)

## Actual diagnosis

A protected SHA-original Maryborough 31-page role run (`42324832506`) completed wall, room-area and floor-finish stages but timed out (35 minutes) inside:
`CrossViewCeilingFinishProducer.publish -> SourceMaterialSemanticProducer.publish -> _recover_admissible_viewport_words -> RasterTextCorroborationProducer.publish -> Tesseract extract_lines`.

Observed in `pb_source_material_semantic_authority.py`: `SourceMaterialSemanticProducer.__init__` unconditionally constructs a new ordinary `RasterTextCorroborationProducer` for each floor/ceiling publisher, losing its already authenticated positive **and negative** OCR memo.

Observed in `pb_raster_text_corroboration_authority.py`: `RasterTextCorroborationProducer.publish` stores results by the full document/revision/source-SHA/snapshot/observation selector, and on each cache hit rechecks that the producer's immutable bytes still match the requested source SHA. Backend is chosen once when a producer is constructed. The separate `for_physical_plan_view_shadow` carries a different clip-only policy and cannot be substituted.

## Bounded implementation

Share **only the existing ordinary word raster producer** between live `SourceMaterialSemanticProducer` instances that refer to the **identical** `SourceVisibilityProducer` object. Use a source-owned strong reference and a lock for constructor races, with no cross-source global proof. A floor material producer may be released before its ceiling peer is constructed; weak references alone would discard the OCR proof too early. The source/raster reference cycle is ordinary Python GC-managed and is released when the source itself becomes unreachable. The first material consumer chooses the production OCR backend once, and all later material consumers of that same immutable source keep the same backend. Reject any cached producer with the wrong source, underlying source observation producer or clip-only policy, rather than reuse it.

Keep independent material definition/occurrence/viewport stores, complete source scope resolution and `_plan_raster` physically isolated. No extra pass or relaxation of source/partition/page/text/mask authority, no geometry, 2.5 pt snap, 20k cap, scale, FIRM quantity, customer projection or benchmark change.

## Tests and acceptance

1. Two material producers and an opted-in RCP material producer of exactly the same source share the one ordinary raster object; source identity, snapshot/word memo and fixed backend stay the same.
2. A second independent producer-owned source never reuses this OCR object, even if identifiers happen to match.
3. Separate clip-only physical-plan raster producer is not the ordinary object and retains its policy.
4. A poisoned foreign-source or clip-only entry fails closed; a released floor material producer does not discard the memo while the source is live, and source/raster cycles collect when the source is released.
5. Existing source-tamper invalidation remains in `RasterTextCorroborationProducer.publish`; no rewriting its memo.
6. Final-head focused Python 3.13 and 3.14 CI, clean signed/customer Lot16 eight and Maryborough three private-original retention, then one bounded full Maryborough role before a merge. If original run still times out or source/customer bodies change, remain DRAFT.

This is **a runtime performance repair**. It creates zero new FIRM/customer quantities and does not change the frozen 120 denominator or the last provisional 9/120 result.
