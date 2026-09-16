# PDF source visibility remediation architecture v3

Base: `ebb8e9a343a6a1104a0186c2b8a3db7a7b1ea50f` (current `main`, merged PR #323)

This refresh carries the already-reviewed source-visibility architecture onto the post-P2 governing main. PR #323 changes W4 wall candidate identity only; it does not change native PDF extraction, Phase-1 source observations, G17 physical-opening authority, live quantity publication, benchmark gold, or commercial output.

## OBSERVED

1. PR #321 is already merged and established the current native-provenance baseline:
   - `clip_known=True, clip_present=False` means clip association succeeded and no active clip exists;
   - `clip_known=False` means association is unavailable, missing, or unmatched and must never imply unclipped;
   - non-finite native geometry is excluded from authority-bearing coordinate presence.
2. `extract_native_page()` still exposes legacy `segments` as raw extracted vector geometry. Clip state is metadata only; the raw span is not replaced with a proven visible span.
3. `SourceObservationProducer.ingest_native_pdf_bytes()` publishes `native_pdf_segment` observations from raw `segments`. The Phase-1 observation contract does not currently distinguish raw source existence from proven visual presence.
4. Merged PR #319 can resolve `PHYSICAL_OPENING_EXISTS` from producer-backed lineage, but GPT-2 draft PR #322 demonstrates that raw lineage existence is insufficient: clipped/invisible geometry, child-minted page/viewport scope, arbitrary derived geometry, and rectangle-without-wall-continuation attacks remain blocking.
5. PR #323 changed W4 assembly identity to a direction-canonical path fingerprint and left live extraction/commercial publication unchanged. This does not alter the source-visibility design below.
6. Stale PR #308 explored raw-vs-visible geometry and source-integrity diagnostics but predates #318/#321 and must not be cherry-picked.

## INFERENCE

Raw content-stream existence and visual presence are separate propositions.

A raw primitive may remain auditable while being ineligible for semantic or measurement authority. Therefore positive G17 existence must eventually consume only producer-owned visibility-proven source geometry, not generic raw segments or caller-published semantic records.

## PROPOSED SOURCE-VISIBILITY CHANGE

### Preserve legacy raw extraction

Do not redefine `segments` or historical segment IDs. Existing readers keep the current raw geometry contract.

### Add a separate visibility-proven view

Add an additive collection such as `visible_segments` with these rules:

- `clip_known=False` -> retain raw/audit data, emit no authority-eligible visible segment;
- `clip_known=True, clip_present=False` -> raw finite non-degenerate geometry is visibility-eligible;
- `clip_known=True, clip_present=True` with a proven rectangular clip -> emit only the deterministic finite intersection;
- fully clipped primitive -> retain raw/audit data, emit no visible segment;
- unresolved/non-rectangular clip -> retain diagnostic state, emit no authority-eligible visible segment.

Every visible fragment must retain immutable provenance back to the raw primitive and source scope.

### Preserve transform provenance

Continue delegating page-coordinate transforms to PyMuPDF rather than reimplementing CTM composition. Preserve deterministic Form/XObject provenance where available. Explicit recursion/cycle or unresolved transform provenance must fail closed for any authority path.

### Add a distinct Phase-1 observation kind

Do not change the meaning of `native_pdf_segment`.

Add a producer-owned visibility-proven observation kind, e.g. `native_pdf_visible_segment`, emitted only from `visible_segments` and carrying exact document/revision/source SHA/page/snapshot ownership plus immutable raw-primitive provenance.

Unknown visibility must never create a positive visible-segment observation.

## LATER G17 REMEDIATION BOUNDARY

The source-visibility PR must not itself promote G17.

A later separate G17 remediation will:

- ignore generic caller-derived `wall_face_interruption` / `opening_jamb_boundary` records for positive proof;
- recompute structure from producer-owned visibility-proven native observations;
- prove exact document/revision/source/snapshot/page scope;
- refuse derived viewport minting;
- require two source-visible wall faces with real material continuing on both sides of the opening gap;
- require two source-visible jamb boundaries;
- require independent non-overlapping source roots;
- fail closed on incompatible local interpretations;
- keep identity, dimensions, host binding, completeness, void, deductions, FIRM, commercial and JobHub authority closed.

GPT-2 PR #322 must be replayed unchanged against that later G17 remediation head.

## REQUIRED SYNTHETIC PROOF

The source-visibility implementation must cover at minimum:

1. matched drawing / no active clip -> raw and visible spans agree;
2. active rectangular clip -> visible span is exact intersection;
3. fully clipped raw vector -> raw retained, no visible authority segment;
4. extended association unavailable/unmatched -> raw retained, no visible authority segment;
5. unresolved/non-rectangular clip -> no visible authority segment;
6. partial clip -> no raw-extent leakage into visible geometry;
7. nested clip scopes and scope exit;
8. finite / degenerate / non-finite geometry boundaries;
9. Form/XObject transform provenance replay and cycle fail-closed behavior;
10. historical raw segment IDs unchanged;
11. deterministic replay / stable provenance IDs;
12. input-order and no-mutation checks;
13. #321 clip-known ternary unchanged;
14. Phase-1 visible observation preserves exact source scope and raw primitive reference;
15. benchmark-gold/provider-gold/frozen-holdout integrity remains green;
16. live predictions and commercial output remain unchanged.

## EXPECTED FILES

Likely production changes:

- `pb_vector_geometry_v130.py`
- `pb_source_observation_authority.py`

Focused additive tests only for this PR.

Do not modify in this source-visibility PR:

- `pb_physical_opening_authority.py`
- opening identity/dimensions/host/completeness/deductions
- C15/#316
- W4 identity
- benchmark gold/expected/mappings/scorer/tolerances/holdouts
- live `pb_planreader_pdf_extractor.py` prediction logic
- commercial/JobHub publication

## BENCHMARK

Controlled development baseline remains **50.82% = 31/61 accepted**.

This source-integrity work must claim **0.00 percentage-point gain** unless a later separately authorized live-output change is measured.

Architecture unchanged in substance from v2; refreshed only to current post-#323 main. Production implementation may now proceed under the previously accepted review decision.
