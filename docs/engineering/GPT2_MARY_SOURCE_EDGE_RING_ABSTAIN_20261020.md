# GPT2 — Source edge ring conflicts before Maryborough room promotion

## Architecture and source review
Full pre-code architecture report: GPT2 tracker #2843 comment 6270728187. Actual repository call path inspected: `pb_wall_topology_diagnostics.collect_topology_from_segments` → W2 `build_wall_graph_for_viewport` → W3 `classify_junctions` → W4 `assemble_wall_candidates` and `_source_owned_collision_candidate_addresses` → W5 `reconstruct_room_candidates` → only candidate `RoomCandidate`; none of these alone issue `QuantityEvidence`.

Original private Maryborough PDF SHA `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, 31 pages, original p7 and p11 rendered. Original **plan images and labels do not independently prove a full W2/W4 source edge ring**. The live source-ring verification requires source-produced edge+wall records with exact revision/snapshot/scope; it is not claimed complete here.

## Specific physical problems and safe implemented guard
- W4 on current main **already** implements `_source_owned_collision_candidate_addresses`; do not clobber that existing repair or elect wall by dictionary overwrite.
- FREEZER's historical self-intersecting candidate cannot be treated as a floor. The new `tools/diag_gpt2_source_room_cycle_shadow.py` detects non-adjacent source line crossings and leaves the complete competing edge inventory intact.
- FOOD SERVICE and POS COUNTER are an owner-confirmed connected physical area with interior partitions, not separate forced closed rooms. The tool never converts label membership into a new structural wall.
- WASH UP / FOOD PREP have an owner-confirmed open passage. A missing boundary edge leaves an endpoint degree other than two and returns `ABSTAINED`, never a fabricated divider.
- Multiple disjoint source rings cannot be silently joined into one room; duplicate W2 ids, same geometric segment owned twice, missing W4 source address, wrong source snapshot, absent raw primitive lineage, zero-length segment and nonfinite source coords fail closed.
- Exact 6-decimal diagnostic coordinates match the existing W5 source-address convention. This is **not** a new W2/W4 snap tolerance or a wall-member merge threshold; the 2.5pt W2 tolerance is untouched.

## Source-only function contract
`audit_source_ring(original_w2_w4_edge_receipts, source_sha256=...,page_id=...,snapshot_id=...,decision_scope_id=...)` produces a deterministic first-failure report. `CANDIDATE` means *necessary geometry-only cycle check passed*, and explicitly carries `physical_room_boundary_authority=False`. A furniture rectangle can be `CANDIDATE` but cannot become a structural room; exact W2/W4 source wall type and full source universe remain required. ABSTAIN retains all observed source IDs and typed blockers. No metric, trade finish, wall length, count, wall deduction or customer quantity is produced.

## Verification and gates
Local synthetic 36/36 passed: 20 input-order permutations, 5 affine rotations/translations, genuine simple cycle, open passage, bowtie self-crossing, furniture lookalike, 5 conflicting lineage/ownership cases, two disconnected loops, bad SHA, nonfinite source coordinate and nonmutation. Public exact-head CI, independent source authority review and **producer-issued Maryborough original source edge replay** are still required. No private PDF on public CI.

## GPT1 and GPT MAX handoff
- GPT MAX must supply authoritative original W4 source edge identity, source-relative ownership and physical-wall equivalence. A `CANDIDATE` from this helper must never be treated as host/frame/physical existence authority.
- GPT1 must measure finish-specific rooms only after an authenticated physical ring and correct internal face ownership, preserving open passages. A synthetic closed loop or a floor schedule label does not license material quantity.
- GPT3 retains signed old outputs, uses only issuer-approved FIRM quantities, and independently scores frozen v2.

**No existing producer/publication module, original PDF, signed customer row, W2 snap, raster cap, frozen truth/evaluator/120 denominator changed.** This work is an opt-in review-only shadow, not an accuracy score gain.