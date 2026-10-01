# Structural-member coverage universe snapshot v1 — architecture report

## Observed repository behaviour

- `StructuralMemberResolution` is the producer-owned result of `StructuralMemberProducer.publish()`.
- Only `EvidenceResolutionStatus.CORROBORATED` carries admitted `PhysicalStructuralMember` identities.
- Abstained/conflicting structural resolutions intentionally return no physical members and retain reason codes such as incomplete scope, ambiguous relation, registration incomplete, count conflict, or definition conflict.
- The merged coverage registry requires one `ProducerObjectUniverseSnapshotV1` for every manifest-expected producer/category key.
- Only `enumeration_status=COMPLETE` with an empty id tuple can mean proven zero objects. Missing/incomplete authority must never be represented as zero.
- The structural quantity adapter in parent PR #1145 projects the same producer-owned resolution into exact `QuantityEvidence.input_entity_ids`; it does not own physical admission.

## Inference

The structural producer needs a deterministic read-only coverage enumeration seam. The seam must consume the sealed structural result itself, never an arbitrary caller-supplied list of member ids.

A non-corroborated structural resolution does not prove zero physical members. It therefore maps to `INCOMPLETE`, not `COMPLETE` with an empty list.

## Proposed change

Add shadow-only `pb_structural_member_coverage_snapshot.py`:

`structural_member_resolution_to_coverage_snapshot(resolution, *, registry_run_id)`

### CORROBORATED + valid physical identities
Return `ProducerObjectUniverseSnapshotV1` with:
- producer = `structural_member`
- owning_authority = `StructuralMemberAuthority`
- category = normalized selector.member_kind
- source_document_id / revision_id / source_sha256 / snapshot_id copied exactly from selector
- registry_run_id supplied by the registry run
- admitted_object_ids = sorted exact `PhysicalStructuralMember.physical_member_id`
- enumeration_status = COMPLETE
- reason_codes = structural resolution reason codes

### Non-corroborated result
Return the same bound producer/category snapshot with:
- admitted_object_ids = ()
- enumeration_status = INCOMPLETE
- reason_codes = existing resolution reasons plus a fallback `structural_member_enumeration_incomplete`

This is never a zero-object claim.

### Malformed CORROBORATED result
Blank/duplicate physical member ids, member-kind mismatch, or zero published members map to:
- admitted_object_ids = ()
- enumeration_status = INCOMPLETE
- reason code `structural_member_enumeration_identity_invalid`

Invalid source lineage (empty document/revision/snapshot/category/run id or invalid SHA-256) fails construction rather than emitting an unbindable snapshot.

## Authority boundaries

- Physical existence and identity stay entirely in StructuralMemberAuthority.
- This adapter cannot accept arbitrary object ids and cannot create a PhysicalStructuralMember.
- Coverage registry remains a consumer only.
- Structural QuantityEvidence remains independent but should resolve to the same physical ids when both are built from the same resolution.
- Extractor, commercial rows, JobHub, W10 and benchmark files remain untouched.

## Required proof

- corroborated result -> COMPLETE exact ids;
- abstained/conflicting -> INCOMPLETE, never COMPLETE-empty;
- malformed corroborated identity -> INCOMPLETE;
- deterministic/input-order invariant;
- exact selector lineage copied;
- invalid run id/source lineage rejected;
- structural quantity ids and snapshot admitted ids agree exactly;
- combined registry run produces structural records with explicit quantity dependency but remains PARTIAL/DANGLING when TakeoffOutputRow is absent;
- no mutation;
- no live/non-test importer;
- benchmark separation and provider-gold isolation remain green.

## Benchmark firewall

No benchmark identifier, project name, expected quantity, mapping, tolerance, score, or golden value participates in structural enumeration.
