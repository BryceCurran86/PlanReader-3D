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

## Development accuracy scoreboard

While V2 project truth is still expanding, use the development scoreboard to
measure only the independently verified denominator items already present in all
four project manifests:

```powershell
python benchmarks/frozen_holdout/full_plan_v2/run_development_scoreboard.py
python benchmarks/frozen_holdout/full_plan_v2/run_development_scoreboard.py --produced-dir <sealed-output-dir>
```

Each sealed output directory may contain one `<project_id>.json` file per
configured project. A file is a JSON list of production results with
`quantity_id`, `trade_category`, `value`, `unit`, `object_refs`,
`lineage_ok`, and `abstained`.

The development scoreboard reports `observed_accuracy` for partial diagnostic
runs, but `development_accuracy` remains null until every configured project
has a sealed output file and no lineage conflict is present. This prevents a
partial or cherry-picked run from becoming the product accuracy headline.

Unsupported production quantities are counted as `hallucinations` and reduce
`precision_adjusted_accuracy`. Missing expected items, partial identity
closures, outside-tolerance quantities, and unresolved duplicates remain
separate failure states.

Object matching remains exact identity matching. The scoreboard must never
derive benchmark `object_refs` from labels, room names, descriptions, or
numeric similarity. The production-to-benchmark reconciliation layer must
supply those identities from source/canonical lineage before a sealed run can
be scored.

This development score is separate from the V2 publication gate. A project may
contribute independently verified development truth while its overall manifest
remains `INCOMPLETE`; that does not make the project or suite publishable.
