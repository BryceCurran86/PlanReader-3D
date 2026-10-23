# GPT2 → GPT MAX structural-identity and source-closure handoff — 2026-10-20

**Review-only first deliverable.** No production behavior, benchmark truth, test gate, source PDF, commercial output, or signed quantity changes in this PR.

## What was read

- `AGENTS.md`
- `docs/AI_ENGINEERING_PLAYBOOK.md`
- `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`
- `pb_wall_room_topology_wall_assembly.py`
- `pb_live_wall_opening_authority_composition.py`

Observed earlier repository issue evidence: W4 producer page-7 scope reported two physically distinct candidates with the same `wall_candidate_id` `wall_6d948b1b47258597fa66`; their `face_a_segment_ids` include `split_2296` and `split_9744`. That is a historical original-source receipt requiring a same-source replay before promotion.

## Observed producer behavior

1. W4 `assemble_wall_candidates` is the structural chain assembler; only a subset of classified junctions permit continuation. Unresolved or ambiguous junctions deliberately prevent chaining while retaining candidates.
2. W4 `_UnionFind.union` deterministically selects a representative **edge root** by sorted order; such deterministic selection cannot itself prove two physical walls are identical. Wall identity must remain source-owned, not a dictionary last-write-wins effect.
3. `compose_live_wall_opening_authority` in `pb_live_wall_opening_authority_composition.py` composes physical wall candidate authority, physical opening existence, host bindings, whole-wall frames and opening-universe completeness against one immutable source snapshot. It stops before metric geometry and commercial quantity publication.
4. `LiveWallOpeningAuthorityComposition` retains separate per-page wall scopes, opening binding traces and host frame traces; `LiveWallScopeTrace.scope_complete` and `wall_candidate_ids` are relevant for detecting hidden incomplete universes.
5. A room label, topological face, finish occurrence, or cross-sheet translation is not proof of wall identity or host binding.

## First-failing chain and proposed staged implementation (not approved yet)

**Task A — collision proof.** Reproduce exact two-record collision from source; compare the complete W4 candidate records, source-segment membership, end junctions, centerline and physical equivalence. Verify whether current `canonical_path_fingerprint` already distinguishes their geometries. A two-record source scope must retain both candidates or positively classify physical equivalence. Never resolve by insertion order, nearest or first.

**Task B — identity shadow patch after review.** On producer-only shadow branch, derive candidate identity from canonical physical-path provenance, not endpoints alone; deterministically preserve both distinct records. Audit every downstream `wall_candidate_id` indexed mapping for potential overwrite. Leave commercial and frozen truth paths untouched.

**Task C — MAX host handoff.** With identical source SHA / revision / snapshot and page scope, replay `compose_live_wall_opening_authority` before and after. Show all physical opening identity records, resolved structural host record IDs, whole-wall frame IDs, complete candidate-universe receipts and the first failure for each unresolved object. No count or area promotion from presence of a host.

**Task D — room evidence.** Continue Maryborough physical floor boundary closure independently. Honour owner-confirmed open passage between DRY STORE, WASH UP, FOOD PREP and FOOD SERVICE/POS COUNTER; do not invent separating walls. Resolve PWD, LAUNDRY, AIRLOCK, FREEZER, M-AMB/F-AMB from source boundary evidence. Owner markup is corroborative review material, not PDF-native source ink.

**Task E — finishes and ceiling evidence.** Independently prove FT2/FT3 finish definitions, plan occurrence ownership, and page-11 → page-7 correspondence without choosing among ambiguous candidate registrations. Authenticate page-9 IPF1/grid/CL03 reflected ceiling zones and external soffits. Consumer GPT1 handles metric dimensions and FIRM quantities.

## Predicted abstentions

- Two W4 records collide but distinctness cannot be authenticated: neither may be silently overwritten.
- Page scopes incomplete or mismatched across revision/snapshot: host/frame cannot be promoted.
- Open room passage or wall-face ring unclosed: room stays unsupported.
- FT2/FT3 mark not tied to exact physical floor region: floor-finish area stays abstained.
- Ceiling code on a view without exact zone boundary: zone area stays abstained.
- Source ownership for opening filling type, figured vertical dimension or count incomplete: opening quantity/count stays abstained.

## Required tests

Reproduce collision and prove no loss; synthetic two-distinct-walls/same-endpoints positive and genuine-same-path duplicate; reversed segment ordering; split/merge invariance; rotation/translation; look-alike negative; ambiguous junction; deterministic stable IDs; unmodified signed Lot16 eight rows; Maryborough existing signed floor rows; unchanged default commercial output and V2 truth; original source proof on exact head before authority review.

## Non-negotiable boundaries

No global snap tolerance change, primitive cap change, geometric nearest-match identity, assumed wall division, default opening count, assumed height, consumer publish flag, or score-driven threshold. Preserve frozen V2 references, hashes and evaluator. Source-specific geometry is **diagnostic evidence**, never a coded special case.

## Completion receipts required to support GPT MAX

1. Source collision retained/resolved without silent overwrite.
2. Wall scope completeness accounted for, per page.
3. Host/frame continuity before and after, with exact physical opening identity.
4. No loss or rewriting of existing sealed quantity IDs and source provenance.
5. Explicit GPT1 handoff of genuinely new measured candidates and GPT3 frozen post-seal score delta.

Until these receipts exist, this document is a review and work plan, **not** a claim that 99% or even one new target has been reached.
