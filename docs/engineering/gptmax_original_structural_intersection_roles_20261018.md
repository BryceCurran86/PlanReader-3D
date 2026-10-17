# GPT MAX source-owned structural intersection roles — architecture report (2026-10-18)

## Observed repository behavior
AGENTS.md and docs/AI_ENGINEERING_PLAYBOOK.md require W2 graph construction, W3 junction classification, W4 wall assembly, and a separate physical existence/equivalence authority. The original raster-host census in tools/diag_gptmax_raster_host_source_membership.py cannot promote a W4 host. Neither positive painted pixels nor a CAD endpoint by itself establishes physical SAME.

## Original-source observations (NOT thresholds or prediction inputs)
The exact SHA-256 architectural PDF (10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844) and structural PDF (b40259589dd39a46e45d25e145cfa789d9a9415b50613ebc4fee01dceab6b3d6) were independently verified locally, without modifying either. Original structural page 10 contains a five-path T-junction and a separate four-path perpendicular return. Positive raster ink is non-unique across competing half-point registrations, so cross-document SAME remains ABSTAIN.

## Inference
A gap in a structural face can be a source-owned perpendicular T-junction rather than a missing horizontal wall fragment. A three-sided return is not necessarily a long horizontal wall flank. Neither observation proves an opening host or metric area.

## Proposed opt-in source-only change
tools/gptmax_original_wall_intersection_authority.py classifies exact source-path structural T-junction/return evidence without mutating geometry or publishing. It fails closed on competing full OR partial same-layer segments and partial bridges. tests/test_gptmax_original_wall_intersection_authority.py covers positives, negatives, source-layer conflicts, partial overlaps, translation/scale, source-order permutation, and no-mutation.

## Authority boundaries and files untouched
No producer wiring, W2/W3/W4, host/frame, scale, QuantityEvidence, customer output, original PDF, benchmark truth, denominator, evaluator, 20,000 primitive cap, or snapping policy changes. Outputs retain canonical_w4_host=ABSTAIN, cross_document_same_physical_wall=ABSTAIN, opening_frame/area/count=ABSTAIN, new_firm_quantity=False.

## Validation / release decision
Source-neutral and original-private replay locally passed 18 tests (the original-only test is kept private and is NOT in this public PR). Exact-head original-source CI and independent retention review remain mandatory before merge. This is DRAFT and must not be treated as ninth FIRM quantity or an official score.
