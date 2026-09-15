# PDF source visibility remediation architecture v2

Base: `26d9225ecd4eaf1e79109600374e88a1d48a505d` (current `main`, merged PR #321)

This is the architecture report required by `AGENTS.md` before production mutation.

## OBSERVED repository behavior

1. PR #321 completed the Priority-1 residual provenance fixes on current main:
   - `clip_known=True, clip_present=False` now means a drawing seqno was matched and no active clip exists;
   - `clip_known=False` means the extended clip association is unavailable, missing, or unmatched;
   - non-finite native line/rect/word coordinates are rejected at extraction;
   - lineage refuses `page_coords_present=True` unless every coordinate is finite.
2. `extract_native_page()` still returns legacy `segments` as raw extracted vector paths. `clip`, `clip_present`, and `clip_known` are additive metadata; the raw geometry is not clipped to its proven visible portion before entering the legacy `segments` collection.
3. PyMuPDF documents `Page.get_drawings(extended=True)` as a hierarchical structure: clip/group records establish scopes using `level`; a clip's `scissor` applies to subsequent records at deeper levels until scope ends. Ordinary vector extraction can still expose drawing paths that are not visually present on the rendered page.
4. `SourceObservationProducer.ingest_native_pdf_bytes()` currently converts `native["segments"]` into `native_pdf_segment` observations containing source identity and four coordinates, but it does not preserve a positive visibility proposition or the clip-known/clip-present state in the source-observation contract.
5. `PhysicalOpeningAuthority` from merged PR #319 can therefore see source-root existence and geometry but cannot prove that the source geometry was visible. GPT-2 PR #322 independently encodes this as a blocking attack using real PDF clipping operators.
6. Stale PR #308 already explored a stronger separation between raw source primitives and visible rectangularly-clipped geometry, plus Form/XObject provenance and fail-closed source-integrity diagnostics. It predates merged #318/#321 and conflicts with their extractor changes; it is research evidence, not a branch to cherry-pick.
7. Current live quantity prediction, wall deduction, commercial output, and JobHub publication do not depend on PR #319 physical-opening existence, so the current authority defect has not moved the controlled 50.82% benchmark.

## INFERRED authority requirement

Raw content-stream existence and visual presence are separate propositions.

A source-native segment may be auditable even when it cannot safely participate in semantic or measurement authority. Therefore:

- legacy/raw `segments` must remain available for compatibility and audit;
- a separate additive visibility-proven geometry view must be created;
- unknown visibility must not be treated as visible;
- rectangular clipping may be used only when the visible intersection is deterministic and finite;
- unresolved/non-rectangular clipping must block affected geometry from positive authority rather than approximating it;
- Form/XObject provenance failures must fail closed rather than silently dropping provenance;
- positive G17 opening-existence authority may consume only visibility-proven source geometry.

This does not itself establish opening identity, dimensions, host binding, universe completeness, physical void, net wall area, FIRM quantity authority, or commercial publication.

## PROPOSED change

### 1. Preserve legacy raw extraction

Do not redefine the existing `segments` contract or historical IDs. Existing W2/live readers continue to receive the same raw geometry behavior apart from already-merged #321 safety fixes.

### 2. Add a visibility-proven segment view

Extend `extract_native_page()` additively with a separate collection such as `visible_segments`.

For each eligible raw source primitive:

- `clip_known=False` -> no positive visible segment is emitted for authority use; retain raw source/audit metadata and an explicit unresolved visibility diagnostic;
- `clip_known=True, clip_present=False` -> raw geometry is visibility-eligible, subject to normal finite/non-degenerate checks;
- `clip_known=True, clip_present=True` with a proven rectangular clip -> emit only the deterministic segment/rectangle intersection with that clip;
- fully clipped primitives -> emit no visible segment while retaining raw source provenance;
- unresolved/non-rectangular clip state -> emit no authority-eligible visible segment and preserve a blocking diagnostic.

The implementation must preserve source primitive identity and enough provenance to trace each visible fragment back to the immutable raw primitive.

### 3. Form/XObject provenance

Preserve deterministic Form/XObject provenance where PyMuPDF exposes it. Continue delegating coordinate transformation to PyMuPDF rather than reimplementing CTM composition.

If an explicit recursive/cyclic Form structure is detected or transform provenance cannot be safely established for a candidate authority path, fail closed with deterministic diagnostics.

Do not silently reinterpret local Form transforms as whole-sheet transforms.

### 4. Phase-1 source observations

Do not silently replace the meaning of existing `native_pdf_segment` observations.

Add a distinct producer-owned observation kind for visibility-proven geometry, e.g. `native_pdf_visible_segment`, emitted only from `visible_segments` and bound to the same document/revision/source hash/page/snapshot.

A visible observation must retain an immutable reference to its raw source primitive. If the visible geometry was clipped, the emitted geometry is the proven visible intersection, not the raw pre-clip span.

Unknown/unresolved visibility never creates `native_pdf_visible_segment` positive evidence.

### 5. G17 positive authority boundary

After the upstream visibility producer exists, `PhysicalOpeningAuthority` remediation may be implemented separately so that positive physical-opening existence is recomputed only from `native_pdf_visible_segment` observations.

Generic caller-published derived `wall_face_interruption` / `opening_jamb_boundary` records remain ineligible to establish existence.

The later G17 resolver must additionally prove:

- same exact document/revision/source hash/snapshot/page ownership;
- no derived viewport minting;
- source-visible two-face wall continuation on both sides of the gap;
- two source-visible jamb boundaries;
- independent non-overlapping native roots;
- no incompatible local interpretation.

GPT-2 PR #322 is the independent red-team suite and must be replayed unchanged against that later remediation head.

## EXPECTED ABSTENTIONS

The source-visibility layer must fail closed when:

- extended clip association is unavailable or unmatched;
- clip geometry/state is unresolved;
- a primitive is fully outside its proven clip;
- geometry is non-finite or degenerate for active topology;
- Form/XObject provenance has an integrity failure;
- a positive visible fragment cannot be deterministically tied back to a raw primitive.

No nearest/first/smallest arbitration and no rendering guess may convert these states to visible authority.

## SYNTHETIC PROOF REQUIRED

Before acceptance, tests must include:

1. matched drawing with no active clip -> raw and visible geometry agree, `clip_known=True`;
2. active rectangular clip -> visible geometry equals exact deterministic intersection;
3. fully clipped raw vector -> retained raw source, no visible authority segment;
4. extended association unavailable/unmatched -> raw source retained, no visible authority segment;
5. unresolved/non-rectangular clipping -> no visible authority segment;
6. finite/degenerated/non-finite geometry boundaries;
7. nested clip scopes and scope exit behavior;
8. Form/XObject transform provenance replay and cycle fail-closed behavior;
9. historical segment IDs and existing raw `segments` semantics unchanged;
10. deterministic replay/stable fingerprints;
11. input-order/no-mutation checks;
12. existing Priority-1 `clip_known` ternary remains intact;
13. benchmark-gold/provider-gold/holdout integrity remains green;
14. live prediction and commercial output remain unchanged;
15. GPT-2 clipped/invisible G17 attack cannot obtain positive existence from the new visibility layer.

## FILES EXPECTED TO CHANGE AFTER REVIEW

Likely:

- `pb_vector_geometry_v130.py`
- `pb_source_observation_authority.py`
- focused/additive source-integrity and source-observation tests

The first remediation PR should stop at source visibility/source-observation integrity. It should not simultaneously promote G17 semantic authority.

A later separate G17 remediation PR will modify `pb_physical_opening_authority.py` and replay PR #322 unchanged.

## FILES / DOMAINS THAT STAY UNTOUCHED

- benchmark gold, expected quantities, mappings, scorer, tolerances, frozen holdouts
- `pb_planreader_pdf_extractor.py` live prediction logic
- wall-length/wall-height quantity authority
- C15/#316 ceiling work
- opening identity, dimensions, host binding, completeness, deductions
- commercial takeoff / JobHub publication
- Cursor Priority-2 W4 identity work

## BENCHMARK

Controlled development baseline remains **50.82% — 31/61 accepted**.

This source-integrity remediation is additive/shadow authority infrastructure and must claim **0.00 percentage-point gain** unless a later separately-authorized live-output change is measured in the controlled comparator.
