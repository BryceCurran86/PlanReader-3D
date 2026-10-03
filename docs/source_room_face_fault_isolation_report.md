# DEF-04: SourceRoomFaceAuthority fault isolation (diagnosis and change)

Status: **Draft; needs an authority-promotion review before merge.** No accuracy claim. The
change is monotonic: a scope without a degenerate face behaves exactly as before.

## 1. Observed repository behaviour

- `_derive_scope` planarizes every wall-candidate centerline of a CORROBORATED, complete
  wall scope (`extract_planar_faces`), checks every face edge has exactly one authenticated
  wall owner, then abstained the **whole page scope** with `source_room_face_tiny_or_degenerate`
  if any face had area < 1 pt^2 or < 1% (`_TINY_RELATIVE_THRESHOLD`) of the largest face.
- Planar faces are disjoint cells, so a degenerate cell cannot alter another face's polygon.
- The wall scope's records are all W4 candidates. On the Lot16 sheet every one of 2,638
  candidates is `single_line`, `status=candidate`, with **zero** supporting evidence ids; only
  84 are equivalence representatives. So at this layer there is no per-wall existence signal
  that separates a wall from annotation linework.
- `pb_source_wall_topology_authority.py` has the same whole-scope rule (not changed here).

## 2. The invariant

A planar face is a disjoint cell, so degeneracy is a property of the face. What a degenerate
cell can signal is local inconsistency of the walls around it (a stray line splitting a sliver
off a room, a doubled wall, an overlap at a junction). A face that shares a boundary edge with
it may then be an incomplete fragment of a larger room. A face that shares no boundary edge
with it is independent of that defect. Whole-scope invalidation is right only when the defect
is not isolated.

**Measured, development drawings (read-only census, not inputs to any rule):** the tiny-face
rule is the only thing stopping annotation geometry from being published as rooms on a
polluted wall pool.

| scope (page-wide, complete) | bounded faces | degenerate | outcome now |
|---|---|---|---|
| Lot16 p3 (live chain) | 214 | 123 (57%) | still abstains |
| Lamu p41 (viewport bound bypassed, diagnostic) | 163 | 107 (66%) | still abstains |
| Lamu p42 (same) | 78 | 39 (50%) | still abstains |

On Lot16 p3 only about two of the 214 faces are real rooms (a bedroom and a pantry); the other
non-degenerate faces are title-block cells, dimension-chain strips and poche corner squares.
Isolating the tiny faces **without** the strict-minority rule would have published about 88
mostly-junk faces. Wall-disjoint taint alone does not help (only 3 faces are tainted), and
component-level taint is worse (the 51-face title-block table is a clean component).

## 3. Change

`pb_source_room_face_authority.py`:

1. Degenerate faces are withheld, never published, and recorded as `withheld_candidates` with
   full provenance (face id, polygon, bounding walls, area, reason, causing faces).
2. A face sharing a planarized boundary edge with a degenerate face is withheld
   (`source_room_face_edge_adjacent_to_degenerate_candidate`).
3. Withheld faces never corroborate another face: wall-face and two-sided-wall counts for the
   multi-room component gate use independent faces only.
4. Isolation requires degenerate faces to be a strict minority of all bounded faces; otherwise the
   scope abstains with `source_room_face_tiny_or_degenerate` as before.
5. Unchanged whole-scope abstains: incomplete/uncorroborated wall scope, duplicate boundary-edge
   ownership, unresolved boundary-edge ownership, no independent face, component ambiguity.
6. `SourceRoomFaceScopeResult.face_universe_complete` (False when anything was withheld) and
   `withheld_candidates` are new defaulted fields; reason codes gain
   `source_room_face_candidates_withheld`.

`pb_live_canonical_room_composition.py`: when a resolved scope withheld candidates, the same reason
code is appended to the composition. **Decision for review:** composition status stays
CORROBORATED, because each published room is independently proven and
`pb_surface_evidence_v160` only consumes rooms from a CORROBORATED composition. Downgrading to
CANDIDATE would be consistent with the page-level partial precedent but would stop those rooms
reaching surfaces.

The threshold, the absolute floor and the area predicate are untouched.

## 4. Customer-output effect

None measured: every real page above still abstains. The only scopes that change are those that
previously abstained solely because a strict minority of faces was degenerate; they now publish
the independent faces. A synthetic PDF through the real producer chain (3 rooms plus a 16x5 pt
island box) goes from `abstained / 0 rooms` to 3 rooms with the `candidates_withheld` flag.

## 5. Tests

`tests/test_source_room_face_authority_fault_isolation.py` (30): degenerate island does not
destroy unrelated faces; edge-adjacent neighbour withheld; stray-line fragment withheld; withheld
faces never corroborate; sliver touching every room fails closed; strict-minority boundary 0..5
islands; duplicate and unresolved ownership still abstain; incomplete scope still abstains;
provenance equality with the faces-only baseline; clean scopes unchanged; seeded property (isolated
junk never changes or removes valid faces); translation, quarter turns, uniform scale, input order,
wall splitting, unrelated far content, deterministic replay and no mutation; real producer chain
end to end. Mutation check: removing the isolation, the minority rule, the adjacency taint or
the corroboration rule fails 10, 3, 4 and 3 tests respectively.

## 6. Findings not changed here

- Faces with holes: an island component inside a room is not subtracted (`has_voids=False` is
  hard-coded in the room index), so an enclosing room's area includes free-standing islands.
- The anti-box gate does not stop grid tables: a title-block or schedule table whose cells are all
  non-degenerate publishes cells as rooms on a page-wide complete scope.
- Wall candidates are not existence-proven at this layer, so faces inherit wall-pool pollution. For
  Lot16 the real blockers are wall-pool pollution (the raster pool is mostly the vector overlay
  re-rendered, see Defect 7) and the absence of closed room cycles in the raster wall pool, not DEF-04.

## 7. Benchmark observations that must not influence implementation

None of the census numbers, page numbers or drawing names is an input to code or tests.
