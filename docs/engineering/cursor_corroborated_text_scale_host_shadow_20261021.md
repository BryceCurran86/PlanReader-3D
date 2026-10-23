# Architecture: corroborated native words, unique graphic block-bar scale, unique primitive-owned hosts

## Observed repository behavior

Traced, not inferred from scores:

- `PdfTextIntegrityAuthority._glyph_unicode_consistency_reasons` abstains with `text_glyph_mapping_unverified` when the embedded font program cannot answer `has_glyph(unicode, fallback=0)`. Identity-H CID subsets take that path even when the texttrace glyph id equals the code point.
- `pb_physical_scale_authority._trusted_words` consumes only `TRUSTED_PDF_TEXT`. Empty trusted-word lists yield `physical_scale_bar_unavailable`.
- `pb_scale_block_bar_shadow.detect_block_scale_bars` already measures a block bar (arithmetic numerals plus block edges). It grants no authority (`scale_authority_granted=False`) and is not called by the live scale producer.
- `OpeningLabelDimensionAuthority._trusted_text_lines` likewise requires integrity `CORROBORATED`. Missing trusted text is `opening_label_dimension_text_unavailable`.
- `OpeningHostBindingProducer.publish` requires a complete authenticated host universe or a local boundary-clean fallback. `_resolve_two_face_lineage_host_from_records` then CONFLICTS with `opening_two_face_wall_lineage_ambiguous` if any owner wall sits in page-wide `equivalence.ambiguous_wall_ids`, even when the four interrupted primitives map to one local pair.
- W7 `detect_opening_host_candidates` always emits `ambiguous_host` and is not host authority.
- Existing shadows `pb_raster_text_corroboration_authority` and `pb_source_amortized_glyph_text_corroboration_shadow` already corroborate subset-font words as `CANDIDATE` with `takeoff_eligible=False`. They do not grant `TRUSTED_PDF_TEXT` and are not consumed by scale, labels, or hosts.

Receipts (post-producer, not inputs): a development floor-plan page with Identity-H subsets has zero trusted words; the block-bar detector reports a unique 0…N m run when numerals are supplied; host claims abstain at universe-completeness / two-face ambiguity. Those receipts must not set thresholds.

## Inference

Subset-font numerals can become usable for *shadow* consumers without weakening the live integrity boundary, if the only admitted words are raster-corroborated or amortized-glyph `CANDIDATE` records. A unique block bar from those words is graphic-scale *evidence*, not FIRM measurement: title-block ratio text still cannot raise firm authority. Unique four-primitive wall ownership is stronger than page-wide unresolved equivalence for a shadow host band; two equally owning groups must still abstain.

## Proposed change

New shadow compiler `pb_source_corroborated_text_scale_host_shadow.py`:

1. Admit only corroborated native words (direct OCR, amortized glyph, or already-trusted integrity). Uncorroborated words stay invisible.
2. Run `detect_block_scale_bars` on those words. Zero bars abstain; two disagreeing ppm values conflict and retain both; one unique bar (or several that agree) is `CANDIDATE` scale. Never call `resolve_page_scale_calibration`. Never grant FIRM.
3. Parse opening labels with existing `parse_opening_label_dimensions`. Bind a label only when exactly one parseable corroborated string intersects the opening box. Ties conflict. Axis order stays unresolved.
4. Bind a host band only when each of four unique face primitives has owners and the owners collapse to exactly two walls (or one wall owning all four). Page-wide `ambiguous_wall_ids` is not a veto. Two owner sets of equal size conflict. W7 is not used.

`status=CANDIDATE`, `commercial_projection_allowed=False`, `takeoff_eligible=False`, `shadow_only=True`. Live extractor, W10, JobHub, and `ci.yml` stay untouched.

## Authority boundaries crossed

None that may become firm. Existing seams `resolve_page_scale_calibration` / `measurement_authority_for_page_scale` are not called. Hosted-opening geometry remains unwired. `#273` ranking is not consumed.

## Expected abstentions

- Uncorroborated Identity-H words
- Numerals without block edges; title-block `1:100` alone
- Two parseable labels intersecting one opening
- A face primitive with zero owners, or two distinct owner pairs
- Empty or non-four face-primitive tuples

## Files that stay untouched

`pb_pdf_text_integrity_authority.py`, `pb_physical_scale_authority.py`, `pb_opening_host_binding_authority.py`, `pb_planreader_pdf_extractor.py`, W10 defaults, `benchmarks/frozen_holdout/full_plan_v2/**`, `documents/sources/*.pdf`, `.github/workflows/ci.yml`.

## Benchmark observations that must not influence implementation

Frozen item counts, expected opening sizes, project names, file names, and development scores are not inputs, thresholds, or oracles.
