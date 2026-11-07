# F07 paint ownership: bind a word's paint to its own native characters (architecture report, 2026-11-06)

Owner handover 2026-11-06: Claude's first item is the two unresolved original Maryborough page 11 F07 words. Claim: [#4135 comment 6683542230](https://github.com/BryceCurran86/PlanReader-3D/issues/4135#issuecomment-6683542230). Shadow only; no quantity, no customer row, no change to the provisional 9/120 count.

## Observed repository behavior

- `SourceMaterialSemanticProducer.for_physical_plan_view_shadow` segments the page with `segment_source_page_viewports(..., physical_plan_view_shadow=True)`. For a plan viewport it calls `_original_paint_owned_plan_word_ids`, then `_complete_source_plan_lines`.
- `_trusted_lines_for_viewport` / `_complete_source_plan_lines` declare the text scope incomplete (`text_crosses_viewport_boundary`) for any trusted word whose PyMuPDF **word cell** intersects the viewport without being fully inside it, unless the word is in `original_paint_owned_ids`.
- `_original_paint_owned_plan_word_ids` re-opens the SHA-verified original, resolves the word's CORROBORATED text-integrity receipt, and asks `_original_native_word_paint_within_parent` whether the word's **paint** (glyph rectangles, or the paint operation's box) lies inside the parent viewport.
- That function finds the word text inside the receipt's text-trace span(s) and accepts a glyph run only if every glyph rectangle satisfies `_bbox_fully_inside(rect, word.bbox, tolerance=1e-6)` and the paint-in-parent condition. It also rejects any foreign glyph overlapping the word cell, requires exactly one matching run, and requires a complementary fill/stroke pair when two sequence numbers are present.
- On the original p11 (SHA b1be5353, PyMuPDF 1.28.0, local geometry-only trace, no OCR): the single F07 plan viewport has exactly 3 boundary-crossing words. All three belong to one source line and ONE fill-text paint operation of 18 characters. Their word cells overhang the viewport's bottom edge by 0.68 pt (under the 2.5 pt snap tolerance); every glyph rectangle is 1.144 pt inside the viewport and the operation's paint box 0.792 pt inside. The 18 trace-glyph origins are exactly equal (difference 0.0, 18 of 18) to the 18 native character origins. The leftmost glyph rectangle of the three words starts at -0.00085 pt, -0.00183 pt and +0.00415 pt relative to the PyMuPDF word cell (float32 ulp at these coordinates is 6e-5 to 1.2e-4).

## Inference

- The two words the private run reported as "genuinely straddling" do not straddle in paint. They fail only the glyph-in-cell test, whose 1e-6 tolerance is below the noise between the text trace's glyph rectangles and PyMuPDF's word cell. The third word passes by +0.004 pt of luck.
- The glyph-in-cell test is a geometric proxy for a question the source answers exactly: *are these trace glyphs the word's own characters?* The trace and the native text page carry the same pen origins.
- This is not a viewport-boundary conflict, so no viewport, clip or snap change is justified, and none is proposed.

## Proposed change (opt-in plan-shadow path only)

1. A new helper `_native_word_chars_by_address(page)` builds, from `page.get_text("rawdict")`, for each native word address `(block, line, word)` the ordered `(character, origin)` pairs, and checks that their union box equals the native word row's box (same 1e-5 tolerance the function already uses). Anything irregular yields no entry, which abstains.
2. `_original_native_word_paint_within_parent` takes the new required keyword `native_chars_by_address` and replaces the rectangle-in-cell test with an exact binding: each matched trace glyph must have the same character and an origin equal at float32 precision to the corresponding native character of the word's own address. The parent-containment condition, the foreign-overprint rejection, single-match uniqueness and the fill/stroke pairing rule are unchanged.
3. `_original_paint_owned_plan_word_ids` passes the new mapping. Nothing else changes: not the receipt resolution, the viewport segmentation, the text-integrity authority, the snap tolerance, the 20,000 primitive cap, or any default-on behavior.

The binding is strictly stronger than the proxy it replaces: a same-text run elsewhere in the span, an overprinted glyph, or a moved glyph no longer matches, whatever the rectangles say.

## Not changed / not claimed

No FT2/FT3 occurrence, material scope, area, ceiling zone or customer row is produced or promised. Whether the F07 text scope completes after this change depends on gates not measured here (material definition completeness, other words in the scope); the private SHA-original replay owned by MAX decides it.

## Benchmark observations that must not influence implementation

The expected Maryborough items, the signed room areas, the provisional 9/120 count and the private run's counts are observations of a failure mode only. No threshold, tolerance or rule is derived from any expected value; the proposed rule is an exact identity test.

## MAX original validation correction

Protected private run 42227311488 stopped in the new original fixture before
testing paint ownership: `original_p11` constructed the default-off native-text
producer and found zero source-owned F07 views. Independent local reproduction
gave 61 passing tests and this one setup error. The actual material supplier
explicitly uses `source_native_finish_text_shadow=True`; its unchanged original
consumer gate on this same source head completes one CORROBORATED scope with
52 records and no unresolved words. Lot16's historical eight signed/customer
records remain byte-identical. These are different scopes and neither is a
floor-finish quantity.

The validation fix configures the original fixture with the same explicit
source-native text opt-in as the real supplier and adds an original test through
`SourceMaterialSemanticProducer.for_physical_plan_view_shadow` and its complete
occurrence scope. Production character/paint matching, default-off behavior,
viewport, source bytes, snap and cap are unchanged. Missing private source still
skips visibly; a provisioned but incomplete source still fails. Final fixed-head
dual Python and protected original replay remain required before release.

## Required tests (all synthetic except the last)

Positive: a word whose glyph rectangle exceeds its cell by float noise but whose origins match is owned. Look-alike negatives: the same text elsewhere in the span with different origins, a glyph run whose character or origin differs, a rectangle truly outside the parent, a paint box straddling with a glyph outside, a foreign overprint, two independent traces of the same word. Ambiguity: duplicate native words at one address, missing or irregular native characters. Invariance: translation of page content, input order of spans, extra unrelated text. No mutation, determinism, and the producer still publishes no quantity. Original-positive (skips without the private PDF): the three p11 words are all owned; the text scope for the F07 viewport has no `text_crosses_viewport_boundary`.
