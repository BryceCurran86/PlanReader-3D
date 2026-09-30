# Take-off Coverage Registry - Architecture Review v1

Status: architecture-only review gate. No production implementation in this change.

## Scope

Build a derived, read-only registry for already-proven physical objects.
For each admitted object, report exact take-off quantity links, output-row links, and downstream authority/publication state.

Required coverage states: ACCOUNTED, PARTIAL, UNACCOUNTED, ABSTAINED.

The registry must preserve proven objects when editable registration, quantity links, or rows are missing.
It must never create a physical object, infer a missing link, raise measurement authority, approve a row, or alter extraction/publication.

## Observed repository behaviour

### Physical existence is upstream authority

pb_wall_room_topology_canonical_adapter._adapt_wall and adapt_topology_to_canonical_level copy topology into canonical objects while forcing takeoff_eligible=False and deduction_authority=False.
Therefore W10 canonical presence alone is not physical-existence authority.

pb_physical_wall_existence_authority.resolve_physical_wall_existence only reaches CORROBORATED after current source/revision ownership and independent-domain evidence are proven.
Candidate, conflict, and abstained wall existence must not be admitted.

pb_physical_opening_authority.PhysicalOpeningAuthority owns physical opening existence.
Unresolved opening existence must remain unresolved.

pb_structural_member_authority.StructuralMemberProducer.publish emits stable PhysicalStructuralMember ids only from a CORROBORATED resolution.
pb_canonical_building.CanonicalEvidenceObservation is explicitly evidence-only and carries no_instance_creation=True.
Those records must never become coverage objects.

### Editable registration is not the object universe

EditableGeometryObject already carries source trace, geometry_ref, revision_hash and dependent_quantity_ids.
Editable3DCorrectionLedger.link_dependent_quantities is an exact additive object-id to quantity-id link.

But pb_editable_3d_workspace_hydration documents that model_masses/model_openings have no foreign key to takeoff_rows, so hydrated objects start with empty dependent_quantity_ids.
pb_editable_3d_inspector_panel also registers hydrated walls only.
Starting the registry from the editable ledger would therefore omit real interpreted objects.

### QuantityEvidence is the strongest generic object-to-quantity seam

QuantityEvidence carries quantity_id, input_entity_ids, evidence ids, status, authority, abstention and blocking reasons.
Existing wall length, wall gross area, wall net area, room area and generic opening-count producers already place exact physical object ids in input_entity_ids.

Not every producer does.
pb_source_roof_covering_authority currently emits QuantityEvidence without input_entity_ids.
Structural-member quantity is also not exposed through the same generic QuantityEvidence object-link path.
Those gaps must remain visible; the registry must not guess links.

### TakeoffOutputRow is downstream state

TakeoffOutputRow carries exact quantity_id plus optional geometry_ref, revision_hash, authority_status, is_publishable and blocking_reasons.
pb_planreader_jobhub_publish_contract.run_jobhub_publish_preflight remains the commercial gate.
The registry may report these fields but must not reproduce, weaken or mutate that gate.
### Correction matching is not a discovery rule

pb_editable_3d_quantity_recalculation creates exact corrected rows with geometry_ref=object_id and can add their ids to dependent_quantity_ids.
Its description-keyword matching is local to pairing a known correction row with a known recalculation target.
It must never be reused to discover object-to-takeoff coverage.

## Inferences

1. Registry admission must come from the owning physical-existence authority; the registry cannot decide existence.
2. The registry is a left join: missing downstream data is a visible result, not a reason to drop the upstream object.
3. Exact input_entity_ids, dependent_quantity_ids, quantity_id and non-conflicting geometry/revision lineage are valid seams.
4. Labels, descriptions, equal values, nearest geometry, page-only coincidence, first/best candidates and benchmark values are invalid seams.
5. Publication authority is orthogonal to coverage. A row may account for an object while still awaiting estimator approval.

## Proposed architecture

### 1. Admission

Accept only caller-supplied, producer-proven physical objects.

Wall: existing physical-wall existence must be CORROBORATED.
Opening: existing physical-opening authority must prove PHYSICAL_OPENING_EXISTS.
Structural member: PhysicalStructuralMember must come from a CORROBORATED StructuralMemberResolution.
Legacy production objects: owning producer must already have established physical instance identity.
CanonicalEvidenceObservation.no_instance_creation=True: never admit.
W10 candidate copied to CanonicalWall: never admit solely because it is canonical.

No second physical identity is minted; registry key is the existing authoritative object id.
### 2. Exact left joins

For each admitted object:

1. Object -> editable registration:
   exact object identity only; any source/revision/geometry conflict invalidates that join; absence preserves the object.

2. Object -> QuantityEvidence:
   exact membership in input_entity_ids only; abstained evidence remains visible; duplicate/conflicting quantity ids fail closed.

3. Editable object -> dependent quantity ids:
   consume ids exactly as written; dangling ids remain visible; they supplement but never override QuantityEvidence conflicts.

4. Quantity id -> TakeoffOutputRow:
   exact quantity_id equality only.
   If geometry_ref is present it must not contradict object identity/geometry lineage.
   If both revisions are known they must agree.
   Shared source lineage must not conflict.
   Stale/superseded mismatch is a defect, never a fallback-search trigger.

5. Output row -> commercial state:
   report existing authority_status, is_publishable, blocking_reasons, revision and approval only.
   Never call approval and never rewrite JobHub preflight.

### 3. Coverage semantics

ACCOUNTED:
At least one explicit dependency/link exists and every explicit linked quantity id resolves to a current lineage-compatible TakeoffOutputRow.
Commercial publishability is reported separately and does not by itself demote coverage.

PARTIAL:
At least one downstream link exists, but one or more explicit dependencies are dangling, conflicting, stale, lineage-incompatible or unresolved while another resolves.
UNACCOUNTED:
The proven physical object has no explicit object-to-quantity relationship in QuantityEvidence.input_entity_ids or validated editable dependent_quantity_ids.

ABSTAINED:
The physical object exists, downstream QuantityEvidence explicitly abstains/refuses for that object, and no resolved non-abstained row accounts for it.

Unresolved physical existence creates no registry object at all.
This prevents the coverage layer from minting geometry by implication.

### 4. Expected quantity families are out of v1

There is no current central contract saying every wall must always emit a fixed family set such as length + gross + net + finish.
V1 measures completeness only over dependencies explicitly emitted by existing producers.
A universal expected-family matrix requires a separate authority review.

### 5. Audit renderer integration

PR #1137 defines CoverageRecordProvider and the same four states.
Once that interface is on the target branch, add only a thin read-only adapter using exact scene object id lookup.
The renderer must never become the source of object-to-row linkage.
No viewport/title work is part of this task.

## Synthetic proof required

Tests must prove exact positive joins; survival without editable registration; survival with empty dependency list; exact input_entity_ids without editable registration; abstained quantity handling; dangling/mixed links; geometry and revision conflicts; duplicate/conflicting ids; input-order invariance; no mutation; and evidence-only records excluded.
Adversarial tests must prove equal labels, equal values, nearest geometry and page coincidence cannot create links.
W10 authority flags, commercial rows and JobHub preflight results must remain unchanged.
## Benchmark firewall

The current 3LAUREL all-unlinked audit observation is only a symptom of missing lineage.
It must not determine admission thresholds, expected families, matching heuristics, coverage thresholds, scoring, tolerances, denominator, gold or mappings.
No benchmark-defining file is read or changed by this design.

## Files/functions traced

AGENTS.md; docs/AI_ENGINEERING_PLAYBOOK.md.
pb_canonical_building.py; pb_wall_room_topology_canonical_adapter.py.
pb_physical_wall_existence_authority.resolve_physical_wall_existence.
pb_physical_opening_authority.PhysicalOpeningAuthority.
pb_structural_member_authority.StructuralMemberProducer.publish.
pb_editable_3d_correction_model.py; pb_editable_3d_workspace_hydration.py; pb_editable_3d_model_bridge.py.
pb_editable_3d_inspector_panel.py; pb_editable_3d_quantity_recalculation.py.
pb_migration_contracts.QuantityEvidence and wall/room/opening/roof quantity producers.
pb_takeoff_output_authority.TakeoffOutputRow.
pb_quantity_takeoff_adapter.quantity_evidence_to_takeoff_output_row.
pb_planreader_jobhub_publish_contract.run_jobhub_publish_preflight.
PR #1137 provider contract reviewed only, not modified.

## Files that remain untouched

pb_planreader_pdf_extractor.py; viewport/title code; live opening deduction/publication authorities; JobHub publish contract; commercial writers; W10 authority defaults; benchmarks/**; benchmark gold; expected quantities; scorer; mappings; tolerances; denominator; acceptance rules.

## Architecture review stop

After approval: add one shadow/read-only registry module; accept only producer-proven objects; perform exact left joins; add adversarial/no-mutation tests; integrate PR #1137 provider only when available; then run a gold-free shadow census and authority review before any live consumer.

No production code should be written until this admission/linkage/state contract is approved.
