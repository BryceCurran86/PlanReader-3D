# Text-integrity coverage on the four original projects (2026-10-16): the producer trusts almost none of the text outside Lot16

Status: **measurement and a read-only diagnostic.** No authority, threshold, benchmark file, signed output or live path is changed.
Tool: `tools/diag_text_integrity_coverage.py` (tests: `tests/test_diag_text_integrity_coverage.py`). Author: Claude integration lane.

## Why this matters
Every label, dimension, scale numeral, schedule row, tag and room name enters the quantity chains through `PdfTextIntegrityAuthority`
(`TRUSTED_PDF_TEXT`). A word it abstains on is invisible to those chains: more than twenty authority modules call `text_integrity_authority()`, among them the physical scale producer, the opening
label dimension and semantic authorities, the schedule instance-binding and row-height authorities, the vertical-placement and joinery-height authorities, and the wall-finish and ceiling-finish binders. The tool ingests pages with the same `SourceVisibilityProducer` the live chain uses and reports, per page, how
many words are trusted and why the rest are not.

## Observed (original PDFs, `main` `47c8031a`, Windows, 2026-10-16)
| project / page | native words | trusted (CORROBORATED) | main reasons (counted per word) |
|---|---:|---:|---|
| 3Laurel p2 (site plan) | 765 | **0** | `text_glyph_mapping_unverified` 683, `text_font_binding_ambiguous` 63 |
| 3Laurel p3 (floor plan) | 1,215 | **0** | `text_glyph_mapping_unverified` 1,144, `text_font_binding_ambiguous` 63, `text_unicode_untrusted` 11 |
| 3Laurel p13 / p15 (laundry, ensuite) | 435 / 518 | **0 / 0** | same |
| Maryborough p7 (floor plan) | 1,545 | **0** | `text_glyph_mapping_unverified` 1,523 **and** `text_clip_state_unresolved` 1,523 |
| Maryborough p9 / p11 / p26 / p28 | 1,246 / 1,131 / 899 / 1,391 | **0 / 0 / 0 / 0** | same pair |
| Q5446 p1 (outlined lettering) | 4 | **0** | `text_glyph_mapping_unverified`, `text_clip_state_unresolved` |
| Lot16 p3 (floor plan) | 738 | **493 (67 %)** | clip state unresolved on 237 |
| Lot16 p4 / p10 | 291 / 364 | **291 (100 %) / 344 (94 %)** | |
Lot16 is the only project whose text the producer trusts, which is the project with signed quantities (8/27); the others have no trusted label, scale numeral, tag or schedule word at all (0/24 and 0/63 on the frozen development scoreboard).

## Cause, measured
The authority verifies the glyph mapping independently of ToUnicode: `get_texttrace()` gives the rendered glyph id per character and the font program must return the same glyph for the decoded Unicode
(`_glyph_unicode_consistency_reasons`). It needs the embedded font program to offer a Unicode lookup. The tool probes this per font (`fitz.Font.has_glyph` over 60 digits and letters):
- **Lot16 p3:** embedded programs of 340-377 KB with a Unicode lookup (59/60, 58/60, 41/60): verifiable.
- **3Laurel p3:** six Type0 `Identity-H` Arial/Calibri **subsets** of 4-31 KB, ToUnicode present, **0/60** Unicode lookup in every font program; the traced glyph id equals the code point (`G` -> 71), consistent but not verifiable from the font alone.
- **Maryborough p7/p11:** TrueType subsets (`ISOCPEUR`, `MicrosoftSansSerif`, `Arial`, 15-62 KB), **0/60**; and every word is additionally inside an unresolved clip state.
So the fail-closed rule behaves as designed and removes the text of every CAD/Word export that embeds subsets without a Unicode table.

## What can recover the text today, measured
`pb_raster_text_corroboration_authority` (shadow) reads exactly these words twice at two scales with RapidOCR and corroborates when both readings equal the native claim. On the first 150 words of 3Laurel p3
(`scripts/raster_text_corroboration_page_shadow.py`, RapidOCR in a scratch venv): **106 corroborated (71 %)**, 19 competing readings, 14 no reading, 3 native-claim mismatches, 3 view disagreements; 402 s for 150 words (about 2.7 s per word), i.e. roughly an hour for the page.
`rapidocr` and `onnxruntime` are deliberately not in `requirements.txt` (deployment-memory decision), and the modules that import the corroboration authority are the newer ones (room label, plan view, material semantics, callout, cross-view room area, raster plan dimension, opening detail definition, elevation frame area), not the scale producer or the opening label dimension authority.

## Consequences for the other lanes
- A block-style scale bar (shadow PR for `pb_scale_block_bar_shadow.py`) is detected on 3Laurel p3 (0 ... 10 m, 28.3462 pt per metre, 1:100 within 8e-6), but the scale producer would still see **zero trusted numerals**, so the bar cannot be consumed until the numerals are trusted or corroborated.
- The 139 opening candidates on 3Laurel p3 all abstain at `opening_label_dimension_text_unavailable` for the same reason.
- Printed legends and area tables (for example the area summary on the 3Laurel floor plan) are not available to any authority that requires trusted text either.

## Decisions this needs (not taken here)
1. Owner: whether the four-job launcher and CI jobs that feed these chains install `rapidocr`/`onnxruntime` (as the diagnostic workflows already do), and the time budget (about 2.7 s per word on this machine).
2. Authority owners: whether the opening label/dimension authority and the scale producer should accept raster-corroborated words (a separate authority-promotion review), and whether a font-program-independent glyph verification (for example against a trusted reference outline set) is acceptable for subset fonts without a Unicode table.
3. Clip state: why every Maryborough word is `text_clip_state_unresolved` (the CAD export wraps text in clip paths); the corroboration authority can discharge it by rendered-pixel proof.

## Reproduce
`python -m tools.diag_text_integrity_coverage --pdf <original pdf> --pages 3,7 --json out.json` (read-only; prints one line per page and writes the per-page status, reason counts and font table).
