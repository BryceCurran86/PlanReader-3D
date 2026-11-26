# Proven doorway chords as topology-only closures in the canonical preview (default off)

Date: 2026-11-26. Order: owner directive on issue #4764 (comment 7172590477, item 2); claim on #4764 (comment 7173283111). It follows the read-only channel of the P2c note (`claude_canonical_preview_doorway_chord_shadow_architecture_note_20261125.md`), whose section 3 left applying the chords as a separate change.

## 1. Observed repository behaviour

- The canonical preview (`pb_new_source_trace_preview.source_native_trace_preview`) draws rooms with `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`, not with the layered module's builder. That tracer closes a doorway only when one of its own producers owns the whole gap.
- The proven doorway chords come from the layered dark-painted builder (`dark_painted_wall_source=True, door_jamb_returns=True`), reported by `pb_source_owned_doorway_chord_preview_shadow` since the channel landed.
- On the originals checked here (8 chords on three sheets), the tracer closes none of those doorways itself, and for none of the 8 do its own wall pieces touch both ends of the doorway (the nearer misses are 2 pt, the larger ones up to 82 pt).

## 2. Change (shadow level, default off, no new authority)

- The tracer takes `source_owned_doorway_chords` (default none): the channel's topology-only receipts. Each chord in a viewport closes its door interval across its wall band, unless the tracer already closed that doorway (same direction, touching band, at least half of the shorter interval shared). Only the tracer's own closures can hold a chord back, so no chord outranks another. A collinear gap lying inside an applied chord (within the existing 0.8 pt double-stroke tolerance) no longer vetoes the room beside it. The closure kind is `source_owned_doorway_chord_closure`.
- A receipt that is not topology-only (any authority flag not False) or has malformed geometry is rejected.
- `source_native_trace_preview(..., source_owned_doorway_chord_closures=False)`: when True it computes the channel's chords on the rows the preview scoped, passes them to the tracer, and adds one summary key saying which chords were applied. It cannot be combined with the read-only channel, whose contract is that nothing was applied. A raster-underlay page gets no chords.
- `tools/run_canonical_source_native_preview.py --with-doorway-chord-closures`, with a validator that fails closed unless the block belongs to the source and page, reports applied chords honestly and claims no authority.
- Untouched: the chord producer and its gates, both builders' wall evidence, W10, quantities, authority, issuer, schedules, finishes, the 20,000 cap, the 2.5 pt snap, the app's default call.

## 3. Verification

- Synthetic tests (`tests/test_preview_doorway_chord_closures_v1.py`): an open room closes only with the chord; a doorway the tracer already closed gets no second closure; a far chord changes nothing; a partly covering chord keeps the gap unresolved; authority and malformed receipts are rejected; order, replay, translation, viewport and tiled-run behaviour; preview and runner switches.
- Preview-related suites and the route guard pass; 3Laurel tracer suites pass with the original.
- Originals, switch off versus on (counts only):

| Source page (index) | Chords proven / applied | Tracer closures | Rooms (candidate) | Total room area | Preview run time |
|---|---|---|---|---|---|
| Maryborough 6 | 6 / 6 | 3 -> 9 | 6 -> 6 | unchanged | 35 s -> 87 s |
| Maryborough 23 | 0 / 0 | 9 -> 9 | 3 -> 3 | unchanged | no change |
| Maryborough 25 | 1 / 1 | 1 -> 2 | 2 -> 2 | unchanged | no change |
| Maryborough 26 | 1 / 1 | 1 -> 2 | 0 -> 0 | unchanged | 18 s -> 33 s |

- No room uses a chord closure on these pages and no existing closure is lost. Two room records on page 6 and one on page 25 get new IDs because only their starting vertex moves: the ID includes the polygon's vertex order, which the geometry library may change when any closure is added. That sensitivity predates this change.

## 4. What this does not do

- It does not make a new room on these originals. The tracer's walls do not reach both ends of any of those doorways, so the next gate is wall evidence in the preview's tracer (the layered merged collinear dark-face collector is not in it; P2c note 2.3). That is a separate topology change for its own review.
- It is not on by default and the app does not pass it. Turning it on there is the owner's decision.

## 5. Benchmark observations that must not influence the implementation

Page indices, counts and run times above are observations used only to verify. No threshold, count, page index or project name enters code. The 0.8 pt tolerance is the tracer's existing double-stroke constant.
