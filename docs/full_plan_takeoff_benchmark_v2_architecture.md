# Full-Plan Takeoff Reconciliation Benchmark V2 — Architecture Review

Status: benchmark/evaluation architecture only. No production extraction, measurement authority, commercial publication, benchmark gold, or scorer implementation changes are made by this report.

## Compliance

Files read:
- AGENTS.md
- docs/AI_ENGINEERING_PLAYBOOK.md
- docs/planreader_public_tender_benchmarks.md
- .github/workflows/ci.yml
- pb_takeoff_coverage_registry.py
- pb_takeoff_coverage_audit_adapter.py
- pb_quantity_takeoff_adapter.py
- pb_takeoff_output_authority.py

Functions/contracts traced:
- pb_takeoff_coverage_registry.build_coverage_registry_v1
- CoverageRegistryRunManifestV1 / CoverageRegistrySummaryV1 / CoverageObjectRecordV1
- pb_quantity_takeoff_adapter.quantity_evidence_to_takeoff_output_row
- pb_takeoff_output_authority.TakeoffOutputRow
- existing extractor/evaluator firewall documented for pb_benchmark_accuracy_engine

Authority boundaries crossed: none. This work is read-only evaluation downstream of existing physical-object and QuantityEvidence authorities.

Files that remain untouched in the implementation PR:
- pb_planreader_pdf_extractor.py
- pb_planreader_jobhub_publish_contract.py
- live wall/opening/structural authority modules
- W10 takeoff_eligible / deduction_authority defaults
- existing public-tender gold, mappings, tolerances and canonical-five manifests
- pb_benchmark_accuracy_engine.py

## Observed repository behaviour

1. Physical existence is already owned upstream. The coverage registry does not create objects; it consumes producer-owned admitted-object snapshots.
2. QuantityEvidence.input_entity_ids and editable dependent_quantity_ids are the approved exact object-to-quantity seams.
3. TakeoffOutputRow.quantity_id is the approved exact quantity-to-output seam.
4. build_coverage_registry_v1 is a left join over admitted objects and independently reports unaccounted, partial, abstained and accounted object states plus reverse orphan/dangling quantity census.
5. Coverage v1 intentionally states expected_family_completeness=UNKNOWN. Therefore its ACCOUNTED state alone cannot prove that every takeoff family that should exist has been produced.
6. Existing benchmark documentation enforces a strict extractor/evaluator firewall: expected values may only enter after extraction is sealed.
7. CI rejects production-code and benchmark-defining-file changes in the same PR.

## New source suite

The replacement headline suite uses the newly supplied Australian project sets, not the historical Kenyan canonical five.

Currently identified new projects:
1. Lot 16 Power — architectural construction plans plus structural engineering set.
2. 3LAUREL — complete construction plan set Rev3.
3. Maryborough Service Station — combined architectural set.
4. Q5446 — standard plans plus siting, inclusions, specification/selection and estimate-support documents.
5. Reserved fifth new project slot — must remain NOT_CONFIGURED until a fifth independent new project plan/takeoff pair is supplied and verified.

The historical KSTVET/Murera/Ghazi/Lamu/Umma suite remains historical evidence only and must not silently fill the fifth slot.

## Inference

The user-facing question is not “did a selected benchmark row pass?” It is:
“For every independently verified takeoff quantity, which physical surfaces/objects make it up, did PlanReader recover those objects, did it publish the corresponding quantity, how close was the quantity, and what exactly was missed?”

Coverage v1 supplies the production-side lineage needed for this, but V2 requires a separate expected takeoff universe because expected-family completeness is deliberately unknown in coverage v1.

That expected universe is evaluation truth only. It must never be imported by extraction, object admission, quantity production, or commercial publication.

## Proposed V2 contracts

### VerifiedTakeoffItemV2

One independently verified takeoff line or normalized measurable item:
- item_id
- project_id
- description
- trade/category
- unit
- expected_quantity
- tolerance_policy_id
- expected_object_refs
- source_document_refs
- source_pages/sheets
- verification_status
- denominator_eligible

expected_object_refs identify the verified physical surface/object universe behind the takeoff item. They are evaluator-only references and are not production object IDs unless an independent reconciliation has already proven identity.

### ProjectBenchmarkManifestV2

- project_id
- source_documents with SHA-256 and role
- reference_takeoff documents with SHA-256 and role
- verified_takeoff_items
- status = VERIFIED | INCOMPLETE | NOT_CONFIGURED
- reason_codes

Only VERIFIED projects contribute to the headline denominator.

### Reconciliation states

For each verified takeoff item:
- MATCHED_WITHIN_TOLERANCE
- MATCHED_OUTSIDE_TOLERANCE
- MISSED
- PARTIAL
- UNRESOLVED
- UNSUPPORTED_EXTRA

Rules:
1. A numeric or textual look-alike is never sufficient for MATCHED.
2. MATCHED requires the evaluator to prove the required physical object/surface set is covered by the sealed PlanReader coverage/quantity output and that the quantity is within the independently frozen tolerance.
3. Missing required objects or missing quantity closure is MISSED or PARTIAL, never silently ignored.
4. Ambiguous identity is UNRESOLVED.
5. PlanReader quantities/rows with no verified counterpart are UNSUPPORTED_EXTRA and are separately penalized.
6. No expected value, item label or project name may alter extraction or object admission.

## Headline metrics

Primary:
Verified Takeoff Coverage Accuracy =
matched-within-tolerance denominator items / all denominator-eligible verified items.

Supporting:
- object/surface coverage percentage
- quantity-weighted absolute percentage error by compatible unit/family
- matched outside tolerance count
- missed count and explicit miss list
- partial count
- unresolved count
- unsupported-extra / hallucination count
- gross mismatch count
- runtime and completion status

The headline must fail closed to UNPUBLISHED when:
- any required project is NOT_CONFIGURED or INCOMPLETE;
- a required source/takeoff hash is missing or mismatched;
- extraction did not complete;
- expected takeoff universe is not independently verified;
- object/surface reconciliation is incomplete in a way that would make the numerator or denominator unknowable.

A four-project provisional development report may still be emitted, but it must be labeled PROVISIONAL_4_OF_5 and must not be represented as the final five-project headline.

## Expected abstentions

The evaluator must preserve upstream abstentions. It must not convert them into guessed matches.
Expected cases include:
- no admitted physical object for a required expected surface;
- admitted object with no explicit quantity link;
- quantity link with no TakeoffOutputRow;
- conflicting revision/source lineage;
- incomplete object or quantity universe;
- ambiguous expected-to-produced object reconciliation;
- non-geometric/preliminary/provisional takeoff items excluded from denominator by independent classification.

## Test plan

- exact surface/object closure positive;
- one missing expected surface => PARTIAL/MISSED;
- equal numeric value with wrong object identity => not matched;
- equal description with wrong lineage => not matched;
- extra PlanReader quantity => UNSUPPORTED_EXTRA;
- ambiguous expected-object reconciliation => UNRESOLVED;
- source/revision/hash conflict => fail closed;
- input-order invariance;
- deterministic replay;
- no mutation of coverage summary or takeoff rows;
- extractor results identical with expected V2 universe present or absent;
- four-of-five suite emits provisional only;
- fifth missing slot cannot be silently substituted by an old benchmark project.

## Benchmark observations that must not influence implementation

- Historical 60-row canonical accuracy values.
- Any known miss list from KSTVET/Murera/Ghazi/Lamu/Umma.
- Expected quantities from the new Australian projects.
- Desired 90% or 99% commercial targets.

Those facts may be reported only after a sealed extraction. They are never thresholds or prediction inputs.

## Proposed implementation split

PR A — this architecture report only.

PR B — benchmark-only contracts, evaluator, tests and source manifests for the new suite. No production code changes.

PR C and later — any production fixes discovered by V2 misses, each in separate production PRs with no benchmark-defining changes.

This preserves the repository’s benchmark-gold/production firewall and makes the V2 miss list diagnostically useful without turning benchmark truth into production authority.
