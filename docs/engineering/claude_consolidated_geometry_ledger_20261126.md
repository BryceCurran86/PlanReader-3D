# Claude consolidated geometry release: ledger (26 Nov 2026)

One pull request for the ten speed tasks (owner work order #4764 7192370711, three-merge rule 7192384436) and the register areas assigned to Claude (`OWNER_100_AREA_RECOVERY_REGISTER_20261126.md` at 17914a59b). Draft; nothing here is a release claim. The one combined before/after check is recorded below.

## Profile used for C03-C07

One cProfile of one residential original on the combined branch with C01 and C02 only (1,071 s profiled, about 2.2x a plain run). It was the only profiling run. Profiled cumulative seconds of the targets: wall lineage copies 88, door-candidate detector 99, opening-width matching 34, room-edge checks 33, intersection splitting 17, structural opening enumeration 25 (already indexed), wall pair equivalence 45 (already bucketed).

## Ten tasks

| Task | State | Evidence |
|---|---|---|
| C01 text census reuse | built | `claude_schedule_binding_text_reuse_note_20261126.md`; one original before/after: 5 files identical |
| C02 sliding-door pair scan (app preview) | built | far-wall index; parity with the full scan over 600 generated sheets and edge cases; 7/7 single-line mutants caught; synthetic busy sheet 12.4 s to 0.85 s |
| C03 opening candidates | built | the door detector searches a parallel neighbour only from unmarked leaves; marked set equals every-pair testing over 400 clusters; v171 stays the oracle; 6/6 mutants caught; synthetic 0.22 s to 0.01 s. Structural enumeration unchanged (already indexed) |
| C04 footprint tracing | no change | about 1 s per drawing; decode sharing is AntiGravity A01 |
| C05 junctions and connectivity | built | wall lineage copied with the module's structure copier (parity with `copy.deepcopy`, including which tuples stay shared, over 3,000 structures; synthetic 0.84 s to 0.16 s per 40k copies); intersection sweep walks by position instead of slicing (20k segments: loop 0.48 s to 0.09 s). #4802's indexes not duplicated |
| C06 host matching | built | membership checked before pair classification (parity over 400 generated equivalences; 200k pairs 0.135 s to 0.019 s); opening-width matching reads the jambs once per opening (parity over 4,000 lines) |
| C07 room-ring assembly | built | plain-float shortcut for the room-edge check (parity over 40,000 shapes; 1.15 to 0.27 microseconds per check) |
| C08 recalculation after corrections | blocked | geometry dependency contract written; waits on MAX M02 |
| C09 historical geometry donors | audited | register table below; #4166 recovered (owner approved 26 Nov) |
| C10 geometry test speed, exclusive replay | done | the combined before/after check below; CI sharding is MAX M06/M07 |

Not done, found by the profile: the opening label step re-reads page words for every opening (about 2% of the profiled run; the C01 reuse pattern would apply).

Tests: the 168 test files that import a changed module: 3,589 passed, 5 skipped (17 of them need an original at its repository path and passed where it is present).
The 123 other test files of the register areas: 3,319 passed, 7 skipped; 2 fail the same way on `main` (the Banksia exterior-loop census and the pinned window candidate set of one residential original, both reported earlier).
With #4166 and its counted check: the 287 test files touching the opening or source-visibility code: 5,558 passed (10 that need an original rerun where it is present), 92 skipped, 3 xfailed.

## Current-main disposition (27 Nov, #4764 7200170458)

- `main` e9516390d changed only `vr-editor/` since this branch forked (4cbf46356): no Python change; this branch merges cleanly with it, with AntiGravity #4807 (0fd81c8294) and with #4806 (08a6b7ef8c).
- Combined tree #4807, then this branch, then #4806 (local, not pushed): the 399 test files touching changed code: 7,650 passed, 97 skipped, 3 xfailed, none failed (24 of them need an original at its repository path and passed where it is present). #4807's head has the same Python as the one tested.
- Semantics against `main`: the speed changes keep results (parity tests and identical outputs on four originals). One behaviour change: #4166, a cached raster opening proof no longer stays corroborated when its source changes; no output changed on the four originals.
- Donors kept on origin: `claude/page-scale-tie-order-20261017` (5196a42f19, for MAX scale) and `claude/vector-clip-group-scopes-20261017` (96e88fa289, reconciled into #4807).
- The stale pinned counts in two original workflows are left as they are.
- C08: `claude_c08_correction_dependency_contract_20261127.md`.

## Combined before/after check

`main` 4cbf46356 against this branch, all four originals through the all-source-role handoff, one run at a time, on one shared desktop. The first check (code 895568828) kept every output identical but showed one step repeatably slower: a brochure page in the Q5446 set, +40 s of 69 s profiled. Cause: the recovered #4166 check compared every raster receipt on every proof, so cost grew with the square of the page's primitive count. Fixed (b5e07b28e) by counting writes to the producer's receipt table; any other mapping is still compared entry by entry. The check below is a new after-side run of all four on the final code against the same before outputs.

| Original | Before (s) | Final code (s) |
|---|---:|---:|
| Q5446 | 94 (repeat 85) | 85 |
| Lot16 | 695 | 492 |
| 3Laurel | 408 | 320 |
| Maryborough | 904 | 727 |
| All four | 2101 | 1624 |

- All JSON outputs identical on all four originals (statuses, sealed receipts, summaries, customer rows); verified customer rows 65 before and 65 after.
- Peak private memory within 20 MB of `main` or lower on every role (largest rise: Maryborough, 0.5%); 3Laurel working set +123 MB.
- Timing caveat: my hub checks and a few short tests overlapped the before runs of the first two originals, so the 3Laurel (-22%) and Maryborough (-20%) figures are the cleanest.

## Register areas assigned to Claude

"Live" means the import closure of the benchmark handoff, the app, the PDF extractor or the source-trace preview on `main` 4cbf46356. It shows the code can run there, not that a given drawing reaches it.

| Rank | Scope | Live caller | Disposition so far |
|---:|---|---|---|
| 3 | External footprint | `pb_external_footprint_first_trace` (all), `pb_new_exterior_wall_preflight` (app, preview) | current; tests pass apart from the two noted above |
| 4 | Dark wall ink | `pb_layered_wall_doorway_room_ring_shadow`, `pb_structural_wall_ink_shadow` (all) | current; tests pass |
| 10 | Raster/vector walls | `pb_raster_source_wall_frame_projection` (all), `pb_new_raster_source_wall_trace` (app, preview) | `pb_raster_wall_network_authority` has no caller: blocked |
| 15 | Engine donor #4284 | none | closed unmerged research branch (60 files); needs per-function review before any recovery |
| 16 | Doorway closed rings #4230 | `pb_layered_wall_doorway_room_ring_shadow` | merged 2026-11-07, extended by #4763/#4772/#4773 |
| 17 | Wall connectivity | `pb_physical_wall_candidate_authority`, `pb_physical_wall_identity` | current; tests pass |
| 18 | Thickness, finished faces | thickness modules have no caller | blocked: no live consumer |
| 20 | Cavity slider | `pb_source_native_cavity_slider_jamb_shadow` (app, preview); #4386 merged | pocket host and jamb modules have no caller: partial |
| 21 | Garage closure | `pb_source_garage_door_footprint_continuity` (app, extractor, preview) | current; tests pass |
| 22 | Dual dwelling | `pb_source_dual_dwelling_opening_topology_shadow` (extractor) | current; tests pass |
| 23 | Sliding door hosts | `pb_source_sliding_door_footprint_continuity` (app, extractor, preview) | current; tests pass; C02 speeds it |
| 24 | G17 W2 ownership #4215 | donor not on main | closed unmerged; 16 new definitions absent; 3 donor test files cannot import |
| 25 | Disconnected frame veto #4186 | alternate path still in `_shared_host_frame` | closed unmerged; 6 of 29 donor tests fail on main; needs original replay |
| 27 | Opening source invalidation #4166 | `pb_physical_opening_authority` (all) | recovered in this release: on `main` a cached raster opening proof stays corroborated after a supporting receipt is removed or changed (9 of its 10 tests fail there; all pass here), with the receipt table's writes counted so the check is constant time |
| 28 | Door frame height | `pb_door_height_owner_gate_shadow` (all); #4211 merged | current; tests pass; default-off |
| 30 | Door ancestry #4153 | `pb_gpt2_original_source_geometry_bridge` (benchmark) | definitions on main; 22 of 369 donor tests differ: in the 20 behaviour cases main grants no quantity or authority (8 abstain with another reason, 12 offer a diagnostic material candidate where the donor abstained, including a mark on the room edge), 2 are stale test stubs. MAX 7194290495 accepts candidates as diagnostic only; reply 7194441147 |
| 35 | Schedule census | `pb_schedule_opening_instance_binding_authority` | C01, in this release |
| 42 | Local room geometry reuse | `pb_source_room_face_authority` | C07, in this release (room-edge check) |
| 51 | Wet/dry classes #4242 | module not on main | blocked: finished-face receipts unresolved (frame thickness, wall fill, external lining), per the archive note |
| 52 | Wet/dry receipts #4243 | module not on main | blocked on 51 |
| 61 | Open-plan boundaries | `pb_source_open_plan_room_ring_shadow` (extractor) | current; tests pass |
| 64 | Finished wall faces | `pb_external_footprint_inside_face_runtime` (extractor) | finished-face receipts blocked as in 51 |
| 85 | External/internal overlays | `pb_source_spatial_candidate_overlay` (app) | `pb_plan_edit_verified_vector_overlay` has no caller |
| 86 | Room/ceiling overlays | `pb_source_room_trace_acceptance_runtime` (extractor) | no ceiling overlay module found |
| 98 | Unpushed workspace code | inventory below | |

## Unpushed local Claude work (rank 98)

167 local `claude/*` branches; 13 older ones hold commits on no remote:
- On main under another commit: wall-height viewport blockers, schedule binding (#383), WallTopologyProducer, wall-height hotfix (superseded by item 17), three architecture notes, wall-end jamb caps (#4763).
- Merge-only or local check: Murera research merge, #4268/#4269 local check.
- Parked on purpose: raster/vector ink ownership shadow (94% of the raster pool was re-rendered vector ink).
- Never merged, no caller: completeness-manifest and cross-view registration contracts (September). Narrower main modules cover openings completeness and cross-sheet registration.
- Stashes: one research stash marked do-not-delete (canonical wall room model); one benchmark report regeneration.

Uncommitted changes in 142 Claude worktrees (line endings ignored; definitions checked against `main`):
- Superseded or on `main`: preview and ring work-in-progress trees, glyph mapping, text clip polygon, scale block bar, review-1275, the canonical wall room model, the dictionary-flags fix, and the figured-unit mismatch fix (`main` abstains too, with a different reason code: 84 of 86 of its tests pass).
- Not on `main`, for the owning lane (not changed here):
  - Clip association with non-clip groups (`pb_vector_geometry_v130.py`, AntiGravity A01): 4 of 23 tests fail on `main`. Pushed as donor `claude/vector-clip-group-scopes-20261017` (96e88fa289); AntiGravity reports it reconciled into #4807.
  - Page-scale mapper (MAX scale): returns FIRM for a hand-built VALID record of any non-title-block source, and for USER_APPROVED with a blank approver; 20 of 72 tests fail on `main`. `main`'s resolver does not itself build such records for unknown sources, and `approve_page_scale_calibration` has no caller, so no live path was found. Pushed as donor `claude/page-scale-tie-order-20261017` (5196a42f19) for MAX.
- Kept as parked research, not recovered: Ghazi raster wall network evidence, finish-definition shadow, U1 lineage tracing script.
