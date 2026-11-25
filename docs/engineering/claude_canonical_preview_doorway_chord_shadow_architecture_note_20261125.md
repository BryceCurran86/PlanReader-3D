# Source-owned doorway chords in the canonical bounded preview (MAX item 3, P2c) - architecture note

**26 November 2026:** the door-stroke exclusion this channel relies on now ships only with `door_jamb_returns`, so the channel calls the builder with that switch on (see `claude_door_jamb_return_architecture_note_20261125.md` section 9).

Date: 2026-11-25 (Brisbane). Status: PROPOSAL. Nothing here is built, merged, pushed or posted. Local branch `claude/preview-chords-note-20261125`, cut from main `d69f8e1a9`. Orders: MAX's review #4135 comment 7111308442 item 2 ("prove the canonical bounded A500 preview produces real doorway chords") and note comment 7116011360; the owner said "Yes, start P2c". It builds on P2a and P2b (merged), P3b (draft #4683: door symbol strokes no longer mint wall strips in the layered ring) and P3a (draft #4686: gate receipts). Shadow only. No repository code was changed for this note: every experiment ran as a monkeypatch in a scratch process and prints counts only. **It corrects the P2 note**, which expected P2c to be producer wiring in the preview's builder (section 1.5 below shows why that cannot meet MAX's request).

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md`; the P2 and P3a notes; #4683 and #4686; MAX's comments above and GPT MAX's #4135 comment 7133508361.
- **Functions traced:** `tools/run_canonical_source_native_preview.run_preview` -> `pb_new_source_trace_preview.source_native_trace_preview` (source scope `:206-221`, builder call `:297-323`, closure overlay `:494-500`, summary `:725-737`) -> `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings` (entry checks `:2290-2334`, strip assembly `:2335-2368`, `_gaps` `:2375`, swing arcs and placement `:2430-2470`, closure owners `:2501-2625`, rings `:2626-2714`), its `_swing_arcs`, `_place_swings`, `_merge_ring_results` and `LayeredRoomRingResult`; in `pb_layered_wall_doorway_room_ring_shadow.py` the chord block and `_gaps_containing_swing`; the segmented producers and the proposer; `scripts/check_canonical_trace_route.py`.
- **Authority boundaries crossed:** none raised. Chords stay candidate topology (`source_physical_door_host_authenticated=False`, `metric_area_issued=False`, `commercial_publishable=False`); the preview summary keeps `quantity_authorized=False`.
- **Expected abstentions, predicted before measuring:** a door with no raw wall gap on its wall line yields no chord; a page over the layered structural cap abstains with its reason.
- **Files that stay untouched:** the proposer and its gates, `collect_source_black_segmented_door_swings`, the topology rules of both ring builders, W10, `benchmarks/frozen_holdout/full_plan_v2/**`, the 20,000 constants, the door stack (#4638, #4649, #4654, #4655, #4665). No open PR touches the preview builder or its caller.

## 1. Observed repository behaviour (main `d69f8e1a9`; originals read in place; counts only)

**1.1 What "the canonical preview" runs.** `run_preview` calls `source_native_trace_preview(pdf, page_index)` and writes `canonical_source_native_receipt.json` with the whole summary as `full_preview_summary`, after `validate_canonical_preview` pins `summary["producer"]` to `EXPECTED_PRODUCER`. The preview imports `build_layered_wall_doorway_room_rings` from `pb_next_wall_ring_preview` (`:41-50`) and calls it with `stroke_pair_wall_faces=True`, `wall_end_stroke_closures=False` and the page's display tiles as viewports.

**1.2 That builder is a separate module, not the layered module's builder.** `summary["producer"]` is the string `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings` (`:522`, pinned by the runner), but the function called is the preview module's own copy, with its own strip collectors, gap search, swing placement and result type. It has no merged collinear dark-face collector (0 references; the layered builder gained one at `4285e133a`) and no segmented-swing producer (0 references), reads native curve arcs only, and its `LayeredRoomRingResult` (`:257`) has no witness or chord field; `_merge_ring_results` (`:2161`) keeps rings, closures and counts only. So P3b and #4686, which live in the layered module, cannot change the preview: its summary and PNG digests on the five Maryborough pages are identical before and after P3b (#4683 body). Five production modules import the preview module; none serialises the whole result.

**1.3 Closures.** A gap closes only with exactly one owner (swing, stroke, sliding leaf, cavity slider or panel-lift words); the closure is the whole gap rectangle. On the five pages every closure the preview makes is a `source_stroke_closure` (P2 note 1.5). Its `_place_swings` has no exact-end rule for segmented swings (the layered `_gaps_containing_swing` does).

**1.4 What the proposer would see inside the real canonical run** (spies on the preview builder's `_swing_arcs` and `_place_swings`; the 21 segmented witnesses on the five Maryborough pages with source swings; preview rings/closures in the second column are unchanged by anything below):

| Page (index) | Witnesses | Preview rings / closures | Producers wired as-is into the preview's pipeline | Door ink hidden from the preview's collectors (the P3b rule) | Doors with no preview strip along their wall line | Layered dark-painted builder on the same rows (P3b tree) |
|---|---|---|---|---|---|---|
| A110 (6) | 12 | 6 / 3 | 2 chords (doors 3 and 7), 10 no parent | 1 chord, 1 competing, 10 no parent | not measured | 2 chords (doors 7 and 10), 2 competing, 8 no parent |
| A500 (23) | 4 | 3 / 9 | 0 (4 no parent) | 0 (4 no parent) | 4 of 4 | 1 chord, 2 competing, 1 no parent |
| A501 (24) | 2 | 2 / 5 | 0 (2 no parent) | 0 | 2 of 2 | 0 (2 no parent) |
| A502 (25) | 1 | 2 / 1 | 0 (1 no parent) | 0 | 1 of 1 | 1 chord |
| A503 (26) | 2 | 0 / 1 | 0 (2 no parent) | 0 | 2 of 2 | 1 chord, 1 no parent |

**1.5 Why.** In the preview's own strip set there is no strip along the wall line of any of the 9 doors on A500-A503 within 400 pt; the only strips that cross those lines run across them, not along them (on A502 the one such strip is built from the door's own strokes). The proposer therefore finds no raw gap on the wall line at all (first failing gate "no parent", zero candidates), with or without the door ink. In the layered builder's default configuration the strips along those lines are minted by the merged collinear dark-face collector, which the preview does not have (A500, A502 and A503 probed). On A110 the two builders agree that doors 0, 2 and 4 have no raw gap on their wall line, agree on door 7 as a chord, and disagree on door 3 (preview chord, layered competing parents) and door 10 (layered chord, preview no parent).

**1.6 The layered builder on the same page rows.** The preview's outlined-lettering scope does not apply on any of the five pages (rows identical), so the layered dark-painted builder gives the same result on the preview's rows as on the raw page: 5 chords (A110 2, A500 1, A501 0, A502 1, A503 1). One pass took 7 to 50 s here (A110 50, A500 19, A501 18, A502 7, A503 15) against 24 to 45 s for the preview itself (uneven machine load; indicative only).

## 2. Inference

1. Wiring the segmented producers into the preview's own pipeline cannot give real chords on A500: its wall evidence does not include the doors' walls. The honest result there is 0 of 9 on A500-A503, plus a chord set on A110 that disagrees with the layered builder on 2 of 3 doors.
2. Hiding door ink from the preview's collectors changes nothing useful: still 0 of 9, A110 loses a chord to a competing parent, and rings and closures are identical on all five pages.
3. Closing that gap inside the preview means giving it the layered wall evidence (the merged collinear dark-face collector, whose arrival took A110 from 118 to 559 strips in the layered builder). That is a topology change for its own review, not a producer wiring.
4. The layered dark-painted builder already produces the reviewed chords on exactly these rows. The smallest honest proof that "the canonical preview call produces real chords" is a shadow channel that runs that builder on the rows the preview already scoped and reports its witnesses and chords beside the preview's own result without changing a ring or a closure. Two chord producers that disagree on one page (1.5) would breach AGENTS.md's no-second-resolver rule if both were live.
5. The channel's real-data result depends on P3b: on main without it the layered builder gives 0 chords on all five pages.

## 3. Proposed change (shadow, default-off, no new authority)

**P2c: `source_owned_doorway_chord_shadow` in the canonical preview.**

- A new small module with one function `source_owned_doorway_chord_shadow(rows, *, source_sha256, page_index) -> dict`. It calls the layered module's `build_layered_wall_doorway_room_rings` with `dark_painted_wall_source=True` and no other flag, and returns counts plus per-chord topology-only receipts: a `receipt_id` (`stable_contract_id` over source hash, page index, swing path ids and the rounded interval), orientation, wall band, door interval, the swing, support, jamb and threshold native path ids, the builder status and reason codes (a page over the structural cap says so), and the witness and chord counts. Every receipt keeps `source_physical_door_host_authenticated`, `metric_area_issued` and `commercial_publishable` False and says `applied_to_preview_topology: False`.
- `source_native_trace_preview(..., source_owned_doorway_chord_shadow: bool = False)` (explicit boolean, like the builders' flags). When True it adds ONE summary key with that block, computed from `vector_scope.drawings`, the rows its own selector receives. Rings, closures, strips, the PNG and every other key are unchanged; when False the whole output is byte-identical.
- `tools/run_canonical_source_native_preview.py` (`run_preview`, `main`) gains an optional `--with-doorway-chord-shadow` that is passed through, so the canonical receipt's `full_preview_summary` carries the block. Validation and defaults are unchanged and `check_canonical_trace_route.py` must still pass.
- Not in P2c: applying chords to the preview's rings (needs its own wall evidence, 2.3, and an authority-promotion review), drawing chords on the PNG, surfacing the cap reason of a dropped tile (P2 note D5; measure its blast radius first), the `producer` label.

## 4. Tests

Pure function (synthetic, no private data): a wall with one doorway returns the same chords as a direct builder call on the same rows (differential); an unsupported door is counted as a witness with zero chords; no wall ink and over-cap pages say so; look-alike negatives (a dashed non-door polyline); translation and axis-swap invariance; no mutation of the rows; deterministic replay and stable ids; authority flags. Preview integration (a small synthetic PDF through `source_native_trace_preview`): flag off equals main byte for byte (summary and PNG digests); flag on equals flag off plus exactly one key; PNG identical. Runner: the option passes through, the default receipt is unchanged and the route guard passes. Single-line mutants of the new function and of the flag branch. Local, counts only, after #4683 merges: the canonical runner's receipt shows A110 2, A500 1, A501 0, A502 1 and A503 1 chords; digests with the flag off are identical on the upright and rotated pages used for P2a and P2b; run time.

## 5. Benchmark observations that must not influence the implementation

The page indices, witness, chord and gate counts, the offsets (0.6, 2.4 and 4.56 pt) and the run times are observations on the Maryborough original, used only to verify. No threshold, count, page index or sheet name enters code; the block reads whatever the layered builder returns for the rows it is given.

## 6. Decisions

D1 scope: the shadow channel above (recommended), or port the merged collinear dark-face collector into the preview and then wire producers there (a larger topology change for a separate review; chords would then also be applied to rings), or wire producers into the preview's own pipeline as-is (0 of 9 on A500-A503, disagrees with the layered builder on A110). D2 order: #4683, then #4686, then P2c; P2c does not import #4686, so it can be built now but shows real chords only after #4683. D3 overlay: none in P2c (PNG identical), or draw chord rectangles when the flag is on. D4 viewport: record the viewports and flag each chord as inside or outside them (recommended), or report only chords inside. D5 the dropped-tile cap reason: its own small PR after a census. D6 the `producer` label names the layered module while the preview calls its fork; leave it (the runner pins it) and note it for MAX. D7 applying chords to the preview's topology later needs the wall evidence of 2.3 and an authority-promotion review.

## 7. Not claimed or not run

The owner-local release path (signed Lot16 and Maryborough retention) and the frozen four-project score were not run; nothing here is a score. Not measured: the preview's own strips on A110's doors, any tile-mode page (none of the five tiles), a corpus-wide run time or cap census, and a preview with chords applied. The spies are throwaway monkeypatches; the layered figures come from the P3b tree with the P3a tool.
