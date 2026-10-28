# GPT MAX — Postmerge structural lintel source-identity and numeric-scale safety

29 October 2026. Current owner instructions: `AGENTS.md`; measurement provenance: `docs/AI_ENGINEERING_PLAYBOOK.md`; preceding implementation AntiGravity #4078. Coordinated under #3462 comment 6476181497. This is a negative-only source-boundary fix to a merged **shadow** calculator, not the missing source-backed producer.

## OBSERVED

Merged `pb_structural_lintel_pier_bearing_authority.StructuralLintelPierBearingAuthority.evaluate_lintel_bearing` accepted freely supplied jambs, pier width and bearing measurements, assumed `scale_ratio=0.01764`, assigned metric lengths, and returned `LINTEL_BEARING_CONFIRMED/CANDIDATE` without an authenticated page/viewport scale, source SHA/revision, physical host, original lintel mark or approved bearing specification. Invalid `float("nan")` lengths bypassed every numeric comparator. It constructed a stable ID without pier identities, supplied scale or callout. No genuine production issuer consumes this module.

## INFERRED

A plausible geometric fit is not a source-owned structural lintel. An unverified scale cannot generate a measured metric length, and a 100mm reference must not be mistaken for universally applicable structural/code compliance. Changing the caller scale or selected physical piers must not silently recycle a diagnostic identifier.

## PROPOSED / IMPLEMENTED

- Require all geometry/length inputs to be real, finite and nonnegative where physically appropriate; fail closed on NaN, Inf, malformed points, invalid material and missing pier/context strings.
- Remove the 0.01764 default. If no explicit scale is supplied, retain point geometry, set all metric fields `None`, and issue `ABSTAINED_UNVERIFIED_SCALE` with `source_viewport_scale_receipt_missing`. An explicitly supplied ratio **still does not authenticate** a viewport scale.
- For numerically coherent geometry with explicit positive scale, issue only `LINTEL_BEARING_GEOMETRIC_CANDIDATE`, retain CANDIDATE and the explicit first remaining gate `source_lintel_host_scale_and_specification_unproven`. Never issue legacy `LINTEL_BEARING_CONFIRMED`, claim code-compliant bearing seats, FIRM or takeoff.
- Normalize physical-reference illustrative limits to the caller's explicit numeric unit ratio (not an assumed 1:100 point threshold). These remain provisional diagnostic comparisons, not NCC/AS compliance checks.
- Include both pier identities, explicit scale, scope and callout in source-neutral stable diagnostic ID. This is NOT a producer source lineage/receipt; the next owner of source elevation/structural origin must connect existing source evidence before any promotion.

## VALIDATION / NON-CHANGES

New source-neutral adversarial tests: no scale/null metrics, NaN/Inf/boolean/negative inputs, missing scope, immutable serialized nulls, changed-scale/physical-pier IDs, jamb reversal/replay, provisional numeric positive and threshold conversions. Existing 8 synthetic tests now specify their test-only ratio and do not assert compliance. Validate exact-head Python 3.13 and 3.14 full CI, frozen-truth separation and signed/customer no-mutation, alongside reviewer inspection.

No changes to original PDFs, source hash expectations, full-plan frozen 120 denominator, developer-set scorer, source issuer, customer contracts, authenticated signed Lot16 nine/Maryborough three, 20,000 primitive cap or 2.5pt snap. This cannot count as a new FIRM quantity, customer row, scored accuracy increase, or merged milestone until actual required gates pass.
