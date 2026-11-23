# A110 cap regression and the canonical bounded preview (MAX item 3) - architecture note

Date: 2026-11-24 (Brisbane). Status: PROPOSAL. Nothing here is merged, pushed, posted or wired. Planned branch (local until approved): `claude/a110-cap-structural-primitives-20261124`, cut from main `33eba1c61` (code-identical to `8da4a009c`; the one commit between them adds a docs file). Orders: MAX's review of this lane, #4135 comment 7111308442 points 1 and 2 (his item 3 in #2608 comment 7100270347). Shadow only; no authority, quantity or score is touched. No code has been changed for this note.

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md` and `docs/AI_ENGINEERING_PLAYBOOK.md` earlier in this session (not re-read for this note); MAX's comment 7111308442 in full; the modules named below. Not read for this note: the W2-W10 topology docs (this change touches neither).
- **Functions traced:** `_source_wall_ink_candidate_drawings`, `_is_source_wall_support_row`, `_visible_source_stroke_paint`, `_owner_excluded_green_ink` and the cap block of `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings`; `pb_next_wall_ring_preview._clip_drawing_items`, `_selected_primitive_count`, `_merge_ring_results` and its `build_layered_wall_doorway_room_rings` entry checks; `pb_new_source_trace_preview.source_native_trace_preview` and `_full_page_source_tiles`; `pb_source_segmented_door_swing_shadow.collect_source_black_segmented_door_swings` and `propose_source_owned_doorway_chords`.
- **Authority boundaries crossed:** none raised. Rings stay CANDIDATE with `metric_area_issued=False`, `commercial_projection_allowed=False`, `takeoff_eligible=False`; chords are topology only. The cap is a fail-closed bound on a shadow builder, not an authority gate. Non-test callers that pass `dark_painted_wall_source=True`: `pb_source_native_wall_role_and_junction_shadow.py:232` (imported only by `tools/run_native_exterior_path_ownership.py`), `tools/run_native_exterior_path_ownership.py:60`, `tools/run_original_footprint_first.py:245`; `pb_live_physical_net_wall_integration.py` forwards it only under its own default-False opt-in.
- **Expected abstentions, predicted before any test:** more than 20,000 structural primitives; a page with no wall ink (`no_wall_layer_strips`); green ink never counts and never enters; evidence strokes alone never mint a wall strip.
- **Files that stay untouched by the first PR:** `pb_next_wall_ring_preview.py`, `pb_new_source_trace_preview.py`, the segmented producers, the door stack (#4649/#4655/#4665), W10, `benchmarks/frozen_holdout/full_plan_v2/**`, `scripts/check_v2_truth_separation.py`, `documents/sources/*.pdf`, the 20,000 constant, the cap reason code, the selector's output.

## 1. Observed repository behaviour (main 33eba1c61, real originals read in place, counts only)

**1.1 Selector roles and the cap.** `_source_wall_ink_candidate_drawings` (`pb_layered_wall_doorway_room_ring_shadow.py:216-261`) keeps every original path index and gives each row one role: green (blanked), wall_support (`_is_source_wall_support_row`: named wall layer, black stroke with `_BLACK_MAX` 0.04, or near-black fill), opaque_fill (kept so it can hide a stroke), evidence (any other unfilled, visible, non-green stroke: "doorway/glazing evidence only", docstring `:227-229`), blank. The code says evidence is not wall: mid-gray or pale strokes "must not mint wall strips or alone authorize a bounded footprint primitive count" (`:199-201`). The cap (`:2176-2190`) sums `len(row["items"])` over the selector's whole output, so it counts all four kept roles, and abstains above 20,000 with `unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport`. The comment above it (`:2172-2175`) says black/dark source ink is beneath the 20k cap.

**1.2 History (bisected on the pinned original, same producer, same page).** `111001522` (13 Nov) made the closure count of the A110 real-source test stale by design (2 expected, 5 found). `3ce1d9b18` (18 Nov, Acacia host-gap fix) added the evidence role: the counted set on A110 grew from 15,937 rows / 16,099 primitives to 45,021 rows / 45,189 primitives (green unchanged, 64,333 rows) and the page abstains. `4285e133a` (18 Nov, merged face strips) changes the A110 ring shape independently of the cap. Known-good `e93dbfe2e`: 118 strips, 6 rings, 12 segmented-swing witnesses, 2 chords, 5 closures. Two real-source tests fail on main with the local original and skip in public CI: `tests/test_original_source_segmented_door_swing_20261112.py::test_real_maryborough_a110_original_rings_retains_segmented_source_witnesses_but_never_invents_wall` and `tests/test_original_live_dark_filled_wall_rooms_20261112.py::test_real_maryborough_green_exclusion_unblocks_bounded_original_floor_wall_trace`.

**1.3 Role census, native primitives (rows in brackets).**

| Page (index) | rows | green | wall_support | opaque_fill | evidence | counted today | structural |
|---|---|---|---|---|---|---|---|
| A110 p7 (6) | 109,354 | 64,333 | 14,200 (14,038) | 1,899 | 29,090 (29,084) | 45,189 ABSTAIN | 16,099 ok |
| A500 p24 (23) | 20,334 | 0 | 11,437 | 159 | 8,804 | 20,400 ABSTAIN | 11,596 ok |
| A501 p25 (24) | 17,399 | 0 | 12,738 | 57 | 4,637 | 17,432 ok | 12,795 ok |
| A502 p26 (25) | 13,931 | 0 | 9,146 | 165 | 4,660 | 13,971 ok | 9,311 ok |
| A503 p27 (26) | 17,387 | 0 | 12,194 | 267 | 4,983 | 17,444 ok | 12,461 ok |

"Structural" = wall_support + opaque_fill, the set the cap counted before `3ce1d9b18`; it reproduces the 16,099 of that commit exactly.

**1.4 The canonical preview is a different builder.** `source_native_trace_preview` applies the same selector (`pb_new_source_trace_preview.py:175-183`), adds near-black strokes, and calls `pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings` (viewport-aware; no dark-painted option; no segmented-swing producer; its swing detector reads native curves only) with 3x3 / 4x4 / 5x5 tiles chosen by row count (`:53-65`, `:261`). That builder counts EVERY item of the rows it is given (`_selected_primitive_count`, `pb_next_wall_ring_preview.py:308-320`; entry checks `:2260-2304`), so the retained evidence strokes count there too. Only when the union of the tiles exceeds 20,000 items does it build per tile and merge. `_merge_ring_results` (`:2131-2175`) carries rings and closures but no chords, no witnesses, no two-wall tags, and silently drops the cap reason of a tile that abstained. The tiles are built from the display rectangle (`rect.width/height`) while `get_drawings()` rows are native: on the rotated Maryborough pages (29 of 31 are /Rotate 90) 29% to 56% of the native rows fall outside every tile (measured earlier in this session); upright pages lose none.

**1.5 Measurements (scratch trees, nothing committed).**

Canonical preview, closure kinds spied. Every closure on every page is `source_stroke_closure`; `swing_doorway` 0; chords 0; tiles abstained at the cap 0.

| Page | main: rings / closures / mode | native-frame tiles (scratch): rings / closures / mode |
|---|---|---|
| A110 | 5 / 2 / 25 tiles, 30 s | 5 / 1 / 25 tiles |
| A500 | 3 / 5 / single pass | 2 / 8 / 25 tiles (A500 counts 20,400 items, so it tiles and its rings fragment) |
| A501 | 2 / 4 / single pass | 2 / 5 / single pass |
| A502 | 2 / 1 / single pass | 2 / 1 / single pass |
| A503 | ABSTAINED / 0 | ABSTAINED / 1 |

Upright invariance of the native-frame experiment: identical summary and PNG digests on Q5446 p1 and p10 (an unrelated vector style, outlined text), 3Laurel p3 and Lot16 p3 (raster route).

Layered dark-painted ring, whole page (strips / rings / witnesses / chords / closures / seconds):

| Page | main | main + structural cap (scratch) | known-good `e93dbfe2e` |
|---|---|---|---|
| A110 | ABSTAINED, 0.2 s | 475 / 175 / 12 / 0 / 28 (22 stroke, 6 swing) / 61.7 s | 118 / 6 / 12 / 2 / 5 / 9.9 s |
| A500 | ABSTAINED, 0.1 s | 339 / 148 / 4 / 0 / 13 (9 stroke, 4 swing) / 23.6 s | 92 / 3 / 4 / 0 / 9 / 6.2 s |
| A501 | 254 / 128 / 2 / 0 / 6 | identical | 66 / 2 / 2 / 0 / 0 |
| A502 | 212 / 133 / 1 / 0 / 4 | identical | 51 / 2 / 1 / 0 / 0 |
| A503 | 309 / 141 / 2 / 0 / 6 | identical | 79 / 0 / 2 / 0 / 1 |

The 29,090 retained evidence strokes of A110 cost no pathological runtime (61.7 s for a 109,354-row page).

**1.6 Chords.** The segmented producer finds the Maryborough black-polyline doors (A110 12, A500 4, A501 2, A502 1, A503 2 witnesses) but `propose_source_owned_doorway_chords` needs the swing interval inside ONE raw wall gap with an end within 0.18 pt. Measured nearest same-line gap misses on the post-`4285e133a` tree: 0.6 to 4.56 pt on A500-A503, or no same-axis gap. A110 had 2 chords at the known-good commit and 0 now, so that loss is a regression (`4285e133a`); A500-A503 had 0 chords at the known-good commit too, so there it is an old limitation. No tolerance was changed.

## 2. Inference

1. The cap regression is a counting-semantics change, not a performance need: evidence is documented as not wall, and the structural count reproduces the pre-`3ce1d9b18` value exactly, with no threshold taken from any page.
2. Restoring the cap does NOT restore the Nov 12 A110 ring (6 rings, 2 chords). `4285e133a` makes it 175 rings and 0 chords. "Restored" can only mean "no longer abstains at the cap".
3. In the canonical preview the same evidence strokes decide single pass versus tiles on A500 (20,400 against 11,596 structural); tiling fragments rings and hides doors that straddle a seam. The preview has no producer for the Maryborough door style, so it cannot show a chord whatever its tile frame.
4. Chords on A500-A503 need a gate analysis, not a looser tolerance.

## 3. Proposed change (shadow, no new authority)

**P1 (small PR, after your go).** In `pb_layered_wall_doorway_room_ring_shadow.py` only: one pure role function shared by the selector and a new `structural_native_primitive_count`; the dark-painted cap counts wall_support + opaque_fill primitives (green never, evidence never); same 20,000, same reason code; the selector's output triple stays byte-identical so every Acacia glazing closure keeps its evidence. Replace the two stale 118/6/2 real-source expectations by assertions that hold on both sides of `4285e133a` (not abstained at the cap, structural count 16,099, every ring path index in range, no area or commercial flag); the measured shape lives in this note, not in a test.

**P2 (stacked, needs D2-D4).** Preview tiles in the native frame using the validated frame helper of #4652 (not a second one); role-aware single-pass decision in the next builder's entry checks; default-off segmented producer and chord proposer in the viewport-aware builder, with `_merge_ring_results` carrying chords, witnesses and path ids and the cap reason of dropped tiles surfaced.

**P3 (separate).** Chord parent-gap gate analysis (measurement-only reason export first), the `4285e133a` chord loss on A110, the two 3Laurel contacts (unique jamb ownership, both wall sections), base-level and #4657 schedule evidence.

## 4. Tests for P1 (synthetic, no private data)

Exactly 20,000 structural primitives run, 20,001 abstain; 20,001 evidence-only strokes plus an in-budget wall set run and still close the room; 20,001 opaque fills abstain; green never counts; a compound row counts its items; selector output identical before and after on a mixed fixture (golden); the existing Acacia glazing fixtures pass with 20,001 evidence strokes added; input-order, translation and viewport-expansion invariance of the count; the two existing cap tests (`test_opt_in_never_truncates_more_than_20000_qualifying_source_graphics`, `test_20000_cap_counts_native_items_not_just_pdf_path_containers`) unchanged; default-off byte parity for callers that do not pass the option.

## 5. Benchmark observations that must not influence the implementation

The A110, A500-A503 counts, the 16,099 and 45,189 totals and the chord offsets are observations on the Maryborough original, used only to verify. No threshold, tolerance, count or sheet name enters code; the 0.18 pt chord tolerance is untouched; Q5446 appears only to show that unrelated upright pages do not move.

## 6. Decisions

D1 real-source tests as property assertions (recommended) or pinned to the post-`4285e133a` shape. D2 make the next builder's entry cap role-aware as its own PR (recommended). D3 P2 stacks on #4652 or waits for it. D4 no new evidence limit unless a measured superlinear cost appears. D5 chord gate work starts measurement-only. D6 Q5446 as the unrelated style.

## 7. Not claimed or not run

The owner-local release path (signed Lot16 and Maryborough retention) and the frozen four-project score were not run. Scratch trees `C:\Users\bryce\w37` (patches, discard with `git reset --hard origin/main`), `w38` (detached `e93dbfe2e`), `w39` (clean main, the "before" tree) and `w40` (mutation tree) are local only. Section 8 records what was built after "Yes, build P1".

## 8. P1 as built (24 Nov, after "Yes, build P1")

- **Change:** `pb_layered_wall_doorway_room_ring_shadow.py` only (+63/-23): `_source_wall_ink_role` (one decision per row: green, wall_support, opaque_fill, evidence, blank), `structural_native_primitive_count` (wall_support + opaque_fill primitives), the selector rebuilt on the role function (same triple, same rows, same indices), and the dark-painted cap counts the structural count against the same 20,000 with the same reason code. The footprint-first trace already counts wall-support rows only (`pb_external_footprint_first_trace.py:309-332`); P1 gives the layered ring the same evidence exclusion and keeps opaque fills counted, as before `3ce1d9b18`.
- **Tests:** `tests/test_layered_structural_primitive_cap_v1.py` (47). 33 of 47 fail on the unchanged code. The selector output equals a verbatim copy of the old selector on 8 seeded fuzz sets of 600 rows each; classification is idempotent over the selector, order and translation invariant, never mutates its input; exact boundary 20,000 runs and 20,001 abstains with or without 50,000 evidence primitives; the Acacia glazing fixture still closes its host gap with 20,001 evidence strokes added; original path indices are not renumbered (walls placed after 25,000 evidence rows keep indices 25,000-25,003). 21 of 21 single-line mutants killed by the new file. The two stale A110 real-source tests became property assertions (not abstained at the cap, structural count 16,099 against 45,189 counted, ring flags false, indices in range) plus one strict xfail that keeps the A110 chord loss (2 at `e93dbfe2e`, 0 since `4285e133a`) visible.
- **Blast radius (local corpus, 61 PDFs, 861 pages):** 309 pages abstained at the cap before; 217 after; 92 change from abstain to run (Maryborough 5 of 31: A110, A500 and indices 10, 13, 14; 3Laurel 2 of 18: indices 1 and 8; Lot16 0; 85 pages of 24 public sample PDFs). Classification idempotence broke on 0 pages.
- **Real pages, every field of the ring result compared (dark-painted option, before = clean main):** identical on the 8 pages whose decision does not change (Maryborough indices 20, 21, 24, 25, 26; 3Laurel indices 2, 5, 6). The 7 pages that change: ABSTAINED in 0.1-0.2 s before, CANDIDATE after in 3.4 to 58 s (A110 58.0 s: 475 strips, 175 rings, 12 witnesses, 0 chords, 28 closures; A500 21.7 s: 339 / 148 / 4 / 0 / 13; 3Laurel index 1 3.4 s, index 8 16.2 s). The heaviest page that now runs (72,699 rows, 127,648 counted primitives, 94% evidence) takes 14 s: no superlinear cost was found, so D4 stays "no new limit".
- **Still red on clean main, unchanged by P1:** 5 local-original tests (4 on 3Laurel, 1 Banksia) fail identically before and after. With the local Maryborough original the two rewritten A110 files give 41 passed and 1 xfailed (strict) in 134 s.
- **Local CI-equivalent checks:** route guard, the two source guards (26 tests), `ruff --select F821,F823`, compile of every touched file; 122 test files that touch the selector, the layered ring, the preview or the footprint trace: 2,491 passed, 73 skipped, 5 failed (the 5 above).
