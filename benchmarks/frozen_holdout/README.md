# Active PlanReader Validation: Full Plan V2

The only active PlanReader benchmark / validation framework in this repository is:

`benchmarks/frozen_holdout/full_plan_v2/`

The previous legacy percentage/public-tender/golden-plan benchmark systems are retired and must not be used for scoring, product headlines, regression gates, roadmap decisions, investor progress, or production truth. Their history remains available in Git.

## Active truth chain

`SOURCE DOCUMENT → SOURCE EVIDENCE → PHYSICAL OBJECT → CANONICAL OBJECT → VERIFIED GEOMETRY → VERIFIED QUANTITY → CUSTOMER OUTPUT`

V2 truth must remain source-closed and provenance-preserving. Do not invent geometry, identity, relationships, dimensions, materials, or quantities that the source does not prove.

## Active scoreboard

V2 progress is evaluated across multiple metrics rather than one headline percentage:

- source-closed truth coverage
- physical-object detection coverage
- canonicalization coverage
- geometry correctness
- quantity correctness
- strict-exact matches where appropriate
- correct abstention
- provenance completeness
- customer-runtime publication coverage
- hallucinations
- gross mismatches
- duplicate / double-counting errors

The primary milestone is `V2_CANONICAL_BUILDING_CORE`.

## CI

- `scripts/check_v2_truth_separation.py` prevents V2 truth and production code from changing in the same PR.
- `scripts/check_full_plan_v2_integrity.py` validates configured V2 projects, reference-takeoff byte pins, and verified object references.
- V2 JSON is forced to LF by `.gitattributes` so byte pins are cross-platform stable.
