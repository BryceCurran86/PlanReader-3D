# Structural coverage extractor shadow v1 — architecture report

## Observed repository behaviour

- `GenericPlanReaderExtractor.extract_from_pdf()` already resolves verandah physical supports through `build_secondary_support_structural_member_authority(...).resolution`.
- The existing live `verandah_pillars` prediction is emitted only when that structural resolution is CORROBORATED.
- Extractor diagnostics use explicit shadow payloads initialized in `__init__`, reset at the start of each document, and populated independently of commercial predictions (opening provenance/authority, hosted openings, roof covering, net wall).
- Parent PR #1145 adds deterministic structural `QuantityEvidence` from the same `StructuralMemberResolution`.
- Parent PR #1146 adds deterministic `ProducerObjectUniverseSnapshotV1` from the same resolution.
- Neither parent changes extractor behavior.

## Inference

The safest first live consumer is diagnostic only: expose both structural coverage records on the extractor instance after the producer-owned resolution already exists.

The shadow collector must be observational. Failure to build or serialize coverage diagnostics must never suppress or alter the existing `verandah_pillars` prediction.

## Proposed change

### New module: pb_structural_member_coverage_shadow.py

Provide:

- `empty_structural_member_coverage_shadow(reason="not_collected")`
- `collect_structural_member_coverage_shadow(resolution, *, registry_run_id)`

The collector accepts only a `StructuralMemberResolution`.

It calls:
- `structural_member_resolution_to_coverage_snapshot`
- `build_structural_member_count_quantity`

and returns a JSON-safe dict containing:
- structural resolution status/reason codes;
- registry_run_id;
- exact producer object-universe snapshot;
- exact structural QuantityEvidence;
- exact physical member ids;
- quantity id.

No TakeoffOutputRow is created.

### Extractor changes

1. Initialize `self.structural_member_coverage_shadow` to explicit not-collected abstention.
2. Reset it at the start of every `extract_from_pdf()`.
3. Immediately after the existing `structural_support` resolution is produced, attempt shadow collection inside its own `try/except`.
   - registry_run_id is deterministic and source-bound: `extractor-structural:<source_sha256>`.
   - on any collector failure, store `shadow_collection_failed`.
   - then continue into the existing live prediction block unchanged.

The new shadow code never writes `pred_dict`, never changes `structural_support`, and never changes the condition that publishes `verandah_pillars`.

## Authority boundaries

- Structural physical existence/identity: StructuralMemberAuthority only.
- Quantity trace: deterministic projection of that resolution only.
- Coverage object enumeration: deterministic projection of that resolution only.
- Commercial prediction: pre-existing extractor logic unchanged.
- TakeoffOutputRow/JobHub: not used.
- Coverage registry summary: not built yet.
- W10/canonical: untouched.
- Benchmark data: untouched.

## Expected shadow states

- Complete physical support row -> CORROBORATED shadow, COMPLETE object snapshot, firm structural count QuantityEvidence.
- Text/specification-only or structurally incomplete evidence -> non-corroborated shadow, INCOMPLETE object snapshot, abstained quantity evidence.
- No resolved secondary support -> not_collected shadow.
- Collector exception -> abstained shadow with shadow_collection_failed, while live extraction continues normally.

## Required proof

- constructor default and per-document reset;
- complete synthetic verandah source yields the same four physical ids in:
  - live prediction metadata,
  - producer object snapshot,
  - QuantityEvidence.input_entity_ids;
- quantity remains 4 and live prediction is byte/value-equivalent with shadow collector enabled or forced to fail;
- text-only structural evidence cannot become COMPLETE or firm quantity;
- shadow collector failure cannot change live predictions;
- no TakeoffOutputRow/JobHub call;
- no benchmark/gold dependency;
- provider gold isolation, benchmark separation and extractor mutation tests green.

## Benchmark firewall

No benchmark id, expected value, mapping, tolerance, scorer output, project name, or golden quantity is read by the shadow collector.


## Self-review hardening

The collector headline can never remain CORROBORATED when either downstream
projection rejects the resolution. An incomplete object snapshot or abstained
quantity downgrades that diagnostic headline to ABSTAINED; original producer
status is not mutated. Producer reasons, snapshot reasons and quantity blocking
reasons remain visible together.

Validation includes malformed identities, invalid enum status, invalid run/source
lineage, deterministic JSON replay, no input mutation and full prediction-dict
parity between a successful collector and a forced collector failure.

Review is performed autonomously under Bryce's instruction to review this work
and continue without stopping. This approval covers diagnostic consumption only;
commercial TakeoffOutputRow/JobHub promotion is still a separate boundary.


## AG09 secondary-area coverage trace hardening

Coverage collection is intentionally broader than commercial publication. Explicit
secondary-area labels `ALFRESCO`, `PORCH`, and `PATIO` may now activate the same
producer-owned structural resolution and coverage trace when the existing
geometry/evidence gates pass. This does not create a new customer quantity tag.

`verandah_pillars` remains publishable only for canonical `verandah` evidence.
For other admitted secondary-area names the extractor may populate the shadow
object universe, structural QuantityEvidence, and coverage registry summary,
while leaving `pred_dict` unchanged. This closes the diagnostic blind spot
identified during real-source review without promoting a synonym into commercial
authority.
