# G17 visible opening existence remediation — architecture v1

Base: post-source-visibility main `b64b59bd89e78beba3074efcc4418e8e5f76c604`.

## OBSERVED

- `PhysicalOpeningAuthority` currently consumes `SourceObservationAuthority` and can publish `PHYSICAL_OPENING_EXISTS` from caller-published derived observations of kinds `wall_face_interruption` and `opening_jamb_boundary`.
- Current candidate discovery traces those derived records to native roots, but does not require the native roots to be producer-proven visible.
- Two parallel face records plus two matching jamb records are sufficient for the current positive pattern; a closed four-edge rectangle can therefore satisfy it without visible wall continuation on both sides of the supposed opening.
- GPT-2 draft PR #322 attacks unrelated-root semantic self-certification, page/viewport laundering, fully-clipped raw vectors, unresolved clipping, rectangle-only structure, missing jambs, weak semantic-only evidence, shared lineage, ambiguity, and downstream leakage.
- Merged source-visibility PR #325 provides producer-owned `native_pdf_visible_segment` observations. Unknown clip association and active clips remain fail-closed in phase 1.

## INFERENCE

- Caller-assigned structural semantic labels are not proof of a physical opening.
- Positive G17 existence must be rediscovered from producer-proven visible native geometry.
- A local physical opening requires more than a box: two wall faces must each visibly continue on both sides of a common gap, and two independent visible jambs must connect the two face offsets at the gap boundaries.
- Source visibility does not mint viewport authority. G17 must not invent a viewport.

## PROPOSED

1. Positive G17 existence consumes `SourceVisibilityAuthority`.
2. Preserve raw `SourceObservationAuthority` constructor compatibility only so the frozen #322 suite replays unchanged; raw source authority alone can never publish `PHYSICAL_OPENING_EXISTS`.
3. Ignore caller-published `wall_face_interruption` / `opening_jamb_boundary` records for positive existence.
4. Enumerate only producer-resolved visible native segments from the same snapshot/document/revision/source/page.
5. Discover a positive local opening only when:
   - two distinct parallel wall-face axes each contain a visible left continuation and visible right continuation separated by the same projected gap;
   - two distinct visible jamb segments connect the corresponding face endpoints at the left and right gap boundaries;
   - all six supporting visible observations are distinct;
   - ownership is consistent; and
   - no incompatible competing candidate contains the selected seed geometry.
6. A closed four-edge rectangle without exterior wall continuation is non-positive.
7. Raw native segments, clipped/unknown-visibility segments, schedule/tag/CV/OCR/heuristic-only observations, caller-derived semantic records, page/revision/source mismatch, and viewport minting remain non-positive.
8. Identity, dimensions, host binding, completeness, physical void, deductions, FIRM commercial publication, and JobHub remain closed.

## EXPECTED ABSTENTIONS / CONFLICTS

- Raw `SourceObservationAuthority` only -> ABSTAINED.
- No visible receipts -> ABSTAINED.
- Fully clipped or unresolved/non-rectangular clip -> ABSTAINED.
- Rectangle only -> ABSTAINED.
- Two faces without two jambs -> ABSTAINED.
- One continuation side missing -> ABSTAINED.
- Shared/duplicated support -> ABSTAINED.
- More than one incompatible candidate covering the seed -> CONFLICT.
- Page/source/revision mismatch -> fail closed using existing source-authority semantics.

## REQUIRED TESTS

- Frozen GPT-2 #322 replay unchanged.
- Positive synthetic with two split wall faces plus two jambs.
- Rectangle-only negative.
- One-sided continuation negative.
- Two faces/no jambs negative.
- Fully clipped negative.
- Active unresolved/non-rectangular clip negative.
- Raw-source-only negative.
- Caller-derived semantic labels from unrelated native roots negative.
- Page laundering negative.
- Viewport minting negative.
- Shared/duplicated support negative.
- Competing incompatible candidates -> CONFLICT.
- Translation/rotation/scale metamorphic invariance.
- Input-order and harmless continuation-segment splitting invariance.
- Deterministic replay / stable IDs.
- Live/commercial/JobHub unchanged.

## BENCHMARK

The development baseline `31/61 = 50.82%` is evaluation telemetry only. It must not determine geometry thresholds or candidate selection. No benchmark gain is claimed by this G17 authority remediation itself.
