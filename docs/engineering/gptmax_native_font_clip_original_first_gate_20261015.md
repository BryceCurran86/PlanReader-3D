# Original source font mapping and clipping first gate

## Observed repository behavior

Read AGENTS.md, docs/AI_ENGINEERING_PLAYBOOK.md, W1-W10 reference architecture,
source word-integrity producer, material definition and source plan ownership.
Traced `SourceMaterialSemanticProducer.publish` through
`_trusted_native_material_schedule_cluster_blocks`,
`_recover_native_material_block`, and `RasterTextCorroborationProducer.publish`
to `classify_native_word_integrity`, `_decode_status`,
`_font_binding`, `_glyph_unicode_consistency_reasons`,
`_font_for_glyph_validation`, `_text_clip_reasons`, and `_clip_model`.

Original Maryborough page 11 contains an exact source-native FT3 definition
block and 24 word/glyph origin runs. Three words were rejected, retaining
`text_glyph_mapping_unverified` and `text_clip_state_unresolved`; the existing
source-raster whole-line readings differ from literal punctuation. The
read-only PR #2720 inspects original glyph origins; it does not prove ink.

## Inference

The next missing proof may have two independent explanations:
(1) no-fallback embedded-font reconstruction or glyph-to-Unicode checking
cannot resolve custom ISOCPEUR character IDs; (2) the original extended page
clip stack does not establish source-local post-clip visibility.
Neither a valid ToUnicode CMap, original get_texttrace Unicode, PDF font name,
opaque paint, nor an OCR normalization supplies the missing proof.

## Proposed source-only check

Inspect exact original PDF bytes (hash required), every native text block
containing the requested exact source code, the full source word addresses,
the existing authoritative native-word decision, font xref/encoding/subtype,
embedded-font extraction state, no-fallback per-character glyph ID matches,
ToUnicode presence/validation and clip model state. Output every competing
candidate with explicit error/unavailable fields; never elect the nearest
block/word or change text/OCR/clip algorithms.

For each source word retain independently reported native trace vs font-glyph
result and the ordinary receipt reasons. Synthetic cases cover complete
candidate retention, SHA/revision/page negatives, no mutation, stable replay.
The original source CI writes a JSON receipt plus source SHA and verifies
all material/quantity/host promotion outputs stay FALSE.

## Expected abstentions and excluded observations

If the font cannot be reconstructed, a specific glyph is unavailable,
the PDF trace is ambiguous, or clip region assignment cannot be proved, retain
the existing ABSTAIN. Original project path, page, hash and source FT3 code
are CI input/checks only, never production parameters or scoring hints.
No benchmark gold, original source, global snap, PDF source snapshot,
canonical floor, customer quantity, or frozen scorer will change.

Original native font and clip metadata are diagnostic source inputs, NOT
independent post-clip ink proof. A later production change needs separate
generic adversarial and original-source evidence; never use quote folding,
dash deletion, alternate OCR engine or best-matching word.
