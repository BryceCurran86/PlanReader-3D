# Wall identity from source lineage (design, 2026-11-28, MAX 7232924376)

Design only. Nothing here is built into production; no existing id, record or signed row changes.

## Observed
- A wall's assembly id (`wall_candidate_id`) hashes the viewport and the quantised centreline, so any node move renames it.
- The candidate identity (`candidate_identity_id`, v2) adds source primitive ids but still hashes the centreline.
- A host binding's record id and `host_wall_id` hash the member wall ids, their v2 ids, equivalence groups and source
  observation ids; evidence ids and signed rows carry them.
- Snap changes move nodes by fractions of a point: on Lot16 sheet 3 the order-free snap moved host walls at most 0.5 pt
  and renamed the host walls of 13 of 22 openings.
- Splitting at crossings happens before snapping, so the split source pieces (their source ids and endpoints) are the same
  whatever the snap does.

## Inference
A wall's physical makeup is the set of source pieces it is built from; where the snap puts its nodes is a measurement of
that makeup, not part of it.

## Proposed (shadow sidecar, default off)
`lineage_identity_id` = hash(viewport, sorted set of the wall's source pieces longer than the snap tolerance), each piece
being (its sorted positive `source_primitive_ids`, its own quantised endpoints before snapping, direction-free).
Pieces no longer than the tolerance are left out: they cannot define a wall, and different snaps keep or collapse them.

Veto (no lineage id, never a choice):
- a wall with no piece longer than the tolerance, or a piece without positive source ancestry;
- two walls of the same viewport with the same lineage set (collision);
- a source piece claimed by more than one wall.

Rules:
- The lineage id is a new field. Candidate ids, v2 ids, host binding ids, evidence ids and signed rows are untouched.
- No old id is ever copied onto a new wall. A report may say "same pieces, moved by at most the tolerance" only when two
  walls' lineage ids are equal and every piece is the same; any other difference is "changed".
- Adopting lineage ids inside host bindings would rename every binding once and needs MAX's re-signing decision; this
  design does not ask for it.

## Proof required before use
Synthetic: a moved corner keeps the lineage id; a different membership changes it; dropped short pieces do not; collision,
shared piece and missing ancestry abstain; input order and direction invariance; determinism; no mutation. Then a
report-only comparison on the originals (how many host member walls keep their lineage under a snap change).

## First measurement (offline, one Maryborough capture, ordinary snap against order-free 1.0.0)
Local script, not production code. Of 10,690 walls, 80% keep their candidate id; 94% of the 10,340 walls with a lineage
key keep it (346 have no long piece, 4 collide). Host member walls of the 52 openings hosted both ways: 10 keep their
ids, 6 more keep their lineage, 36 differ, mostly because the snap changes where a wall chain ends (17 gain pieces, 14
lose some, 3 overlap, 2 other). So whole-chain lineage is not enough for hosts: host evidence would need the source
pieces at the jambs, a further design step if MAX wants it.

## Built (28 Nov, report only)
`pb_wall_lineage_identity_shadow.wall_lineage_identities` (`wall-lineage-1.0.0`) with the opt-in
`retain_leaf_fragments_shadow` on `build_wall_graph_for_viewport` (adds only the pieces' own endpoints and source ids).
Synthetic tests: moved corner keeps the id; membership and viewport change it; short pieces ignored; vetoes for missing
edge, piece or ancestry, no long piece, shared piece; order and direction invariance; minus zero; no mutation. No live
caller; nothing existing changes.

Observed while building: intersections can yield -0.0, and `stable_contract_id` hashes it apart from 0.0. The existing
`canonical_path_fingerprint` (assembly wall ids) keeps -0.0 too, so those ids can depend on input order at such points.
Not changed here (it would rename walls); for MAX.

## Not authority
No wall, host, opening, measurement or quantity authority; no threshold other than the existing snap tolerance.
