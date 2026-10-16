# Architecture report: outlined-text ink above the 20,000 wall-topology cap (Q5446)

**Status.** Report only, for review. No code, cap, benchmark file, signed output or workflow is changed by this
document. Per `AGENTS.md`, work stops here until a reviewer accepts or redirects it. Written by the Claude
integration lane, 2026-10-16, after the first complete owner-machine run (receipts in
`docs/engineering/four_job_runs/20261016_47c8031a/`, #2846).

## Compliance (what was read and traced)
Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (wall chain), `pb_physical_wall_candidate_authority.py`
(`_assemble_scope_result`, `_filter_repeated_non_physical_drafting_primitives`, `MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS`),
`pb_vector_geometry_v130.extract_native_page`, `pb_annotation_cycle_shadow.py`,
`pb_raster_text_corroboration_authority.py`, `pb_pdf_text_integrity_authority.py`.
Authority boundaries crossed by the proposed change: none in shadow (it only reads native path geometry and
publishes a typed diagnostic). A later promotion would cross the W2/W3/W4 input boundary and therefore needs its
own authority-promotion review.
Stays untouched: the 20,000 cap, W2/W3/W4 inputs, scale and viewport authorities, quantity builders, signed
outputs, frozen V2 files, source PDFs.

## 1. Observed repository behaviour
- Wall topology for a page is built in `_assemble_scope_result`. After `_filter_repeated_non_physical_drafting_primitives`,
  `len(topology_segments) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS` (20,000) returns a blocked scope with
  `physical_wall_candidate_scope_complexity_exceeded`. The whole project handoff then abstains.
- The filter only removes one-segment source paths (`kind == line`, path size 1) that belong to a repeated stroke family. A
  path made of several segments (a flattened curve or a glyph outline) is never removed by it.
- `pb_annotation_cycle_shadow` quarantines an exact-endpoint block only when its cycle walks around one **native
  source word** (at least 8 edges). The live wall authority does not call it.
- The text-integrity and raster-text corroboration authorities work from native text and its glyph mapping.
- Q5446 standard plans: 40 native words in the whole 10-page PDF (a repeated envelope line); page text is outlines.
- Measured with the production extraction and motif filter (receipt README): segments after the filter per page
  41,932 / 31,514 / 24,846 / 34,657 / 23,067 / 21,840 / 26,996 / 26,634 / 20,129 / 8,538 for p1-p10; 9 of 10 pages exceed the cap.
- Path shape on p1 (47,184 segments, 14,664 source paths): 97 % of segments sit in paths whose own extent is at most
  12 pt (57 % open paths, 21 % closed and filled, 17 % closed unfilled); 84 % of segments are shorter than 3 pt
  (median 0.99 pt); about 3 % are in paths larger than 12 pt. p10 (under the cap) has the same mix at lower volume.

## 2. Inference (not proven)
- The over-cap mass is lettering and small symbols drawn as outlines, not wall linework. This is inferred from path
  size and segment length; it is not yet a source-positive classification.
- A classifier cannot be keyed on native words here (there are none), so the existing annotation-cycle proof does
  not apply as written. It is the nearest existing seam and its structure (conjunction of proofs, retain on doubt) is the right shape.
- Removing ids from the live wall input rekeys W2 split edges, W3 junctions, W4 walls and sealed room quantities
  (the annotation-cycle module already records this), so any use beyond diagnostics is a promotion decision.

## 3. Proposed change (shadow only, default off)
A new typed diagnostic in the style of `pb_annotation_cycle_shadow`: `classify_outlined_text_ink(segments, page extent)`
returning, per source path, `GLYPH_INK_CANDIDATE`, `NOT_GLYPH_INK`, or `UNPROVEN` with reason codes, and the exact
withheld-id set that the live path does not consume. A path is a candidate only on a conjunction of source-owned proofs,
none sufficient alone: (a) one source path; (b) path-local extent small relative to the page's own measured line
height, where that height is derived from the page's own repeated path-extent distribution (no fixed constant and no
project constant); (c) membership in a baseline-aligned run of at least N similar paths with regular spacing; (d) no
contact with a long stroke or another candidate class (a short wall return or a door-swing tick must not be absorbed);
(e) retained plausible alternatives: if a path could be a wall piece or a glyph, it stays `UNPROVEN` and counted.
Outputs: typed reason codes, deterministic ids, no mutation, and a count `would_remain_after_withholding` per page so
reviewers can see, without any live effect, whether a page would drop under the cap.
Out of scope until separately approved: withholding ids from the live wall input, raising or bypassing the cap,
using the result for any quantity.

Required tests (AGENTS.md): synthetic positives (outlined letters on a baseline), look-alike negatives (a short wall
stub row, a door-swing arc, a dashed line, hatch ticks), ambiguity/conflict, translation/rotation/scale metamorphic,
input-order and segment-splitting invariance, unrelated-content and viewport-expansion invariance, deterministic
replay and stable ids, no mutation, and a proof that live predictions and the signed Lot16/Maryborough outputs stay
byte-identical with the shadow present.

## 4. Benchmark observations that must not influence the implementation
The Q5446 counts above diagnose the blocker; they are not thresholds. No constant in the module may be fitted to
Q5446, its page numbers, file name, or its expected quantities. The expected outcome of the shadow is a report, not a
score; a page dropping under the cap in the report grants nothing.

## Questions for review
1. Is a shadow classifier acceptable as the route, rather than a different bound on the wall stage?
2. Should it live beside `pb_annotation_cycle_shadow` and share its span helpers?
3. Which lane owns it? (Suggest GPT2 or GPT MAX as the annotation-block owners; the integration lane will verify.)
