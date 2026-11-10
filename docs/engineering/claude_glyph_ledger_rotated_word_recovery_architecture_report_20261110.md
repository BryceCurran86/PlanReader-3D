# Architecture report: glyph-ledger recovery of rotated (vertical) words

Status: report (reviewed by MAX in #4135 comment 6755168519, which authorized implementation) plus the implementation and measured results below. Date 2026-11-10. Lane: Claude, 3Laurel source-to-customer. Opt-in text-trust path only.

## Compliance proof (AGENTS.md first deliverable)

- **Read:** `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` (sections 5, 11, 12, 13; it has no glyph or text-integrity guidance); `pb_font_glyph_mapping_corroboration_shadow.py` (`word_glyphs`); `pb_source_glyph_ledger_text_trust.py` (`decide_glyph_text_trust`, `upgraded_text_integrity_receipt`); `pb_source_visibility_authority.py` (`upgrade_glyph_only_text`); `pb_pdf_text_integrity_authority.py` (`_texttrace_spans`); `pb_elevation_source_owned_witness_adapter.plan_label_width`.
- **Traced quantity:** the printed door width figure, from the label authority to the measurement gate.
- **Authority boundary crossed by the proposal:** one only, the opt-in glyph ledger turning a glyph-only-untrusted word into a trusted receipt. Default stays off (`source_glyph_ledger_text_trust=False` everywhere it is exposed).
- **Stays untouched:** everything in playbook section 11, the frozen 120, the Lot16 signed eight and Maryborough signed three, identity maps, the 2.5 pt snap, the 20k cap, `PdfTextIntegrityAuthority` acceptance rules, `pb_opening_label_dimension_authority.py`, `pb_external_door_height_estimate_policy`, and every default code path.

## Observed repository behavior

1. The Front entry (`22e7e155`) measurement stops at `text_integrity_not_corroborated` even with the opt-in. The label authority uses exactly one text observation for its width: the printed `1,200` (`6788f937`). Text integrity gives it `ABSTAINED`, `text_glyph_mapping_unverified`; the Lhs door's `870` (`af71777e`) is corroborated (`amortized_glyph_verified`).
2. Capturing the ledger's own decision (no repo change) shows `1,200` is `ABSTAINED` with `glyphs_not_recovered`: `word_glyphs` returned `None`, so the word cast no vote and could not be matched against verified glyphs.
3. Cause, reproduced with plain PyMuPDF and the repo's own `word_glyphs`: the word is printed rotated 90 degrees (trace span direction (0, -1), reads bottom to top). `word_glyphs` selects the characters whose centre is in the word box, then orders them by x-centre only. All five characters share x = 943.065, so the order is float noise (`,0120`, not `1,200`) and the spelling check fails. Ordered by y descending it spells `1,200`. The Lhs `870` is horizontal and recovers.
4. Same result ingesting page 3 alone (425 s and 650 s in two runs) and pages 3 to 5 (1,138 s): more pages do not help.
5. Producer counts on page 3 (opt-in): 1,140 glyph-only candidates, 1,063 recovered, 77 not recovered.

**Scope (page 3, PyMuPDF words with the repo's `word_glyphs`; approximates, not equal to, the producer's candidates):** 1,215 words; 262 read bottom to top; 72 of those fail now; 10 horizontal words fail for another reason (not examined). Figure-like words (3 to 4 digits or n,nnn): 228, of which **26 fail, all bottom-to-top**. Ordering along the span's own direction recovers 25 of those 26 and 51 of the 72. They include door width labels and running dimension strings along vertical walls (the owner reports all door widths are printed rotated like a closed door, for example the garage and the room opposite it; I have mapped only the Front entry to an opening, so I cannot yet confirm the others one by one). One figure word still fails after the change (cause not examined). Pages 4 and 5: 18 and 19 bottom-to-top words fail now, but direction-aware ordering recovers 0 and 1 of them, so their cause is different (not examined).

## Inference

- This is systematic for any bottom-to-top text, not a one-off, and it caps the text gate for every vertical-wall dimension and door width under the opt-in.
- Recovering a word is necessary, not sufficient: it is trusted only if every glyph is verified by at least two raster-corroborated words and none is contradicted. Whether the `1`, `,`, `2` and `0` of that font program meet that bar is **not measured**.

## Proposed change (not made; separate small PR after review)

- In `word_glyphs`, order the selected characters by projection on the trace span's own direction vector (tie-stable), keep the centre-in-box selection and the exact-spelling requirement, and return `None` when the selected characters come from spans with different directions. Alternative considered and not preferred: trusting the trace's character sequence, because the existing selection already works in page coordinates.
- No change to thresholds (`CENTRE_TOLERANCE_PT`, `min_words`), to the receipt builder, to the acceptance rule, or to any default.
- Tests first: synthetic words at 0, 90, 180 and 270 degrees; look-alike negatives (reversed spelling, mixed directions, a ligature, a split word); whole-page rotation and translation metamorphic (same glyph pairs recovered); input-order and span-splitting invariance; unrelated-content invariance; deterministic replay and stable ids; no input mutation; decisions on horizontal-only fixtures byte-identical to today; default-off proof that no receipt changes.
- Required review: MAX. The change alters which words become trusted whenever the opt-in is on (live integration and the handoff runner expose it), so the protected exact-head replay and the Lot16-eight / Maryborough-three retention must be run for the PR head, and any signed run that used the opt-in must be shown unchanged.

## Benchmark observations that must not influence implementation

The expected door widths, the 3Laurel opening list, how many words recover, and whether `1,200` ends up corroborated. No threshold may be tuned to make a particular word pass.

## Not proven

That the recovered words verify; that the other door widths (garage and the room opposite it) are in the 26 figure words; the cause of the remaining failures on pages 4 and 5 and of the 10 horizontal failures on page 3.

## Implementation (this PR) and measured results

**Change.** `pb_font_glyph_mapping_corroboration_shadow.word_glyphs` only. It orders the selected characters by projection on the trace span's own unit direction instead of by x-centre, and it keeps the centre-in-box selection, the exact-spelling requirement, the 0.6 pt centre tolerance and the `WordGlyphs` contract. It returns `None` (the word casts no vote) when the characters come from spans with different directions, when the characters come from spans in different fonts, when a span direction is invalid (non-finite, mis-shaped, not a unit vector), or when two characters have no defined order. A span without a `dir` is read as horizontal, exactly as before. No other order is ever tried. The ledger (`decide_glyph_text_trust`), `upgrade_glyph_only_text`, the receipt builder, `min_words >= 2`, the contradiction veto, the raster corroboration and every default-off flag are untouched.

**Tests (47 new, the existing glyph-ledger tests unchanged and passing; 18 single-line mutations of `word_glyphs` all caught, two survivors on the unit-vector tolerance closed with tests).** 0, 90, 180, 270 and 45 degrees; translation, uniform scale, whole-page rotation; shuffled characters, split and reordered spans; unrelated spans; determinism and no mutation; wrong and reversed claimed text; mixed direction; mixed font; non-finite, zero, non-unit, mis-shaped and non-sequence directions; two characters at one position; stray text of another direction in the box; a missing `dir` keeps the horizontal reading (a vertical word without one still abstains); 300 random horizontal words equal to a copy of the previous implementation (the regression oracle); real PDF text in all four rotations through PyMuPDF; and the existing ledger decision with rotated words (two corroborated words verify a glyph, one does not, a contradicting rotated word still vetoes).

**Original 3Laurel, word_glyphs before and after (PyMuPDF words and trace spans, pages 3, 4, 5).** Page 3: 1,215 words, 51 newly recovered, 31 recovered by neither, **0 regressions**; figure-like words: 25 newly recovered, 1 still not. Page 4: no change. Page 5: 1 newly recovered. No word that was recovered before is lost, including the mixed-font tightening.

**Original 3Laurel, the real ledger (explicit glyph-ledger opt-in, page 3).** Glyph-only candidates 1,140; recovered **1,114 (was 1,063)**; raster attempts 93 (was 92); directly corroborated 76; verified glyphs 115; contradicted glyphs 0. The Front entry's printed width word `1,200` (`6788f937`) was `ABSTAINED` `glyphs_not_recovered`; it is now **`CORROBORATED` by `amortized_glyph_verified`**: all five glyph occurrences are verified (corroborated words supporting each distinct glyph: 4, 3, 4, 8, 8; none contradicts). Through the text-integrity authority the label authority's word for the Front entry is now `corroborated`, `trusted`, no reason codes, decode `amortized_glyph_verified`; the Lhs `870` is unchanged.

**What this does and does not prove.** It authenticates the printed text of the Front entry's width word under the explicit opt-in. It does not publish a width, does not authenticate door kind, host or frame, and is not a customer value. The first remaining gate for the Front entry is the host (the east face is continuous across the span and the opening's reveal stubs are unowned); that veto is unchanged. One figure-like word on page 3 remains unrecovered by direction-aware ordering (cause not examined).

**For MAX (protected verification).** Frozen head and exact commands are in the PR description once pushed. The change is reachable only when `source_glyph_ledger_text_trust=True` (live integration and the handoff runner expose it, default False); any signed run that used the opt-in must be shown unchanged, and the Lot16-eight / Maryborough-three retention must be run for the PR head.

