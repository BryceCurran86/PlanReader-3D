# Take-off coverage registry → audit renderer adapter architecture

## Observed repository behaviour

- `pb_takeoff_coverage_registry.py` on current main owns the read-only v1 coverage registry. Physical admission comes only from producer-owned object-universe snapshots bound by `CoverageRegistryRunManifestV1`.
- `CoverageObjectRecordV1` is the complete per-object coverage result. `ACCOUNTED` means only `EXPLICIT_DEPENDENCIES_ONLY`; `expected_family_completeness` is `UNKNOWN`.
- `pb_audit_coverage_record.py` defines the renderer-facing `CoverageRecordProvider` protocol and `AuditObjectRecord`.
- `pb_audit_render.py` consumes `CoverageRecordProvider.record_for(obj)` by exact scene object id and never writes take-off or physical authority.
- W10 canonical presence remains non-authoritative: `takeoff_eligible=False` and `deduction_authority=False`.

## Inference

The renderer interface can consume registry results without becoming a competing authority if the bridge performs only exact object-id lookup and copies already-computed registry state. A canonical scene object absent from the registry cannot be treated as an admitted physical object; therefore the adapter must fail closed rather than infer `UNACCOUNTED` from scene presence.

## Proposed change

1. Extend `AuditObjectRecord` with optional read-only semantic metadata:
   - `coverage_basis`
   - `expected_family_completeness`
   The existing default renderer provider leaves both unset.

2. Add `RegistryCoverageRecordProviderV1` in a separate adapter module.
   - Constructor accepts one `CoverageRegistrySummaryV1`.
   - Builds an immutable exact `object_id -> CoverageObjectRecordV1` index.
   - `record_for(obj)` reads only `obj["id"]`.
   - Exact registry match copies the registry state, reason code, source pages, provenance, takeoff row ids, and the two frozen semantic fields.
   - Renderer-only uncertainty may then lower an `ACCOUNTED` display state to `PARTIAL` or `ABSTAINED`; it never mutates the registry result and never upgrades any state.
   - Missing registry admission returns `ABSTAINED` with reason `not_in_registry_admitted_object_universe`.
   - Duplicate object ids fail at construction.
   - No label, description, value, geometry proximity, page, family, or benchmark matching.

3. Preserve semantic metadata in the renderer payload. Audit HUD text must make clear that registry `ACCOUNTED` means explicit dependencies only and expected-family completeness remains unknown.

## Authority boundaries

- Physical existence: unchanged; upstream producer snapshots only.
- Quantity linkage: unchanged; registry exact seams only.
- Commercial publication: unchanged; JobHub preflight and take-off rows are not mutated.
- Renderer: remains shadow/read-only and cannot raise coverage state.
- Canonical/W10: remains display/input surface only, not admission authority.

## Benchmark observations that must not influence implementation

No benchmark score, expected quantity, mapping, tolerance, project id, filename, or development drawing observation is used by this adapter.

## Required proof

- Exact registry object id maps state-for-state.
- Scene object absent from admitted registry universe becomes ABSTAINED, never ACCOUNTED/UNACCOUNTED by inference.
- coverage_basis and expected_family_completeness survive through AuditObjectRecord.to_dict() and build_audit_scene.
- Renderer downgrade for non-drawable ACCOUNTED objects preserves semantic metadata while lowering state to PARTIAL.
- Equal labels, equal values, same page, and nearby geometry cannot link.
- Input-order invariance and no mutation.
- W10 authority flags unchanged.
- No extractor, commercial row, JobHub preflight, benchmark, or gold changes.
