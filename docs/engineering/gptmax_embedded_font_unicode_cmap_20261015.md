# Embedded-font Unicode cmap vs original source glyph IDs

## Source and authority review

Read `AGENTS.md`, the AI engineering playbook, adopted wall/room source architecture and frozen V2 source separation, as well as `pb_pdf_text_integrity_authority._font_for_glyph_validation`, `_glyph_unicode_consistency_reasons`, `_text_clip_reasons`, merged #2724's `inspect_native_text_gates`, and original SHA-green artifact 11924296660.

Observed in the original Maryborough source: the FT3 definition is native block262 with 24 original source words, of which three have no strict raster literal proof. All 24 have a texttrace run. The original embedded `ISOCPEUR` TrueType xref293 supplies 16,316 bytes; `fitz.Font.has_glyph(codepoint,fallback=0)` is zero even on ASCII; original ToUnicode is xref294. Clip-state ownership is independently unresolved for all 24.

## Hypothesis and narrow test

An embedded TrueType program may have **its own Unicode cmap** mapping a source claimed codepoint to a glyph ID, separate from the PDF's `ToUnicode` stream. Read the original embedded bytes with the optional `fontTools` analyzer, enumerate all real Unicode cmap subtables and retain *every* candidate glyph ID, including conflicts or absence. Compare that set with the exact source texttrace glyph ID for each native word; do **not** pick the nearest matching map, font or inferred codepoint. Check the original PDF SHA and all candidate blocks/word origins. Retain font-program SHA, cmap platform/encoding IDs, glyph name, source trace glyph ID and no-fallback outcome.

This investigation runs only in `tools/diag_embedded_cmap_glyph_shadow.py` and its tests/workflow. `fontTools` is installed in the **dedicated CI investigation only**, not production requirements. Missing or malformed font programs, ambiguous map subtables, remapped PDF subset glyph numbers and absent Unicode cmap explicitly retain uncertainty. The source original actual PDF is asserted by hash in a test workflow; synthetic guards preserve alternate blocks, wrong SHA, wrong page, fallback behavior and no grants.

## Interpretation / expected abstention

Even a perfect match of Unicode cmap to glyph index is **font-metadata correspondence**, not proof the rendered glyph ink *visually reads* that Unicode. It does not resolve clip visibility or strict original 450/600 DPI raster disagreement. A negative does not disprove physical paint. This tool has no route to `trusted=True`, schedule material definition, source room, source finish occurrence, QuantityEvidence, commercial seal or frozen evaluator.

Benchmark name, target code, source page, PDF SHA, accepted quantities and expected values may appear **only in CI invocation/validation**, never in the algorithm. Original 20k cap, source pages, signed Lot16 eight and Maryborough three FIRM measured areas, frozen truth and customer outputs stay unchanged.
