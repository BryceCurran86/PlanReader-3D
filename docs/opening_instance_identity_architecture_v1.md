# Opening instance identity authority — architecture v1

Base: merged G17 main `62a161519e617cdf9ce23069820dbf7c68aaf521`.

## OBSERVED

- G17 now proves one local physical opening existence from producer-owned visible native geometry.
- Every support belonging to the same resolved opening receives the same deterministic `PhysicalOpeningExistenceRecord.record_id` because the record payload is derived from the same document/revision/source/snapshot/page and the same six producer-owned visible supports/raw parents.
- `PhysicalOpeningAuthority.compare_identity()` currently resolves the two source observations but always abstains.
- `physical_opening_identity` capability is currently `False`.
- Tags, schedule rows, OCR text, swing arcs and caller-derived semantic records do not establish G17 existence.

## INFERENCE

- The safest local instance identity is already present in the G17 existence authority: the deterministic existence `record_id`.
- A second centroid/bounding-box/tag-derived identity ledger would duplicate authority and could collapse repeated schedule marks or nearby openings incorrectly.
- Identity comparison must independently re-prove G17 existence for both selectors. Caller-supplied IDs or asserted opening objects are not authority.
- Equality can be positively established only when both selectors resolve to the same producer-owned G17 existence record.
- Two independently proven openings in the same authenticated document/revision/source/snapshot/page whose existence record IDs differ are distinct local instances.
- Different documents, revisions, source byte hashes, snapshots or pages require a separate cross-view/revision equivalence authority and therefore must abstain rather than guessing equivalence.

## PROPOSED

1. Keep `PhysicalOpeningAuthority.compare_identity()` as the sole physical-opening instance identity comparison authority.
2. For each selector, call `prove_existence()` independently.
3. If either selector fails to produce a corroborated G17 existence record, identity remains unresolved.
4. If authenticated scope differs across document/revision/source SHA/snapshot/page, return fail-closed unresolved identity. Do not infer cross-sheet or cross-revision sameness from geometry or tags.
5. If both existence `record_id` values are equal, return `CORROBORATED`, `proven_same=True`, and expose that producer-owned record ID as the resolved physical-opening identity.
6. If both are corroborated in the exact same scope but record IDs differ, return `CORROBORATED`, `proven_same=False`, with an explicit distinct-instance reason.
7. Flip only `physical_opening_identity` capability to `True`.
8. Dimensions, type authority, host identity/binding, completeness, physical void, deductions, net wall area, FIRM/commercial output and JobHub remain closed.

## EXPLICIT NON-AUTHORITY INPUTS

The following must never establish instance identity by themselves:

- opening/type tags such as `D-01`;
- schedule quantities or rows;
- OCR/text similarity;
- nearest centroid or bounding box;
- nearest wall;
- caller-provided opening IDs;
- caller-provided geometry;
- filename/project/benchmark identifiers;
- expected quantities.

## REQUIRED TESTS

- two selectors from the same G17 opening -> same identity;
- deterministic replay within the same snapshot -> same identity;
- two separately proven openings in one page -> distinct local identities;
- identical geometry in a different document -> abstain from sameness;
- identical geometry on a different page -> abstain from sameness;
- different revision/source bytes -> abstain from sameness;
- raw-native-only evidence -> unresolved identity;
- non-opening visible geometry -> unresolved identity;
- caller-derived structural semantics cannot create identity;
- repeated tags/schedules are irrelevant to identity authority;
- downstream capabilities remain false after identity resolution.

## BENCHMARK

No benchmark gain is claimed by this authority seam alone. Development telemetry remains `31/61 = 50.82%` until a controlled score-affecting adapter is merged and rerun.
