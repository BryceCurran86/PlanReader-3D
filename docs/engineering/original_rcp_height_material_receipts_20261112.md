# Original PlanReader: source-trusted RCP height/material word receipts (GPT MAX, 12 Nov 2026)

## Purpose and source of the idea

This is a bounded port of the useful **same-native-text-block, adjacent-line RCP height/material detector** from the isolated draft Next engine (#4284, reviewed head `1b7e2c593f130ac0c29a97089ede4ed3cd76d921`) to **original PlanReader's** PDF text-integrity and cross-view ceiling-finish pipeline.

The new `pb_source_rcp_height_material_evidence.py` uses **only** a current `SourceVisibilityProducer` snapshot. The producer owns original PDF source bytes, SHA, clipping and overprint/glyph decisions, native block/line/word ordinals and observation IDs. The consumer re-resolves each word through existing `_trusted_words_by_page` and discards all words whose native integrity result was not CORROBORATED.

The opt-in method `CrossViewCeilingFinishProducer.source_rcp_height_material_evidence(revision_id=..., page_id=...)` is now an accessible seam in original PlanReader. The existing `publish()` and the original room/floor/ceiling/lining issuer, sealing and customer adapters are **unchanged**.

## What is authenticated, and what is not

A candidate requires:
- One original trusted numeric 1500..6000 mm word and one trusted RCP material code (GRID, IPF, FPB, etc.).
- The **same document revision, source partition, native page and text block**, adjacent source line ordinals, and the correct 90-degree rotated or unrotated callout geometry.
- Unique one-to-one material/height pairing. Competing nearby labels or heights cannot take ownership of a repeated word.
- Exact source observation IDs, source SHA, revision, snapshot, original block/line ordinals and word boxes. Noncanonical source/view selectors abstain or fail closed.

The records are explicitly `SOURCE_TEXT_CANDIDATE_ZONE_UNRESOLVED` and carry `commercial_projection_allowed=false`, `benchmark_credit=false`. They **do not** prove an actual ceiling exists, its geometry, a finished wall's height, which room owns an RCP callout, any ceiling area or any customer takeoff row.

A supported production follow-on must cross-bind a candidate to a source-authenticated physical ceiling zone, room identity, finish definition/occurrence, and specific surface in **existing** `pb_cross_view_ceiling_finish_authority.py` and `pb_cross_view_ceiling_quantity_authority.py`. That must independently prove geometry and area. A linked wall lining additionally needs a finished-face length and physical opening deductions. No Next raw `NativeWord` or PDF text can bypass the original producer.

## Original-source results

On the owner PC, the private Maryborough original SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, original p9/index8 RCP, gave **18** source-trusted material/height candidate pairs. Independent Next code also detected 18 same-bubble pairs at the exact reviewed PR head. A missing or corrupted original must never be labelled as a pass. Existing original Office GRID / Food Prep FPB customer ceiling areas remain exactly sealed as before; the 18 pairs add zero current customer m².

For 3Laurel, the Next engine reads Section A-A's 2700 mm FFL-to-FCL nominal height, and the owner explicitly approved this project's standard height unless overridden. The **original glyph-integrity pipeline p7 currently distrusts the exact 2,700/FFL/FCL words** (`text_glyph_mapping_unverified`), so this patch deliberately does not issue new source-FIRM 3Laurel wall/ceiling height from it.

## Acceptance and safety

Tests use negative same-block, wrong-line, wrong-partition, ambiguous double material/height, wrong-viewport and untrusted-word conditions, plus the actual private Maryborough original. Run existing cross-view/ceiling tests to ensure unchanged production behavior. The new method is **opt-in only**; no default customer flow changes, no benchmark denominator or truth changes, no original PDF in public Git, no signed Lot16 eight opening or Maryborough three floor records modified.

The most recent separately verified development 4-project original-app scoring packet is **33/120 (27.5%)**, but official publication is still withheld because source inventories are incomplete. This patch claims no new accuracy improvement until physical ceiling-zone/room authority is explicitly resolved and a new source-owned customer/score packet independently passes.
