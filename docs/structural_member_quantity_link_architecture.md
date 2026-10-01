# Structural-member quantity linkage v1 — architecture report

## Observed repository behaviour

1. `StructuralMemberProducer.publish()` in `pb_structural_member_authority.py` is the physical-member authority. It returns `CORROBORATED` only after definition consistency, complete view scope, relation conflict checks, cross-view registration, and per-view count consistency. Only then does it expose stable `PhysicalStructuralMember.physical_member_id` records and `StructuralMemberResolution.quantity == len(members)`.

2. `build_structural_member_registration_authority()` in `pb_structural_member_registration_producer.py` converts authenticated source-owned observations/views into that producer-sealed resolution. It does not emit `QuantityEvidence`.

3. `build_secondary_support_structural_member_authority()` in `pb_secondary_support_structural_member_adapter.py` is already called live by `GenericPlanReaderExtractor` for source-proven verandah support symbols. It publishes physical identities only when physical-symbol evidence is complete and consistent.

4. `GenericPlanReaderExtractor.extract_from_pdf()` already consumes a corroborated structural resolution to publish `verandah_pillars`. It explicitly suppresses raw pier/pillar text and structural schedule rows because those are evidence only and must not mint physical members.

5. `QuantityEvidence` is the repository-wide quantity trace contract. The generic opening-count authority provides the relevant count precedent: one aggregate count quantity whose `input_entity_ids` are all authenticated physical instance ids.

6. The merged take-off coverage registry joins objects to quantities only through exact `QuantityEvidence.input_entity_ids` or editable dependency ids. Structural members currently lack the former seam, so a valid structural count can exist while the registry still reports structural objects unaccounted/orphaned.

## Inference

The missing capability is not another structural detector or counter. It is a deterministic adapter from an already-resolved `StructuralMemberResolution` into the existing `QuantityEvidence` contract.

The adapter must not consume text counts, schedules, canonical/W10 objects, or arbitrary caller-supplied member ids. It may consume only the producer-owned resolution and its selector/member lineage.

## Proposed change

Add a shadow/read-only `pb_structural_member_quantity.py` with:

`build_structural_member_count_quantity(resolution: StructuralMemberResolution) -> QuantityEvidence`

### CORROBORATED resolution

Emit exactly one aggregate `QuantityEvidence`:

- `family = "structural_member_count"`
- `semantic_key = "structural_member_count:<member_kind>:<decision_scope_id>"`
- `value = float(len(resolution.members))`
- `unit = "NO"`
- `input_entity_ids = tuple(sorted(member.physical_member_id ...))`
- `evidence_ids = ordered union of every member.source_evidence_ids`
- `formula = "count_of_authenticated_physical_structural_members"`
- `formula_version = STRUCTURAL_MEMBER_SCHEMA_VERSION`
- `authority = MeasurementAuthorityType.MODEL_DERIVED.value`
- `status = AuthorityStatus.FIRM.value`
- `confidence = 1.0`
- metadata copies selector lineage:
  - document_id
  - revision_id
  - source_sha256
  - snapshot_id
  - decision_scope_id
  - member_kind
  - physical_member_ids
  - resolution reason codes
- quantity id uses `stable_contract_id` over the exact lineage, member kind, decision scope and physical member ids.

No schedule/text value participates in the count or identity.

### Non-CORROBORATED resolution

Emit an abstained `QuantityEvidence`:
- same family/semantic key and selector lineage;
- `value=None`;
- `input_entity_ids=()` because blocked resolutions publish no physical members;
- `status=AuthorityStatus.BLOCKED.value`;
- `abstained=True`;
- `blocking_reasons = resolution.reason_codes` (or a structural-resolution-not-corroborated fallback);
- no inferred count.

This retains a typed downstream refusal without manufacturing object links.

## Why aggregate rather than one quantity per member

The existing generic opening-count authority uses one aggregate count quantity linked to every authenticated physical instance. Structural count should follow the same contract. The coverage registry may therefore know that each admitted structural object participates in the count while leaving per-object numeric contribution unknown for the aggregate.

## Authority boundaries

- Physical existence: unchanged, owned by `StructuralMemberProducer`.
- Cross-view identity/completeness: unchanged.
- Quantity value: deterministic projection of the producer-owned physical member set only.
- Extractor: unchanged in this shadow PR.
- TakeoffOutputRow/commercial publication: unchanged.
- JobHub preflight: unchanged.
- Coverage registry: unchanged; it merely gains an exact input-entity seam when callers enumerate this quantity.
- W10/canonical: untouched.

## Expected abstentions

- incomplete view scope;
- ambiguous or conflicting relations;
- incomplete cross-view registration;
- count conflict;
- definition conflict;
- no source-backed member observations.

All produce abstained quantity evidence and no physical object link.

## Required proof

- corroborated single-view and cross-view resolutions produce exact aggregate count and exact physical ids;
- quantity id deterministic/input-order invariant;
- evidence union deterministic;
- non-corroborated statuses produce abstained/no numeric value/no input ids;
- text/schedule count look-alikes cannot affect quantity;
- duplicate/cross-view physical observations do not inflate count after structural authority reconciliation;
- registry integration sees exact structural object→quantity links;
- without a TakeoffOutputRow the object is PARTIAL and reverse census DANGLING, not falsely ACCOUNTED;
- no input mutation;
- live extractor predictions unchanged because no live import/wiring is added;
- W10 flags, commercial rows, JobHub preflight, benchmark files unchanged.

## Benchmark firewall

No benchmark id, filename, expected quantity, scoring rule, mapping, tolerance, or development-set result is an input to this adapter.
