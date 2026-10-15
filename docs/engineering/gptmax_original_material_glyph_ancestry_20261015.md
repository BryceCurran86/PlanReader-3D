# Original PDF glyph ancestry at incomplete material definitions

## Observed repository behavior

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, adopted W1–W10 architecture, source wall/room spec, and merged source-plan material ownership architecture. Followed `SourceMaterialSemanticProducer.publish` -> `_trusted_words_by_page` -> `_trusted_native_material_schedule_cluster_blocks` -> `_recover_native_material_block` -> `_recover_admissible_viewport_words` / `_recover_admissible_viewport_lines` -> `RasterTextCorroborationProducer.publish` -> `_producer_owned_ocr_target`. The independent physical-plan reader and existing commercial floor-finish consumer do not authorize a definition solely from plan occurrence words.

Original Maryborough page-11 replay on merged #2719 confirms a real FT3 material-definition block with 24 source words, 21 independently authenticated. The other three (dash and typographically curly-quoted words) remain non-authoritative because fixed original line OCR does not reproduce the exact original text. Five FT3 drawing mark words are independently source-positive, but their material definition and floor owner remain absent.

## Inference

Before changing OCR, inspect whether a failed literal can be uniquely joined to its original PDF character/glyph sequence, ink style, and native word origin. The source-native Unicode string or font glyph alone is NOT independent corroboration of its visible ink. The existing strict raster/word outcomes must remain intact. Distinguish original raster-literal discrepancy, PDF text-profile block-index disagreement, and missing glyph-origin ancestry instead of folding them into one fuzzy text match.

## Proposed change

Add a read-only original-byte diagnostic that enumerates **every** native candidate block containing an exact requested material code, retaining all competing blocks. For each native word, compare the same original source word to both PyMuPDF raw-character extraction profiles and to original `get_texttrace` unicode/glyph IDs and drawing sequence numbers. Match by exact word origin/geometry, not by arbitrary nearest word or source content substitution. Log original char bboxes/font identifiers and source address, as well as cases with zero/multiple matching runs. No OCR retry, Unicode quote folding, drop-dash rule or matching-result selection.

Synthetic checks enforce no mutation, source SHA/revision input guard, deterministic ordering and multiple candidate retention. An exact immutable Maryborough original-source action will write an audit artifact and print source-only summaries. This research never supplies `trusted=True`, a material-definition record, a material occurrence, metric authority or customer quantity.

## Benchmark observations excluded

The original project source path, expected PDF SHA, page 11, original FT3 label and historical 21/24 are **CI validation inputs only**, never detector defaults or threshold selectors. No frozen reference, evaluator, denominator, expected quantity, original PDF or current customer run is changed.

## Authority review and expected abstentions

An exact glyph text run is still source-native evidence, not independent ink authentication. Literal OCR mismatch, copied fonts, hidden draw sequences, ambiguous duplicate origins and unknown character/glyph mapping remain ABSTAIN. The genuine next acceptance gate would require an independent visual-paint proof of each disputed literal, followed by unique physical A140 room/floor finish ownership and GPT1 measurement/sealing. Until then, old definitions and all sealed outputs remain unchanged.
