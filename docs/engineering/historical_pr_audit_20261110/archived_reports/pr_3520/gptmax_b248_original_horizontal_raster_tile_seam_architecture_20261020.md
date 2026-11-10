# GPT MAX — b248 original horizontal raster-tile source-continuity architecture (2026-10-20)

**Stage:** FIRST DELIVERABLE / ARCHITECTURE ONLY / REVIEW REQUIRED. Tracker #2396; coordination #3462. No production implementation, authority promotion, or benchmark release is authorized by this file.

## Compliance and actual source

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/wall_topology_observability_architecture.md`, `docs/planreader_wall_room_topology_spec.md`, `docs/planreader_public_tender_benchmarks.md`, `.github/workflows/ci.yml`, the Lot16 source-host queue, existing raster seam code/tests and original image-XObject registration shadow. Traced `SourceVisibilityProducer._proven_raster_opening_flank_boxes` through producer-owned W2/W4/physical equivalence into `OpeningHostBindingProducer.publish` / `_resolve_raster_source_band_host_from_records`, then `OpeningHostFrameProducer._scope_bindings`. Metric, canonical, FIRM, customer and frozen-evaluator seams stay downstream and **unmodified**.

Owner-private original `1. Construction Plans - Lot 16 Power (REV E).pdf`: actual SHA-256 `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, 13 pages. Independently re-opened original page 3 in PyMuPDF from a copy obtained through the owner's ChatGPT file library, **not** a GitHub binary, snapshot alias, synthetic drawing or holdout truth. No original PDF or image pixels are committed here.

## OBSERVED — concrete first failure and independently checked native source

Archived selected-root b248 physical opening `physical_opening_existence_b248972669988c108ebc90c6ca3908fd` has origin (606, 197.76) PDF pt, vertical axis (0,1), extent 45.36 pt. The archived producer's first host failure is `no_authenticated_host_wall_band / raster_source_band_left_source_primitive_unmapped`; frame then abstains because host is unavailable. This is **not** a missing opening or host-absence proof.

The opening's vertical source interval y=197.76–243.12 crosses the original page-3 raster-image tile boundary **y=210.48** at x around 606. That boundary separates two independently identified and positively axis-aligned/unmirrored image placements:

| Original PDF image | Native placement PDF pt | Native pixels | Original image SHA-256 |
|---|---|---|---|
| xref **96** (upper) | (476.16, 0.00, 714.36, 210.48) | 993 × 877 | `42ec5a207ef7ae742b7cf6f6b586e17ca1e4328db53477f3c12b691598277759` |
| xref **95** (lower) | (476.16, 210.48, 714.36, 841.92) | 993 × 2631 | `e51ec938d3a773cf74a7759ca3cbe792736c230d81d47237a28fd4e05c74429e` |

Original native image pixel read, at SOURCE coordinate x=605.04 PDF pt over y=203.00–218.00, gives 32 distinct bottom-native image rows from xref96 and 32 distinct top-native image rows from xref95. **All 64 examined original pixel rows were dark** (each RGB channel ≤64, maximum channel 21). Both source images have separate byte hashes and meet at the exact original PDF page tile boundary. This establishes a *source ink observation in two image roots*, **not** a physical wall, opening jamb, W2 edge, W4 member, host, or continuous structural wall. The x=605.04 trace may include another line role; it must not be selected by nearest/proximity or a caller-provided label.

Current `pb_gptmax_raster_tile_seam_shadow.prove_tile_seam_source_pixels` and `prove_contiguous_source_ink_across_tile_seam` authenticate a **vertical x-coordinate** seam with a horizontal scan. Their original Lot16 test at page 3 x=714.36, y=426.5 concerns a different source role/coordinate. The horizontal y=210.48 b248 tile seam is not the same proof and must not be passed to the existing API by swapping coordinate meanings.

The repository's `tools/diag_gptmax_native_image_xref_scope.native_g17_w4_pixel_registration_shadow` already supports source-image ownership as a candidate-only registration. It explicitly leaves caller edge authority, complete W4 universe, source parent equivalence and host false. A new vertical scan of the horizontal seam must reuse, not replace, these safeguards.

## INFERENCE — falsifiable, not a promoted wall claim

A two-image XObject boundary inside b248's source opening extent is a plausible contributor to the 300-DPI G17 ↔ 144-DPI W4 source-parent mismatch. Dark native pixels on both image sides indicate an available **image-root continuity research path**, but may describe drawn linework, symbols or another physical object. Do **not** infer wall topology, structural material, W4 membership, signed area, opening type or frame from darkness or geometric continuity.

Other unhosted G17 cases must stay separately blocked. In particular, a68's interval crosses the different **vertical x=714.36** tile seam, which already has a separate existing source-pixel experiment; 81a/f819 shared-pier candidates require full third-owner exclusion. Do not copy b248 evidence to them.

## PROPOSED — review before ANY code

1. Extend the existing **default-off source-pixel** seam authority with an explicitly named horizontal seam mode/function, retaining existing vertical behavior byte-for-byte. Inputs must include original immutable PDF bytes, expected source SHA, one-based page, y seam, x scanline, bounded offsets and DPI. Every image root must have exactly one unmasked original XObject placement and an axis-aligned, positive, unmirrored transform.
2. Reprove both image roots, their distinct SHA-pinned pixel lattices, abutting placements and a bounded contiguous **vertical** dark-pixel scan with parity to the actual page render. Reject missing, duplicated, conflicting, foreign, white, masked, rotated, mirrored or sheared image placements and partial interrupted scans. Do not infer a wall from a dark stroke.
3. Reuse the producer's existing exact source-observation ancestry and original full W4 candidate universe. If any candidate is not independently authenticated by its actual W2→W4 source parent, return candidate-only evidence and the same first failing host gate. Only an independent producer-approved future structural-membership implementation may consume an explicit source proof.
4. Keep result flags **all false** for W4 structural wall, physical equivalence, host, whole-wall frame, width, height, opening count, FIRM metric, customer projection and benchmark. A candidate-only diagnostic must not enter ordinary production input composition without separate reviewed promotion.

## Required proof before authority review or merge

- Synthetic positive across two unique horizontal image roots, plus blank strip/false line, overlapping/duplicated placements, single xref reused, resized/mirrored/rotated transforms, foreign PDF SHA/page/viewport and incomplete source scope.
- Translation, source-pixel scaling (under trusted image transform), input-order / duplicated image-inventory and unrelated-content/viewport-expansion invariance; unsupported rotations must explicitly abstain, never silently align.
- True original b248 SHA-verified private-source replay, proving xref96/95 original pixel sample/edge geometry. No test may skip original-source validation and report it as passed.
- Original selected-root unchanged 21 physical, 15 authenticated local hosts, 9 local frames and **all eight complete signed customer-body fingerprints**, including physical/canonical IDs, reason and source lineage. These historical totals are retention assertions, never prediction inputs.
- Exact-head Python 3.13/3.14 CI + applicable private-original source job + independently documented W4/source-authority review + explicit owner merge approval. No direct production merge while any gate is missing.

## BENCHMARK facts NOT used in implementation

Frozen Full Plan V2 target records, expected quantity values, 120-denominator score or match identities are neither consulted nor changed. No precision/recall gain is claimed. Preserve 20,000 raster primitive cap, W2 2.5pt snap, original page-revision/snapshot/source identity, original eight signed Lot16 areas/customer rows, production publisher, private source PDFs and frozen evaluator.

**Review request:** Decide whether a source-only horizontal original raster tile-continuity diagnostic is warranted, which exact producer-owned source edge IDs must witness the proposed bridge, and whether this is a distinct scoped proposal rather than an overlapping G17 W4 PR. Stop here for architecture review under AGENTS.md.
