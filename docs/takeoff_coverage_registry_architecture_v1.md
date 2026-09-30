# Take-off Coverage Registry - Architecture Review v1

Status: architecture-only review gate. No production implementation in this change.

## Scope

Build a derived, read-only registry for already-proven physical objects.
For each admitted object, report exact take-off quantity links, output-row links, and downstream authority/publication state.

Required coverage states: ACCOUNTED, PARTIAL, UNACCOUNTED, ABSTAINED.

The registry must preserve proven objects when editable registration, quantity links, or rows are missing.
It must also preserve producer/category enumeration status so an unavailable or incomplete producer is visible instead of being misread as a zero-object category.
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
2. The authoritative object universe must be enumerated through producer-owned snapshots, not an arbitrary caller-supplied list. Missing/incomplete enumeration is a first-class registry summary state and never means zero objects.
3. The registry is a left join: missing downstream data is a visible result, not a reason to drop the upstream object.
4. Exact input_entity_ids, dependent_quantity_ids, quantity_id and non-conflicting geometry/revision lineage are valid seams.
5. The audit is bidirectional: every in-scope QuantityEvidence and TakeoffOutputRow must also be anti-joined back to admitted physical objects so dangling/orphan/conflicting quantities remain visible.
6. Labels, descriptions, equal values, nearest geometry, page-only coincidence, first/best candidates and benchmark values are invalid seams.
7. Publication authority is orthogonal to coverage. A row may account for an object while still awaiting estimator approval.
8. ACCOUNTED in v1 means only that all explicit dependencies known to v1 resolve. It does not assert that every quantity family that ought to exist is present.

## Proposed architecture

### 1. Admission

Accept only physical objects enumerated as admitted by producer-owned authority snapshots. The registry does not accept an arbitrary caller-supplied list as an authoritative universe.

Wall: existing physical-wall existence must be CORROBORATED.
Opening: existing physical-opening authority must prove PHYSICAL_OPENING_EXISTS.
Structural member: PhysicalStructuralMember must come from a CORROBORATED StructuralMemberResolution.
Legacy production objects: owning producer must already have established physical instance identity.
CanonicalEvidenceObservation.no_instance_creation=True: never admit.
W10 candidate copied to CanonicalWall: never admit solely because it is canonical.

No second physical identity is minted; registry key is the existing authoritative object id.

### 1A. Producer-owned object-universe snapshots

The registry must not accept an unqualified list of objects as proof of universe completeness.
Each participating producer/category supplies an immutable enumeration snapshot owned by that producer/authority with these fields:

- producer / owning authority;
- source_document_id;
- revision_id;
- source_sha256;
- snapshot_id;
- authoritative admitted object_ids;
- enumeration_status;
- reason_codes.

The enumeration_status contract is typed and must distinguish at minimum COMPLETE, INCOMPLETE, UNAVAILABLE, and NOT_ENUMERATED.
Only the owning producer decides which object ids are physically admitted; the coverage registry merely consumes that snapshot.
A COMPLETE snapshot with zero admitted ids may establish a zero-object category for that exact source/revision/snapshot.
INCOMPLETE, UNAVAILABLE, or NOT_ENUMERATED must appear explicitly in the registry summary and must never be interpreted as zero objects.

A registry run is therefore bound to the producer snapshot identities it consumed. Conflicting document/revision/source SHA/snapshot lineage across producer snapshots is reported and must not be silently merged.

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

### 2A. Reverse orphan / unbound quantity census

The registry must also enumerate the complete in-scope downstream quantity universe for the same bound source/revision/snapshot run:

- every in-scope QuantityEvidence.quantity_id;
- every in-scope TakeoffOutputRow.quantity_id.

Using only the exact linkage seams approved above, anti-join those quantities against admitted physical object ids and classify them separately as:

- LINKED_QUANTITY: exact admitted-object linkage resolves without lineage conflict;
- DANGLING_QUANTITY: an explicit object/dependency reference exists but its target or downstream row is missing;
- ORPHAN_UNBOUND_QUANTITY: the quantity/row is in scope but exposes no approved exact object-link seam;
- CONFLICTING_LINEAGE_QUANTITY: an exact candidate link exists but document/revision/source SHA/snapshot/geometry lineage conflicts.

The census must never repair an orphan by label, value, page, geometry proximity, quantity family, or project knowledge.
Roof-covering QuantityEvidence that lacks input_entity_ids must therefore appear as ORPHAN_UNBOUND_QUANTITY until its owning producer exposes an approved exact link.
Structural-member publication that lacks the generic object-to-quantity seam must likewise remain explicitly unbound rather than being inferred.

The registry summary must report counts and ids for these four quantity-census states independently of object coverage-state counts.

### 3. Coverage semantics and frozen precedence

CoverageObjectRecordV1 classification is ordered and must apply the following precedence exactly:

1. **UNACCOUNTED** - no explicit object-to-quantity relationship exists in the approved v1 seams.
2. **ABSTAINED** - one or more explicit downstream abstention/refusal records exist, every explicit dependency is an abstention/refusal, and no resolved non-abstained row accounts for the object.
3. **PARTIAL** - one or more explicit dependencies exist, the object is not classified by rule 2, and at least one explicit dependency is dangling, conflicting, stale, lineage-incompatible, unresolved, or abstained. A resolved dependency is not required for PARTIAL.
4. **ACCOUNTED** - one or more explicit dependencies exist and every explicit dependency known to v1 resolves lineage-cleanly.

The ordering is normative. In particular, zero explicit dependencies can never satisfy ACCOUNTED through vacuous all-resolved logic; rule 1 classifies that object UNACCOUNTED first.
An object with only explicit abstentions and no resolved non-abstained row is ABSTAINED, not PARTIAL.
An object with one or more explicit dependencies that are all dangling/unresolved is PARTIAL, because an explicit dependency is known but closure has not been achieved.
A mixed object with at least one resolved explicit dependency plus any abstained or otherwise defective explicit dependency is also PARTIAL.

ACCOUNTED means only explicit-dependency closure. It does NOT mean all quantity families that ought to exist for the object are present.
Commercial publishability is reported separately and does not by itself demote coverage.
Every v1 object record therefore carries coverage_basis=EXPLICIT_DEPENDENCIES_ONLY and expected_family_completeness=UNKNOWN.

Unresolved physical existence creates no registry object at all.
This prevents the coverage layer from minting geometry by implication.

### 4. Expected quantity families are out of v1

There is no current central contract saying every wall must always emit a fixed family set such as length + gross + net + finish.
V1 measures completeness only over dependencies explicitly emitted by existing producers.
Accordingly, coverage_basis is fixed to EXPLICIT_DEPENDENCIES_ONLY and expected_family_completeness is fixed to UNKNOWN in v1.
No consumer may reinterpret ACCOUNTED as full trade, BOQ, estimator, or expected-family completeness.
A universal expected-family matrix requires a separate authority review.

### 4A. Frozen v1 object record schema

The top-level CoverageObjectRecordV1 schema is frozen before implementation. Its exact fields are:

- object_id: str;
- object_type: str;
- producer: str;
- owning_authority: str;
- source_document_id: str;
- revision_id: str;
- source_sha256: str;
- source_pages: tuple[int, ...];
- evidence_ids: tuple[str, ...];
- geometry_ids: tuple[str, ...];
- parent_host_ids: tuple[str, ...];
- quantity_ids: tuple[str, ...];
- takeoff_row_ids: tuple[str, ...];
- coverage_state: ACCOUNTED | PARTIAL | UNACCOUNTED | ABSTAINED;
- reason_codes: tuple[str, ...];
- quantity_contribution: mapping[quantity_id, optional finite numeric value];
- unit: mapping[quantity_id, unit string];
- provenance: immutable mapping copied from existing producer/source lineage;
- coverage_basis: EXPLICIT_DEPENDENCIES_ONLY;
- expected_family_completeness: UNKNOWN.

quantity_contribution and unit are keyed by quantity_id because one physical object can legitimately contribute to heterogeneous quantity families such as metres, square metres and counts. Null contribution is permitted only where the existing quantity evidence abstains or has no numeric value; the registry never fabricates a replacement value.

No additional top-level fields may be added to v1 without another schema review. Nested provenance content may only reissue already-existing source/authority metadata and cannot create a second authority vocabulary.

### 4B. Frozen producer enumeration and summary contracts

ProducerObjectUniverseSnapshotV1 has exactly these fields:

- producer: str;
- owning_authority: str;
- category: str;
- source_document_id: str;
- revision_id: str;
- source_sha256: str;
- registry_run_id: str;
- snapshot_id: str;
- admitted_object_ids: tuple[str, ...];
- enumeration_status: COMPLETE | INCOMPLETE | UNAVAILABLE | NOT_ENUMERATED;
- reason_codes: tuple[str, ...].

CoverageRegistrySummaryV1 must report, at minimum and without collapsing categories:

- the CoverageRegistryRunManifestV1 identity for the run;
- every expected object producer/category key and its enumeration result;
- object counts and ids by coverage_state;
- producer/category enumeration_status and reason_codes;
- explicit identification of every INCOMPLETE, UNAVAILABLE and NOT_ENUMERATED producer/category;
- QuantityEvidence-universe enumeration status and reason codes for every expected producer/source key;
- TakeoffOutputRow-universe enumeration status and reason codes for every expected source/collection key;
- quantity census counts and ids by LINKED_QUANTITY, DANGLING_QUANTITY, ORPHAN_UNBOUND_QUANTITY and CONFLICTING_LINEAGE_QUANTITY;
- coverage_basis=EXPLICIT_DEPENDENCIES_ONLY;
- expected_family_completeness=UNKNOWN.

Only COMPLETE with an empty admitted_object_ids tuple may mean proven zero objects for that exact producer/category/source/revision/snapshot. No other empty or absent list has zero-object semantics.

### 4C. Frozen run-level expected-universe manifest

CoverageRegistryRunManifestV1 is mandatory for every registry run and has exactly these fields:

- source_document_id: str;
- revision_id: str;
- source_sha256: str;
- registry_run_id: str;
- snapshot_id: str;
- expected_object_universe_keys: tuple[(producer: str, category: str), ...];
- expected_quantity_evidence_universe_keys: tuple[(producer: str, source: str), ...];
- expected_takeoff_row_universe_keys: tuple[(source: str, collection: str), ...].

The three expected-key collections are the complete expected universe sets for that run, are duplicate-free, and are interpreted only inside the manifest's exact document/revision/source-SHA/run/snapshot lineage.
An expected universe cannot be inferred from whichever snapshots a caller happens to supply.
Any supplied object, QuantityEvidence, or TakeoffOutputRow universe key that is absent from its corresponding manifest expected set is an unexpected_universe_key contract conflict and fails the run closed rather than silently expanding the manifest.

For every expected object producer/category key, exactly one enumeration result must exist for the run. A producer-supplied ProducerObjectUniverseSnapshotV1 is used when present. If no snapshot is supplied for an expected key, the registry must synthesize a run-side enumeration result with enumeration_status=NOT_ENUMERATED and reason code expected_object_universe_snapshot_missing. The synthetic result reports absence only; it does not decide physical existence and must not impersonate a producer-owned snapshot.

COMPLETE may contain zero admitted object ids. INCOMPLETE and UNAVAILABLE remain visible. NOT_ENUMERATED remains visible. No missing expected producer/category may be silently omitted.

QuantityEvidenceUniverseSnapshotV1 has exactly these fields:

- producer: str;
- source: str;
- source_document_id: str;
- revision_id: str;
- source_sha256: str;
- registry_run_id: str;
- snapshot_id: str;
- quantity_ids: tuple[str, ...];
- enumeration_status: COMPLETE | INCOMPLETE | UNAVAILABLE | NOT_ENUMERATED;
- reason_codes: tuple[str, ...].

TakeoffOutputRowUniverseSnapshotV1 has exactly these fields:

- source: str;
- collection: str;
- source_document_id: str;
- revision_id: str;
- source_sha256: str;
- registry_run_id: str;
- snapshot_id: str;
- quantity_ids: tuple[str, ...];
- enumeration_status: COMPLETE | INCOMPLETE | UNAVAILABLE | NOT_ENUMERATED;
- reason_codes: tuple[str, ...].

For every expected QuantityEvidence producer/source key and every expected TakeoffOutputRow source/collection key, exactly one corresponding enumeration result must exist. Missing snapshots are synthesized as NOT_ENUMERATED with reason codes expected_quantity_evidence_universe_snapshot_missing or expected_takeoff_row_universe_snapshot_missing respectively.

A zero linked/dangling/orphan/conflicting quantity count is conclusive only for a COMPLETE relevant quantity universe. INCOMPLETE, UNAVAILABLE, or NOT_ENUMERATED must remain attached to the census so missing enumeration can never masquerade as zero orphan quantities or zero dangling rows.

Before any joins or classification, the registry must reject conflicting source_document_id, revision_id, source_sha256, registry_run_id, or snapshot_id lineage between CoverageRegistryRunManifestV1, every supplied ProducerObjectUniverseSnapshotV1, every QuantityEvidenceUniverseSnapshotV1, and every TakeoffOutputRowUniverseSnapshotV1. Such a conflict fails the run closed and is reported with reason codes; incompatible universes are never merged.

### 5. Audit renderer integration

PR #1137 defines CoverageRecordProvider and the same four states.
Once that interface is on the target branch, add only a thin read-only adapter using exact scene object id lookup.
The renderer must never become the source of object-to-row linkage.
The adapter must preserve coverage_basis=EXPLICIT_DEPENDENCIES_ONLY and expected_family_completeness=UNKNOWN in the audit record/payload and legend semantics.
A neutral ACCOUNTED colour means only that explicit dependencies known to v1 resolve; it must never be presented or labelled as proof of complete trade scope, complete BOQ scope, or all expected take-off families.
No viewport/title work is part of this task.

## Synthetic proof required

Tests must prove exact positive joins; survival without editable registration; survival with empty dependency list; exact input_entity_ids without editable registration; abstained quantity handling; dangling/mixed links; geometry and revision conflicts; duplicate/conflicting ids; input-order invariance; no mutation; and evidence-only records excluded.
They must prove producer enumeration semantics: COMPLETE-empty is the only zero-object proof, while INCOMPLETE, UNAVAILABLE and NOT_ENUMERATED remain explicit non-zero-claim summary states.
They must prove CoverageRegistryRunManifestV1 detects an entirely omitted expected object producer/category and reports NOT_ENUMERATED rather than zero objects.
They must prove omitted expected QuantityEvidence and TakeoffOutputRow universes become NOT_ENUMERATED with reason codes and cannot yield conclusive zero orphan/dangling counts.
They must prove document, revision, source SHA, registry run id, and snapshot id conflicts between manifest and any supplied universe fail the run closed before joins.
They must prove exactly one enumeration result per expected manifest key, reject duplicate supplied results for the same key, and fail closed on any supplied universe key absent from the manifest's complete expected sets.
They must prove the reverse quantity census classifies linked, dangling, orphan/unbound and conflicting-lineage quantities without inventing links, including roof-covering and structural-member generic-link gaps.
They must prove the frozen coverage precedence: zero explicit links -> UNACCOUNTED; abstentions only -> ABSTAINED; any remaining one-or-more explicit dependencies with at least one defective/dangling/unresolved/abstained dependency -> PARTIAL (including dangling-only); one-or-more all-clean explicit dependencies -> ACCOUNTED.
They must prove ACCOUNTED always retains coverage_basis=EXPLICIT_DEPENDENCIES_ONLY and expected_family_completeness=UNKNOWN through the renderer adapter.
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

After approval: add one shadow/read-only registry module; require CoverageRegistryRunManifestV1; consume producer-owned object-universe snapshots plus explicit QuantityEvidence/TakeoffOutputRow universe snapshots; synthesize NOT_ENUMERATED only for manifest-expected missing enumerations; enforce run-lineage conflicts before joins; perform exact left joins plus the reverse orphan/unbound quantity census; implement only the frozen v1 contracts and coverage precedence; add adversarial/no-mutation tests; integrate PR #1137 provider only when available while preserving explicit-dependency-only semantics; then run a gold-free shadow census and authority review before any live consumer.

No production code should be written until this admission/linkage/state contract is approved.
