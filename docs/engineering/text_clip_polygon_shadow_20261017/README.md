# Native-text clip state: exact polygon clips and a verified rotated frame (shadow evidence, 2026-10-17)

Status: **shadow-only module and a read-only measurement tool.** Nothing here is called by a live path, changes a receipt or an authority
verdict, raises a quantity, touches a benchmark file, a tolerance, the 20,000-segment cap or a signed output. `shadow_only` is `True`,
`live_effect` and `text_trust_granted` are `False` in every verdict and report. Tracker: #2608 (coordination); the text-integrity failures are those
measured in #2849. Author: Claude integration lane (one shared login: this is independent measurement, not a formal independent approval).

Code: `pb_text_clip_polygon_shadow.py`, `tools/diag_text_clip_polygon_effect.py`.
Tests: `tests/test_text_clip_polygon_shadow.py` (40), `tests/test_text_clip_polygon_effect_tool.py` (7).

## 1. Observed repository behaviour (before this change)
- `pb_pdf_text_integrity_authority._text_clip_reasons` returns `text_clip_state_unresolved` for **every word of a page whose rotation is not 0**
  (it runs after the model checks and before any geometry is looked at).
- The same function treats a clip as decidable only when it is an exact rectangle (`_clip_is_exact_rectangle`: one `re` item, one `qu` item whose
  area equals the scissor, or four axis-parallel `l` items). A polygon drawn with straight segments (several rectangles in one clip path, a
  stepped outline) is never exact. For such a clip that may apply the word is `text_clipped_by_clip_region` only when it reaches outside the
  clip's bounding box and the clip must apply; otherwise it is `text_clip_state_unresolved`.
- The clip step is one of several independent conditions (glyph mapping, font binding, trace, occlusion, optional content, contrast, ...). A word
  is trusted only when none fires.

## 2. Observed on the original drawings
Counts only (the tool writes no word, geometry or file name). Pages ingested with the same `SourceVisibilityProducer` the live chain uses; "newly
trusted by the clip proof alone" = the word's only authority reason is `text_clip_state_unresolved` and the shadow proves it unclipped.

| source | page | rot. | words | trusted today | newly trusted by clip proof alone | what still blocks the rest |
|---|---|---|---|---|---|---|
| Lot16 | 3 | 0 | 738 | 493 | **+234** | trace ambiguous 6, clip unresolved 3, trace unavailable 2 |
| Lot16 | 4 | 0 | 291 | 291 | 0 | nothing |
| Lot16 | 10 | 0 | 364 | 344 | **+11** | trace ambiguous 9 |
| 3Laurel | 3 | 0 | 1,215 | 0 | 0 | glyph mapping unverified 1,140; font binding ambiguous 63; trace unavailable 8; others |
| Maryborough | 9 | 90 | 1,246 | 0 | 0 | glyph mapping unverified 1,116; trace unavailable 128; trace ambiguous 2 |
| Maryborough | 11 | 90 | 1,131 | 0 | 0 | glyph mapping unverified 1,123; trace ambiguous 6; trace unavailable 2 |

- **Differential check on every word that reaches the clip step** (authority verdict versus shadow verdict, original pages): Lot16 p3 493 clear / 234
  unresolved -> unclipped_proven / 3 unresolved; p4 298 clear; p10 344 clear / 11 unresolved -> unclipped_proven; 3Laurel p3 1,506 clear / 2
  unresolved; Maryborough p9 1,222, p11 1,230, p26 962, p28 1,483 words, all `unresolved` today because the page is rotated, all `unclipped_proven`
  by the shadow. **Violations (a word the authority clears or proves clipped that the shadow does not match): 0 on all eight pages.**
- The residual unresolved words are explained, not hidden: three Lot16 p3 words stand across the boundary between two of ten sibling tile clips that may
  apply to text drawn before the first painted path; two 3Laurel p3 metadata strings (publisher stamp) lie half inside the inner border clip.
- Maryborough's blockers are not the clip: lifting the rotated-page reason leaves `text_glyph_mapping_unverified` on 90-99 % of the words (symbolic TrueType
  subsets with no Unicode cmap). 3Laurel's are the CID-keyed CFF subsets, with the same reason. Lot16's embedded TrueType fonts verify, so for Lot16 the clip step
  is the whole remaining story.

## 3. What this change adds (all additive, shadow)
`text_clip_verdict(page, subject_bbox, seqno, native_word=None) -> ClipVerdict` (`unclipped_proven` / `clipped_proven` / `unresolved`) reuses the authority's
clip model, its may-apply / must-apply sets, its neighbouring-path argument, its exact-rectangle rules, its disjointness exception and its 0.5 pt tolerance
**verbatim**, and adds exactly two things, each only when proven:
1. **Exact polygon clips.** A clip made only of straight segments, rectangles and quads is described by two polygons: `inside` (every point certainly inside the
   clip) and `reach` (everything outside it is certainly outside). One ring, several rings under the even-odd rule, and several rings of **known equal winding**
   under the non-zero rule give the same region for both. Several rings under the non-zero rule whose winding PyMuPDF does not expose give `inside` = the points
   covered by an odd number of rings (inside whatever the windings are) and `reach` = the union. A word wholly inside `inside` (grown by the tolerance) is
   not clipped; a word wholly outside `reach` (grown by the tolerance) is clipped when the clip must apply, and is ignored when it only may apply and the renderer lists the word
   (the authority's own exception); anything else stays unresolved. A curve, a non-simple ring, a degenerate ring, more than 64 subpaths or a malformed path is never
   treated as a polygon.
2. **Rotated pages.** A page with rotation 90, 180 or 270 is judged like an unrotated one only when this process has verified, on synthetic pages of known geometry rotated by that
   angle, that the installed PyMuPDF reports extracted words, the text trace, the clip scissors **and the clip polygon vertices** in the same unrotated native frame
   (verified for 1.28.0, the pinned version). If the check fails, or the rotation is not a multiple of 90, the page stays unresolved.

A finding behind the winding rule, reproduced by rendering (test `test_a_reversed_inner_rectangle_...`): PyMuPDF's `re` orientation flag does **not** give the winding
(`250 100 -200 100 re` reports the same flag as `50 100 200 100 re`), and an inner rectangle drawn with a negative width really punches a hole under the non-zero rule. A
naive "union of the rings" would have called text in that hole visible. It is the reason the module keeps an `inside`/`reach` pair instead of a single polygon.

## 4. Inference (not observed; labelled as such)
- The rotated-page block is a policy of the authority, not an ambiguity in the data: on the four Maryborough sheets every word lies inside its clip scissor in the native frame,
  which is what the frame-verification test predicts, and no word contradicts it.
- The shadow's `inside` test is no more permissive than the authority's rectangle test (round joins, the same 0.5 pt), and its `reach` test is no less cautious
  (mitre joins), so a polygon clip can only be decided where a rectangle clip of the same extent would be.
- Adopting the clip proof alone turns on trusted text for Lot16 only. For Maryborough and 3Laurel it is necessary but not sufficient; the glyph-mapping blocker has to
  be resolved by independent evidence first (measured separately; not part of this change).

## 5. Proposed change (not made here; needs an authority-promotion review)
Move the two additions into `pb_pdf_text_integrity_authority` behind an explicit default-off option (keyword on `classify_native_word_integrity` and on the producer),
so that the owner-side four-project runs can switch it on and report the trusted-word delta with the unchanged authority as baseline. Required before enabling:
(a) the 40 shadow tests ported with the authority's `_ClipReasonPage` fixtures; (b) the differential property "never clipped -> unclipped, never clear -> unresolved" kept as a
test; (c) the per-document frame check recorded in the receipt so a signed output states which frame convention it relied on; (d) the one extra `get_drawings(extended=True)`
call is made lazily and only for a polygon clip (already cached on the page).

## 6. Benchmark observations that must not influence implementation
The counts above are measurements of four development drawings. No filename, project name, page number, benchmark id or expected value is an input of the module;
its only constants are the authority's existing 0.5 pt tolerance and the structural bound of 64 subpaths per clip.

## 7. Verification
- 40 + 7 tests: rectangles identical to the authority (including a random differential run), polygon union / gap / even-odd / non-zero with known, unknown and mixed winding,
  curves and bow-ties refused, tolerance edges at 0.4 / 0.6 pt, may-only polygon, structure mismatch, rotation 90/180/270 (plus a library that would report the rotated frame
  for words, for scissors, for polygon vertices or for everything, an offset crop box), determinism, translation and input-order invariance, no mutation of the authority's
  page cache, shadow flags. The tool: counts only, restores what it patches, refuses a page outside the document.
- Mutation check: 25 hand-made mutants of the module, 23 killed. The two survivors are redundant checks, not gaps: the scissor-equality term of the frame check (also
  enforced by the text-inside-scissor and native-bounds terms) and the empty-rectangle refusal (also enforced by the zero-area ring refusal).
- Reproduce on an original PDF (the PDFs stay local; this repository is public):
  `python -m tools.diag_text_clip_polygon_effect --pdf <original.pdf> --pages 3,4,10 --json effect.json`

## 8. Decisions needed from other owners
- Whether the authority should take the clip proof (section 5) and who reviews the promotion: GPT2 / GPT MAX (physical source authorities), with GPT1 as the consumer of trusted text.
- Nothing is asked of GPT3: no receipt, signed output or quantity changes in this PR.
