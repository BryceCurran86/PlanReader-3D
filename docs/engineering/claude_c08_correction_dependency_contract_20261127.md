# C08: what must be recalculated after a user correction (geometry side)

Date: 2026-11-27. Order: #4764 7200170458 (remaining C08 dependency contract). For MAX M02. Report only: no code changes.

## Observed (current behaviour, `main` e9516390d)

- `pb_new_source_trace_preview.source_native_trace_preview(..., review_packet=...)` recomputes the whole page on every correction: page read, wall-ink scoping, outer-wall attempt, door review, space key, the room tracer once without the packet (recording pieces) and once with it, the review block and the overlay.
- Pieces the tracer hands to the packet (`barrier_view`, `LayeredBarrierView`): wall strips, other wall fills, opening closures and their rects, unresolved gaps. The hook runs after walls, openings and chords are built and before rooms are formed.
- Tiles: n x n over the page (n = 3 up to 7,000 drawings, 4 up to 20,000, 5 above). Under the primitive cap the tracer runs one pass over the page; over it, one pass per tile, each forming its own rooms, and `_merge_ring_results` merges them by record id. "Tile" below means one tracer pass.
- `plan_review` decides every mark against the pieces of all tiles: a reject applies only when it crosses exactly one candidate (overlapping pieces count once) and user-line ends join every piece within 2.5 pt.
- `ReviewPlan` gives every tile all user barrier rects, and each tile's domain grows to include them.

## Proposed contract (not built)

Reuse, keyed by all of: source SHA-256, page index, native page frame receipt, preview options (`admit_wall_joint_paint`, `source_owned_doorway_chord_closures`), tile layout and geometry code revision:
- the scoped drawings, outer-wall attempt, door review, space key, overlay and automatic rooms;
- per tile, the pre-hook pieces (strips, fills, closures, closure rects, unresolved gaps).

Recompute on every new `review_revision` / `packet_sha256`:
- packet validation, then `plan_review` over all tiles' pieces (reject uniqueness and end joins are page-wide);
- room formation for every invalidated tile, the merge, and the review block.

Tile invalidation (exact): a tile is re-formed when a removed strip, fill or closure belongs to it, a gap of it becomes covered or uncovered, or the set of user barrier rects changes. Because every tile currently receives every user rect, any added, moved or removed user wall or closure invalidates all tiles; only rejects and non-barrier marks (finish, exclusion, outline) stay local. Giving a tile only the rects that reach it would be a behaviour change and needs its own review.

Never:
- reuse across a different source, page, frame, option set or code revision; if the key cannot be proven, recompute everything;
- let a user mark grant physical wall, opening, metric, commercial or benchmark authority (unchanged).

## Needed from M02 (MAX)

1. Correction identity: monotonic `review_revision` with `packet_sha256`, and the rule for undo (a lower revision is a new packet, not a cache hit by number).
2. Invalidation events outside geometry: source replaced, page or viewport reassigned, application update.
3. Where the cache lives (session or stored) and its size bound.
4. Which downstream results must be marked stale; the geometry side can supply changed room ids (`same_as_automatic`, `room_id`, `user_mark_ids`).

## MAX's answers (#4764 7201721302), adopted into the contract

- Packet identity: a canonical digest of source revision, page, frame, options and schema plus the ordered active operations (order by `correction_id`; the tracer's result does not depend on mark order).
- Undo removes the operation and invalidates the affected pass; pieces recorded once serve every later packet.
- Upstream extraction cache keyed by original SHA, page, frame, options and code, bounded in bytes and entries; a source change invalidates the whole document.
- An edit invalidates the affected topology and every dependent room, finish, quantity and customer receipt; no stale commercial output.
- The API is agreed with MAX before any cross-file edit; it is not built.

## Geometry-local invalidation tests (`tests/test_correction_invalidation_scope_v1.py`)

Confirmed on synthetic pages: the pieces offered to the marks do not depend on them; pieces recorded once give the same rooms as a fresh run for every later packet, including undo; marks that are not barriers leave rooms unchanged; a mark changes only the room it touches (compared by geometry); mark order does not matter.

**Fixed (2026-11-27, owner approved):** a room's `record_id` hashed its corner list as shapely returned it, so closing a gap in one room changed an untouched room's id, and the review block reported `same_as_automatic: false` for unchanged rooms. `pb_next_wall_ring_preview` now writes every ring turning the same way and starting at its smallest corner, before the edge owners and the id are computed. Geometry is unchanged; preview room ids change once. Dependents may now invalidate per room id.

Limits:
- ids still name source paths by their position in the drawing list, so reordering the same lines changes ids (corner lists do not change); one source file always lists them in one order.
- `pb_layered_wall_doorway_room_ring_shadow` has the same corner-order pattern. It feeds the benchmark handoff, so it is not changed here: its receipts would change.

C08 stays open until the API is agreed.

## One measurement (one residential floor plan page: one tracer pass, 18 rooms)

Preview without a packet: 29.0 s, of which the tracer run is 14.8 s: 13.9 s before the correction hook and 0.9 s forming rooms. A correction today repeats the whole page and runs the tracer twice. Under this contract no correction repeats the part before the hook: it re-forms the rooms of the invalidated passes (about 1 s per pass) and re-runs the plan and review block (not timed).

## Benchmark observations that must not influence the implementation

Any timing here is a measurement of one page. No project, page, count or expected value enters code.
