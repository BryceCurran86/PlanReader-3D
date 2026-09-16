# PDF Source Visibility Remediation v4

Continuation of the previously reviewed source-visibility architecture, refreshed onto post-#324 main `4725618af71377aa6828f5374849c5d3ac167e37`.

## OBSERVED

- `pb_vector_geometry_v130.extract_native_page()` preserves raw vector segments and additive clip provenance (`clip_known`, `clip_present`, `clip`) without claiming that raw PDF vector instructions were actually visible.
- PyMuPDF `Page.get_drawings(extended=True)` exposes hierarchical `clip` / `group` scopes via `level`; its `scissor` is insufficient by itself to prove that an arbitrary clipping path is rectangular.
- `pb_source_observation_authority.SourceObservationProducer` publishes producer-owned raw `native_pdf_segment` observations from immutable PDF bytes, but generic derived observations can carry arbitrary semantic kinds if a trusted producer explicitly writes them.
- G17 downstream authority must not treat raw, clipped, clip-unknown, or caller-labelled derived geometry as visible physical structure.

## INFERENCE

- Raw content-stream presence and visual presence are distinct propositions.
- Unknown clip state cannot prove visibility.
- Active clipping cannot be treated as exact rectangular clipping merely from PyMuPDF `scissor`.
- A semantic kind named `native_pdf_visible_segment` is not authority by itself; downstream resolution needs a producer-owned visibility receipt and raw-parent recomputation.

## PROPOSED / IMPLEMENTED IN THIS PR

Phase 1 is intentionally conservative:

1. Preserve the existing raw source-observation contract unchanged.
2. Add `SourceVisibilityProducer`, wrapping `SourceObservationProducer` without exposing its generic derived writer to ordinary consumers.
3. Re-decode the same immutable PDF bytes and inspect each existing native segment's clip provenance.
4. Mint `native_pdf_visible_segment` only when:
   - geometry is finite and non-degenerate;
   - clip association is known;
   - no active clip is present.
5. Any active clip remains non-authority-visible in Phase 1, including rectangular clips, until clip-shape rectangularity and exact segment intersection are independently proven in a later enhancement.
6. Visibility observations retain exactly one raw `native_pdf_segment` parent, the same document/revision/source/page/partition, identical geometry, and no derived viewport authority.
7. `SourceVisibilityAuthority.resolve_visible()` requires a private producer visibility receipt and independently resolves/rechecks the raw parent. A generic producer publishing the same observation kind cannot self-certify visibility.
8. This PR stops at source visibility. It does not change G17 physical-opening existence, identity, dimensions, host binding, deductions, live extraction, commercial output, JobHub, benchmark gold, mappings, scorer tolerances, or holdouts.

## EXPECTED ABSTENTIONS

- extended clip association unavailable/unmatched;
- any active clip in Phase 1;
- non-finite or degenerate segment geometry;
- missing producer visibility receipt;
- missing or mismatched raw parent lineage.

## TEST PLAN

- unclipped native segments produce visible receipts;
- fully clipped real PDF vectors retain raw observations but produce no visible receipts;
- non-rectangular real PDF clipping produces no visible receipts;
- clip-unknown and active-clip synthetic states abstain;
- generic derived `native_pdf_visible_segment` cannot self-certify;
- deterministic replay retains snapshot and visible IDs;
- no viewport authority is minted;
- existing raw source observations remain intact.

## BENCHMARK

Development benchmark remains `31/61 = 50.82%`. It does not set any implementation threshold or visibility rule. No benchmark gain is claimed by this source-layer PR.
