# Opening -> Host Wall Binding Authority — post-completeness gate v2

Exact validator base: `36a1f49ad92f553102101f8a2bf1d01ee45b2f52`.

Historical attack source: PR #334 / `c1c1ad1a64e7c5c26ee85dc9455c31e4c0c8c0fc`.

This is architecture + validator work only. Production host binding is not implemented here.

## Current authority state

The governing main already contains separately reviewed authority for:

- physical opening existence;
- local physical opening identity;
- producer-bound figured opening width;
- PDF text integrity / native text render eligibility; and
- producer-owned opening-universe completeness.

Those propositions do not prove a host wall. `PhysicalOpeningAuthority.capabilities()` still keeps `host_identity`, `host_binding`, `physical_void`, and `net_wall_area` false.

The historical #334 validator predates the merged dimension and completeness modules, so its assertion that those modules are absent is obsolete. Its host-binding attacks remain valuable and are refreshed here without reopening those upstream propositions.

## Authority separation

The required separation is:

`opening existence != opening identity != opening dimensions != opening-universe completeness != host nomination != host identity != host binding != physical void != deduction/net wall != commercial publication`.

A unique host must never be established by any of the following alone:

- nearest wall;
- first/smallest wall candidate id;
- bbox/footprint overlap;
- local containment;
- caller-supplied wall id;
- caller-supplied #323 path fingerprint;
- candidate count;
- radius-limited search;
- a local/cropped wall list claiming completeness;
- coincident wall geometry with unresolved provenance;
- opening width or height;
- opening-universe completeness (which is a different universe proposition); or
- a caller-authored `hosted` status.

## Reuse existing wall identity

Do not create a second wall fingerprint or physical-equivalence system.

Host production must reuse the existing wall identity stack:

- `canonical_path_fingerprint` for path normalization;
- `resolve_physical_wall_identity` to recompute producer-side candidate identity from wall geometry + lineage; and
- existing fail-closed physical-equivalence semantics for duplicate/coincident paths.

Equal geometry with different provenance is not automatically one physical wall. Different candidate IDs are likewise not automatically distinct physical walls.

## Producer/query boundary

Expected production shape is a structural in-process writer/query boundary, consistent with the already merged completeness authority:

- trusted writer: `OpeningHostBindingProducer`;
- read-only query: `OpeningHostBindingAuthority`;
- ordinary selector: `OpeningHostBindingSelector`;
- consumer call: `producer.authority().resolve(selector)`.

The selector contains lineage/scope and the upstream producer-owned opening record identifier only. It must not contain walls, geometry, candidate lists, host IDs, fingerprints, completeness claims, counts, radii, or opening spans.

The writer owns the exact host decision scope and must fail closed if source/host enumeration is incomplete, truncated, viewport-local, stale, mismatched, or ambiguous.

The v2 validator uses synthetic data at the writer boundary. This does not make those objects ordinary caller authority: the test explicitly verifies that the read-only resolver accepts only the selector. A production integration must bind the writer to the real producer-owned opening and wall/topology state rather than expose writer capability to downstream consumers.

## Required behavior

A positive bind is permitted only when the exact producer-owned decision scope is complete and exactly one physical wall remains after wall-identity/equivalence reconciliation and structural host geometry.

Fail closed on:

- multiple plausible physical walls;
- multi-wythe/cavity ambiguity without assembly identity;
- same path with unresolved provenance;
- nearby wall substitutions;
- incomplete/truncated host universe;
- local viewport/crop laundering;
- document/revision/source/snapshot/scope mismatch; and
- caller attempts to inject host identity, fingerprints, or completeness.

Structural equivalence must be deterministic under candidate order, path direction reversal, collinear segmentation, translation, and rotation.

## Downstream firewall

Even a CORROBORATED host bind authorizes only the host proposition. It must not by itself establish:

- opening physical void;
- opening deduction area;
- net wall area;
- FIRM/commercial quantity publication; or
- JobHub publication.

Those remain separate future gates.

## Benchmark policy

No benchmark/gold/scorer/mapping/tolerance/denominator/holdout file is changed by this validator. No score gain is claimed. Controlled development baseline remains `31/61 = 50.82%` until a canonical rerun proves otherwise.

Keep the validator PR DRAFT / TEST-ONLY / DO NOT MERGE. Production remediation must be a separate PR and must replay the exact frozen validator unchanged.
