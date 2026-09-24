# Item 19B — source-owned wall-finish / physical-face binding architecture report

Status: architecture report only; no live quantity promotion  
Baseline main: `fc57bcdcc53bd7da0823a314eaea7df7b3f76d2b`  
Scope: SOURCE FINISH EVIDENCE → EXACT PHYSICAL WALL / SEMANTIC PHYSICAL FACE SCOPE

## Compliance trace

Files/functions read and traced:

- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `docs/wall_topology_observability_architecture.md`
- `docs/planreader_wall_room_topology_spec.md`
- `docs/planreader_public_tender_benchmarks.md`
- `.github/workflows/ci.yml`
- `pb_wall_finish_propagation_authority.py`
  - `WallFinishPropagationProducer.publish`
  - `WallFinishPropagationProducer.publish_scope_summary`
- `pb_physical_wall_candidate_authority.py`
  - producer-owned wall scope and `PhysicalWallCandidateRecord`
- `pb_net_wall_boolean_union_authority.py`
  - `NetWallBooleanUnionProducer.publish`
- `pb_source_wall_topology_authority.py`
  - `build_source_wall_topology_authority`
- `pb_source_room_face_authority.py`
  - `build_source_room_face_authority`
- `pb_wall_role_authority.py`
  - `WallRoleProducer.from_source_topology`
  - `WallRoleProducer.publish`
- `pb_wall_thickness_face_authority.py`
  - `WallThicknessFaceProducer.publish`
- `pb_cross_sheet_registration_authority.py`
  - `CrossSheetRegistrationProducer.publish`
- `pb_surface_evidence_v160.py`
  - `associate_surface_to_target`
  - `associate_with_measured_surfaces`
- `pb_planreader_pdf_extractor.py`
  - `_has_internal_plaster_finish`
  - legacy internal finish emission around `internal_plaster` / `internal_paint`
  - external-key-pointing fail-closed diagnostic
- relevant finish / room-face / wall-face tests, including:
  - `tests/test_wall_finish_propagation_authority_v2.py`
  - `tests/test_source_room_face_authority_v1.py`
  - `tests/test_wall_thickness_face_authority_v1.py`
  - `tests/test_ghazi_wall_finish_recovery_authority_v1.py`
  - `tests/geometry/test_finish_tags_and_schedules.py`

Authority boundaries crossed by a future positive Item 19B result:

1. immutable source visibility / provenance
2. trusted finish annotation semantics
3. native annotation-to-leader connectivity
4. native leader-to-terminator connectivity
5. exact terminator-to-physical-wall ownership
6. semantic physical-face role resolution
7. finish-scope completeness / conflict resolution

Files deliberately untouched by this report:

- `pb_wall_finish_propagation_authority.py`
- PR #858 files / net-wall publication
- benchmark expected quantities, mappings, tolerances and scorer
- live plaster / paint / key-pointing publication
- JobHub / commercial output

## OBSERVED

### 1. Item 19A deliberately stops at the correct boundary

`WallFinishPropagationProducer.publish()` verifies:

- a caller request exists for the wall/trade
- the producer-owned physical-wall scope is CORROBORATED
- the exact physical wall exists in that scope
- the producer-owned net-wall record is CORROBORATED
- lineage matches document/revision/source SHA/snapshot/page/scope/wall/trade

It then intentionally returns:

`WALL_FINISH_BINDING_UNAVAILABLE`

because `WallFinishAssignment` is caller-provided diagnostic/request data. Its material, trade and `left_face/right_face/both_faces` values cannot prove source finish ownership.

This is the correct seam for Item 19B. Item 19B should create an upstream source-owned finish/face authority, not weaken Item 19A.

### 2. Existing wall identity and topology seams are sufficient inputs; do not create a second wall graph

`PhysicalWallCandidateRecord` preserves:

- exact wall candidate identity
- `WallCandidate.centerline_pts`
- `face_a_segment_ids`
- `face_b_segment_ids`
- physical identity
- immutable scope lineage

`build_source_wall_topology_authority()` derives source-owned wall/envelope topology from complete CORROBORATED physical-wall scopes and can establish exact external-vs-internal wall role where topology is sufficient.

`build_source_room_face_authority()` derives bounded room faces and exact `bounding_wall_ids` from the same producer-owned wall authority.

These are the correct identity/topology inputs for Item 19B.

### 3. Existing face geometry is not, by itself, finish-face authority

`WallThicknessFaceAuthority` defines stable `face_left_wkb_hex` and `face_right_wkb_hex`, but Item 19B must not equate left/right with interior/exterior.

The new binding should therefore store a semantic physical-face role such as:

- exterior face of exact external physical wall
- room-facing face of exact physical wall / exact room face
- opposite-room face of exact shared wall

Only a later deterministic orientation bridge may translate a semantic face to left/right geometry.

### 4. Existing surface-evidence code is not sufficient for positive Item 19B authority

`pb_surface_evidence_v160.associate_surface_to_target()` deliberately permits majority overlap, centroid and proximity associations.

Those are useful diagnostics, but Item 19B must not use proximity/nearest-target logic to mint a source-owned wall-finish binding.

A positive direct-callout path must instead require actual native connectivity.

### 5. Legacy extractor behavior proves why Item 19B is needed

`GenericPlanReaderExtractor._has_internal_plaster_finish()` currently recognizes page-wide phrases such as:

- `internal plaster`
- `plaster and paint`
- `finish internally`

The legacy internal-finish path can then emit `internal_plaster` and `internal_paint` from derived/proxy wall geometry.

By contrast, the external-key-pointing path now explicitly records only:

`evidence_present_unresolved`

because a page-wide phrase does not prove finish-face extent.

Item 19B should generalize the latter fail-closed principle and provide the missing positive source-owned binding seam.

## REAL-SOURCE EVIDENCE LEDGER

No benchmark expected quantity was used in this audit.

### KSTVET

Canonical source audited:

- SHA-256: `6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc`
- page 54

Observed finish wording includes repeated native callouts equivalent to:

- `150mm thick concrete walling blocks key to finish externally.`
- `150mm thick concrete walling blocks plaster and paint to finish internally.`

These are not merely page-wide keywords. At least the audited page-54 examples have native callout geometry.

#### Direct-callout audit example A — external finish

Native text block 123:

- text bbox approximately `x=699.9..807.3, y=464.1..496.3`
- wording: concrete walling blocks → key to finish externally

Native geometry shows:

- leader stroke seq 10069 from approximately `(662.1, 480.4)` to the text bbox edge at `(699.9, 480.4)`
- connector stroke seq 10066 from approximately `(651.9, 480.4)` to `(662.1, 480.4)`
- black circular terminator seq 10067/10068 centered approximately at `(648.1, 480.4)`
- wall-face/native wall band at approximately `x=645.3` and `x=650.9`

The leader is therefore source-connected to its own text and terminates inside the native wall assembly band.

This is strong evidence for a generic direct-callout producer.

#### Direct-callout audit example B — internal finish

Native text blocks 124/125:

- text bbox begins approximately at `x=111.4`
- wording: concrete walling blocks → plaster and paint → finish internally

Native geometry shows:

- leader stroke seq 10082 from the text edge at approximately `(218.3, 622.0)` to `(256.1, 622.0)`
- connector stroke seq 10079 from approximately `(256.1, 622.0)` to the terminator
- black circular terminator seq 10080/10081 centered approximately at `(270.1, 622.0)`
- native wall-face band at approximately `x=267.3` and `x=273.0`

Again the terminator is physically inside the wall assembly band, with no nearest-note selection needed.

#### KSTVET classification

Architecture viability: **YES for a direct-callout producer**.

Current real-source authority result should still be:

`FINISH_BINDING_SOURCE_PRESENT_GEOMETRY_PENDING`

until the callout terminator is resolved through the existing physical-wall authority to one exact `physical_wall_id` and the semantic face role is independently resolved.

The audit coordinates and sequence numbers above are diagnostics only. They must never become implementation constants.

### Lamu

Canonical source audited:

- SHA-256: `fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2`

The non-BOQ project description states:

`The floors are finished in cement sand screeds while the walls are plastered and painted.`

This is genuine non-quantity source wording and may establish that wall plaster/paint is part of the works.

However the audited drawing sheet does not provide a finish leader, room-finish schedule, finish tag, or face-specific annotation tying plaster/paint to exact physical wall faces.

The commercial finish bill also contains plaster/paint descriptions and quantities, but those commercial quantities are excluded from prediction authority.

Classification:

- source semantic scope exists
- exact physical-face scope is not proven
- **finish-face binding remains blocked**
- do not infer `both_faces`

This is a useful negative case for the general-specification path.

### Ghazi

Canonical source audited:

- SHA-256: `c8c001c9dadb791e7cb18b7bea19ce795eebba2f9b9eb7dec4844212da4d8f4f`

The supplied architectural drawing package contains only the floor-layout sheet (`Drawing No. 1 of 3`) and does not show wall-finish callouts or a room-finish schedule.

Internal plaster / plastic-paint wording appears in the commercial bill.

Classification:

- drawing/source finish-face evidence unavailable
- commercial BOQ wording must not establish geometry or exact face scope
- **source blocker; abstain**

Do not manufacture missing elevations or finish schedules.

## INFERENCE

### Item 19B is architecturally viable

KSTVET proves that a real public drawing can encode:

trusted finish annotation
→ native leader geometry
→ native terminator geometry
→ physical wall assembly

without nearest-note matching.

Therefore a generic source-owned direct-callout producer is justified.

### Positive wall binding and complete trade scope are separate propositions

A single valid callout may prove one exact wall + semantic face binding.

It does **not** prove that every physical face in the requested finish trade has been accounted for.

The authority must preserve partial positive evidence while keeping the trade scope incomplete.

### Semantic face role should precede left/right geometry

For KSTVET-style wording, `externally` and `internally` are semantic role evidence.

The record should bind:

exact physical wall + semantic face role

rather than prematurely writing caller-style `left_face` / `right_face`.

For an external wall with exact topology, `exterior_face` is one physical face and `interior_face` is the opposite face. For a shared internal wall, a room-facing face must be tied to an exact room/space identity; plain `internally` is not enough to choose one of two room-facing sides.

## PROPOSED AUTHORITY

Implement, in a later code change after review:

`pb_wall_finish_face_binding_authority.py`

Shadow-only first.

### Proposed input authorities

Required:

- immutable source bytes / source visibility authority
- producer-owned `PhysicalWallCandidateAuthority`

Optional depending on evidence kind:

- source-derived wall topology / `WallRoleAuthority`
- `SourceRoomFaceAuthority`
- `CrossSheetRegistrationAuthority` for elevation/section evidence only

Do not accept caller-supplied:

- physical wall geometry
- finish geometry
- face target
- wall role
- completeness flag
- benchmark/project identity

### Proposed source evidence kinds

1. `direct_wall_callout`
2. `room_finish_schedule`
3. `elevation_facade_callout`
4. `wall_type_finish_schedule`
5. `general_specification_scope`

Only source kinds with the required downstream ownership chain may create a CORROBORATED exact-face binding.

### Proposed record

Prefer a sealed producer-owned record with fields equivalent to:

- `binding_id`
- `document_id`
- `revision_id`
- `source_sha256`
- `snapshot_id`
- `page_id`
- `viewport_id`
- `decision_scope_id`
- `physical_wall_id`
- `physical_face_role`
- optional exact `room_face_id` / `room_id` when a room-facing side is required
- `trade_scope_id`
- `finish_material`
- `source_evidence_ids`
- `source_evidence_kind`
- `status: EvidenceResolutionStatus`
- `scope_complete: bool`
- `reason_codes`

Use `stable_contract_id` for record identity.

Do not add a second EvidenceResolutionStatus vocabulary.

### Direct-callout positive contract

A `direct_wall_callout` may become CORROBORATED only when all of the following are true:

1. finish annotation words are native visible source observations in the exact snapshot
2. the parsed finish phrase is semantically accepted without project-specific vocabulary
3. native leader geometry is connected to the annotation itself, e.g. endpoint intersects/touches the annotation bbox
4. the leader chain is contiguous by native geometry
5. a native terminator is attached to that chain
6. the terminator intersects/touches exactly one authenticated physical wall assembly or source primitive set owned by exactly one physical wall
7. no second wall is equally owned by the terminator
8. semantic face wording is explicit enough to identify the physical face role
9. the required wall topology / room-face authority for that role is CORROBORATED
10. all lineage matches document/revision/SHA/snapshot/page/scope

Failure of any link must abstain.

No nearest note, nearest wall, first candidate, smallest gap or project-name rule is permitted.

### Completeness contract

For each `trade_scope_id`, produce a scope summary over the complete qualifying physical-face universe.

The scope summary must distinguish:

- CORROBORATED individual face bindings + incomplete scope
- complete scope
- ambiguous/unresolved faces
- conflicting bindings

`scope_complete=True` only when every qualifying physical face is accounted for exactly once (or duplicated by semantically identical source evidence that deduplicates to the same binding).

A local note can never silently promote a whole trade scope.

### Conflict and duplicate behavior

- same source callout replayed twice → same stable binding / no double count
- same finish repeated on same exact face → deduplicate
- distinct conflicting finish semantics on same face/trade → `CONFLICT`
- terminator touching two walls → `ABSTAINED` / ambiguous wall ownership
- stale revision/SHA/snapshot → abstain
- wall lineage mismatch → conflict/abstain, never rebind by proximity

## REQUIRED SYNTHETIC PROOF FOR IMPLEMENTATION

Before any real-source promotion, test at least:

1. leader-bound finish note → one exact exterior wall face
2. room finish schedule → complete room-facing interior faces
3. facade elevation finish → exact external faces only with authenticated cross-view identity
4. page-wide keyword → abstain
5. nearby unrelated plaster note → abstain
6. duplicated note → no duplicate binding
7. two conflicting finishes on same face → conflict
8. one local finish note cannot authorize all walls
9. caller `both_faces` cannot mint authority
10. reversed wall orientation preserves semantic physical face identity
11. translation invariance
12. rotation invariance
13. scale invariance
14. input-order invariance
15. unrelated-content invariance
16. viewport-expansion invariance
17. stale revision/source-SHA rejection
18. stable IDs / deterministic replay
19. no input mutation
20. exact physical-wall lineage mismatch rejection
21. leader endpoint merely near text but not connected → abstain
22. terminator merely near wall but not intersecting authenticated ownership → abstain
23. one terminator touching two candidate walls → abstain
24. generic page-wide wording plus exact wall geometry → still abstain for face ownership

## BENCHMARK FACTS EXCLUDED FROM IMPLEMENTATION

The following are explicitly not algorithm inputs:

- benchmark expected finish quantities
- benchmark accepted/missed status
- scorer tolerances
- project names / benchmark ids
- any target quantity used to choose a wall, face, threshold or finish extent

Real development sources were used only to determine whether producer-ownable evidence forms exist and to expose failure modes.

## DECISION

**Item 19B is viable.**

The first implementation should be a standalone, shadow-only direct-callout authority.

KSTVET provides real native evidence for the direct-callout pattern, but current real-source output must remain `FINISH_BINDING_SOURCE_PRESENT_GEOMETRY_PENDING` until the source terminator is resolved through the existing producer-owned physical-wall/topology authorities to an exact physical wall and semantic physical face.

Lamu is a useful broad-scope semantic negative/partial case.

Ghazi is a source-blocked negative case.

No live wall-finish quantity promotion is authorized by this report.
