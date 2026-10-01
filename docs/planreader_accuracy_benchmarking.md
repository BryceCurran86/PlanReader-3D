# PlanReader V2 Accuracy, Truth and Coverage Validation

PlanReader's active validation system is the Full Plan V2 independently source-closed truth framework.

## Truth chain

`SOURCE DOCUMENT → SOURCE EVIDENCE → PHYSICAL OBJECT → CANONICAL OBJECT → VERIFIED GEOMETRY → VERIFIED QUANTITY → CUSTOMER OUTPUT`

A truth record must state only what the source proves. Do not manufacture geometry, dimensions, relationships, materials or quantities for downstream convenience.

## Verification states

Where practical, distinguish object exists, object identified, geometry verified, quantity verified, and fully source-closed.

Coverage should be traceable through:

`DETECTED → AUTHENTICATED → CANONICALIZED → QUANTIFIED → PUBLISHED`

## Active scoreboard

V2 progress is multi-dimensional: source-closed truth coverage, physical-object detection coverage, canonicalization coverage, geometry correctness, quantity correctness, strict-exact matches where appropriate, correct abstention, provenance completeness, customer-runtime publication coverage, hallucinations, gross mismatches, and duplicate/double-counting errors.

Do not collapse these into a legacy headline percentage.

## Active files and commands

V2 suite: `benchmarks/frozen_holdout/full_plan_v2/`

Truth integrity: `python scripts/check_full_plan_v2_integrity.py`

Fail-closed V2 baseline/status evaluation: `python benchmarks/frozen_holdout/full_plan_v2/run_baseline.py`

The baseline may remain UNPUBLISHED while projects are incomplete. That is correct fail-closed behaviour.

## Change separation

V2 truth and production runtime code must be changed in separate PRs. CI enforces this with `scripts/check_v2_truth_separation.py`.

Production fixes must never edit V2 truth simply to make code pass.

## Primary milestone

`V2_CANONICAL_BUILDING_CORE`

Normal upload should increasingly resolve into stable building/storey/room/wall/opening/door-window/slab-floor/ceiling objects with geometry, relationships and provenance preserved for downstream quantities and customer publication.
