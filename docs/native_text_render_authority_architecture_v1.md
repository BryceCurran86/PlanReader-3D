# Native PDF Text Render Authority — Architecture (v1)

**Status:** test-first architecture only. No production implementation, no opening-dimension publication, and no benchmark-score claim.

**Exact base:** post-#331 `main` `507c57db16be515e2432c695341bdea1e71b3fd7`.

**Dependency context:** PR #337 proves that raw `native_pdf_word` ownership is not enough for opening-dimension authority. This gate defines the narrower deterministic render-eligibility evidence that a future producer-bound dimension authority needs.

## 1. Decision

A raw extracted word is not automatically eligible figured-dimension evidence.

Native text must carry producer-owned render evidence showing, at minimum, that it was actually painted in an eligible text rendering mode and not deterministically hidden by a later opaque object. The evidence must remain separate from text-decoding correctness.

The adopted PyMuPDF 1.28.0 dependency exposes the required low-level source/render seams:

- `Page.get_texttrace()` — span/character geometry, text rendering type, color, opacity, optional-content layer and page-appearance `seqno`;
- `Page.get_bboxlog()` — ordered page-appearance objects (`fill-text`, `stroke-text`, `ignore-text`, paths, images, shades) where each list index corresponds to the same `seqno` space used by text trace and drawings;
- `Page.get_drawings()` — drawing geometry plus sequence and opacity/fill information for proving a later opaque occluder.

These are source/render observations, not heuristics based on nearest labels or benchmark values.

## 2. Authority states

A future typed producer record should use explicit states rather than a boolean. Names are illustrative; semantics are required.

- `PROVEN_RENDERED` — eligible text paint operation with positive opacity and no proven later full occluder; this is render eligibility only, not dimension authority.
- `PROVEN_NON_RENDERING` — PDF text rendering mode does not display the text (`ignore-text`, rendering type > 1 where applicable) or text opacity is zero.
- `PROVEN_OCCLUDED` — a later, independently observable, fully opaque object deterministically covers the complete relevant text/glyph bbox.
- `UNRESOLVED_PARTIAL_OCCLUSION` — later objects overlap only part of the text or their opacity/blend semantics do not permit deterministic full hiding.
- `UNRESOLVED_CONTRAST` — text is painted but visibility against its background cannot be proven from vector/source render records alone (for example white text on an otherwise blank/default-white page).
- `UNRESOLVED_DECODE` — extracted Unicode characters are not independently trustworthy for measurement semantics.

Only a state that is both render-eligible **and** decode-eligible may later support a figured dimension. Render evidence must never upgrade decode evidence.

## 3. Deterministic render-order rules

`seqno` is authoritative only for page appearance order within the exact producer-owned page/revision/source snapshot.

A later object may prove occlusion only when all required facts are producer-observed and deterministic:

1. its sequence number is greater than the text sequence number;
2. its visible geometry fully contains the relevant text/glyph bbox (not nearest/bbox overlap alone);
3. the covering operation is actually painted;
4. it is fully opaque under supported blend semantics; and
5. clipping / optional-content state needed for the conclusion is known.

A fill painted **before** text cannot occlude that later text.

Partial overlap must not silently become full occlusion. Unknown blend mode, transparency, clipping, optional-content state, or geometry must fail closed.

## 4. Non-rendering text

PDF text can be extractable while intentionally not displayed. Examples include OCR text layers and rendering mode 3 / `ignore-text`.

If `get_bboxlog()` classifies the text operation as `ignore-text`, or trace evidence proves an invisible rendering mode / zero opacity, the corresponding native text must be `PROVEN_NON_RENDERING` and ineligible for figured measurement authority.

This is a critical distinction from `SourceObservationRecord.raw_text`: the raw characters remain auditable but cannot be promoted into a measured quantity.

## 5. Contrast is a separate boundary

`get_texttrace()` exposes the text paint color and opacity, but source vectors alone do not always prove perceived contrast against the final background.

For example, fully opaque white text on an otherwise blank page is a real paint operation but is not visibly useful to a human reading the default-white rendering. A future authority must not label that case `PROVEN_RENDERED` **for measurement eligibility** merely because `type == fill` and `opacity == 1`.

Safe choices include:

- retain `UNRESOLVED_CONTRAST` unless a deterministic background/render proof exists; or
- add a separately reviewed raster/render-difference authority that proves glyph visibility without OCR or benchmark tuning.

Do not invent a contrast threshold in this producer gate.

## 6. Text decoding remains independently gated

Render eligibility does not prove that extracted characters are correct.

CMap/ToUnicode corruption, replacement characters, malformed mappings, and glyph-to-Unicode uncertainty remain separate blockers. A visibly painted glyph whose extracted string happens to read `900` must not become a FIRM 900 mm measurement unless decode authority is independently established.

PR #336's CMap/ToUnicode attack therefore remains required even after this render gate is implemented.

## 7. Producer/query boundary

The trusted source producer should publish immutable text-render evidence while it still owns the PDF page, source bytes, revision, snapshot and low-level trace/log observations.

Ordinary consumers must not be handed a `fitz.Page` and asked to reconstruct authority independently.

A future source observation or visibility result should be queryable by producer-owned identifiers/selectors and expose typed render evidence such as:

- source observation id;
- exact document/revision/source hash/snapshot/page;
- trace / appearance sequence identifiers;
- text/glyph bbox;
- render state;
- supporting and blocking reason codes;
- optional-content / clip provenance where available.

Consumer-created `is_visible=True`, `opacity=1`, `seqno`, color, or bbox fields are diagnostic claims only.

## 8. Type-3 and vector contamination

Text-render provenance and architectural vector provenance must remain separated. Type-3 glyph drawing operations must not be allowed to masquerade as architectural wall/opening geometry.

The stale PDF-integrity exploration in PR #295 identified this same hazard, but it is not current-main production authority. Any future implementation must be current-main, separately reviewed and must preserve G17 geometry firewalls.

## 9. Downstream firewall

Even `PROVEN_RENDERED` + decode-eligible text does not prove:

- figured-dimension line/witness binding;
- opening existence or identity;
- width or height;
- cross-view equivalence;
- host binding;
- universe completeness;
- physical void / deductions / net wall area;
- FIRM/commercial / JobHub publication.

Those remain separate gates.

## 10. Test-first acceptance

The companion red-team must establish on pinned PyMuPDF 1.28.0 that:

- visible text receives a normal paint entry and trace sequence;
- rendering-mode-3 / ignored text remains extractable but is identified as non-rendering;
- zero-opacity text is identified from trace opacity;
- later opaque full-cover drawing has a greater appearance sequence than the text;
- an earlier fill has a lower sequence and cannot be called an occluder;
- white-on-white painted text demonstrates that paint evidence alone is not contrast authority;
- a future producer-owned text-render authority fails closed on all unresolved states;
- no benchmark, gold, commercial or opening-dimension code changes are present.

## 11. Merge policy

**DRAFT / TEST-ONLY / DO NOT MERGE.** Production implementation belongs in a separate PR and must pass the attacks unchanged. This validator remains unmerged.
