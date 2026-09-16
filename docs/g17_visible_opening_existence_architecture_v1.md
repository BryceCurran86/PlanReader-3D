# G17 visible opening existence remediation — architecture v1

Base dependency: source-visibility PR #325 (`dfc53632c7ed1622d68f01449c63a6ab72095b8f`).

## OBSERVED

- `PhysicalOpeningAuthority` currently consumes `SourceObservationAuthority` and can discover a positive `PHYSICAL_OPENING_EXISTS` proposition from caller-published derived observations of kinds `wall_face_interruption` and `opening_jamb_boundary`.
- The current structural candidate resolver traces derived lineage down to native source roots, but it does not require those roots to be producer-proven visible.
- The current positive structural pattern is satisfied by two parallel face records plus two jamb records. A closed four-edge rectangle can therefore satisfy the pattern without independent visible wall continuation on both sides of the supposed opening.
- GPT-2 PR #322 attacks exactly these weaknesses: unrelated-root semantic self-certification, page/viewport laundering, fully-clipped raw vectors, unresolved clipping, rectangle-only structure, missing jambs, weak semantic-only evidence, lineage overlap, ambiguity, and downstream leakage.
- PR #325 introduces a separate producer-owned `SourceVisibilityAuthority`; only finite/non-degenerate native PDF segments with independently resolved visibility may become `native_pdf_visible_segment` observations. Phase 1 positively accepts only `clip_known=True, clip_present=False`; active/unknown clip remains fail-closed.

## INFERENCE

- A derived semantic label is not evidence that a physical opening exists. `wall_face_interruption` and `opening_jamb_boundary` records must not be sufficient positive inputs merely because they trace to some native geometry.
- Positive G17 existence should be rediscovered from producer-proven visible native geometry, not from caller-assigned semantic kinds.
- A local opening proof requires more than a four-edge box. For two wall faces, each face must visibly continue on both sides of the opening span, and two independent visible jamb boundaries must connect the face offsets at the opening ends.
- Because the new visibility layer does not mint viewport authority, a G17 positive result must not invent one. Page/source/revision ownership comes from producer-owned visible observations; viewport remains unavailable unless a separately authenticated viewport binding exists.

## PROPOSED

1. Extend the G17 authority boundary to consume `SourceVisibilityAuthority` for positive existence.
2. Keep raw `SourceObservationAuthority` compatibility only as a fail-closed read path so the frozen #322 suite can replay unchanged; raw source authority alone can never produce `PHYSICAL_OPENING_EXISTS`.
3. Positive candidate discovery ignores caller-published `wall_face_interruption` / `opening_jamb_boundary` semantic records.
4. Enumerate producer-proven `native_pdf_visible_segment` observations from the same snapshot/page/document/revision/source.
5. Discover a local structural opening only when all of the following are deterministically present:
   - two parallel wall-face lines;
   - each wall face has a left-side visible continuation segment and a right-side visible continuation segment, collinear with that face and terminating at the same opening boundaries;
   - two visible jamb segments connect the corresponding face endpoints at those boundaries;
   - all required visible segment observation IDs are distinct;
   - no competing incompatible candidate contains the selected seed geometry.
6. A simple closed rectangle without exterior face continuation is not a positive opening.
7. Direct raw native segments, clipped/unknown-visibility segments, schedule/tag/CV/OCR/heuristic-only evidence, caller-derived semantic records, page/revision/source mismatches, and viewport minting remain non-positive.
8. Existence output remains narrower than identity, dimensions, host binding, completeness, physical void, deductions, FIRM commercial publication, or JobHub. Those capabilities remain closed.

## EXPECTED ABSTENTIONS / CONFLICTS

- Raw `SourceObservationAuthority` without visibility authority -> ABSTAINED.
- No visible source receipts -> ABSTAINED.
- Fully clipped or unresolved/non-rectangular clip -> ABSTAINED.
- Rectangle only, no two-sided wall continuation -> ABSTAINED.
- Two faces without two jambs -> ABSTAINED.
- One face continuation side missing -> ABSTAINED.
- Shared/duplicated visibility observation reused for independent supports -> ABSTAINED.
- More than one incompatible structural candidate covering the same seed -> CONFLICT.
- Any page/source/revision mismatch -> ABSTAINED / CONFLICT per existing source authority status.

## REQUIRED TESTS

- Frozen GPT-2 #322 replay unchanged.
- Positive synthetic: two wall faces, two-sided continuation on both faces, two jambs -> existence CORROBORATED.
- Rectangle-only negative.
- One-sided continuation negative.
- Two faces/no jambs negative.
- Fully clipped negative.
- Active unresolved/nonrect clip negative.
- Raw-source-only authority negative.
- Caller-derived semantic labels from unrelated native roots negative.
- Page laundering negative.
- Viewport minting negative.
- Duplicate/shared visible lineage negative.
- Competing incompatible opening candidates -> CONFLICT.
- Translation/rotation/scale metamorphic invariance.
- Input-order and segment-splitting invariance where the same physical continuation remains represented.
- Deterministic replay / stable candidate and record IDs.
- Live/commercial/JobHub unchanged.

## BENCHMARK

The development score `31/61 = 50.82%` is evaluation telemetry only and must not determine geometry thresholds or candidate selection. This G17 change may unlock later score-producing opening identity/dimension/host/deduction work, but no score gain is claimed by this architecture document.
