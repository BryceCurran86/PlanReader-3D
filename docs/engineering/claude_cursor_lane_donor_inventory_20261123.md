# Cursor lane takeover: donor inventory and port plan (23 Nov 2026)

Report only; no code changed. Observed on `main` `3c23a5ece`, #4638 head `a649939404`. Public identifiers and counts only (PR numbers, module names, hub comment ids); no private source content, coordinates or customer data. This is item 1 of the ten-item order (#4135 comment 7082388932, #2608 comment 7082410634). AGENTS.md says to stop for review after this report.

## 1. Compliance

- **Read:** AGENTS.md; `docs/AI_ENGINEERING_PLAYBOOK.md` (sections 1, 5, 6, 11, 12, 13 and the section list); hub comments 7079120625 to 7082652907 (including the donor collision audit 7082492417); the #4537, #4443 and #4549 issue text and the #4537 transfer notice (comment 7082414800); title, body, file list and diff of every PR in section 3.
- **Functions traced (entry points, by signature only):** `tools/run_canonical_source_native_preview.py::run_preview` -> `pb_new_source_trace_preview.source_native_trace_preview`; `pb_external_footprint_first_trace.trace_external_footprint_first`, `bound_native_drawings_to_footprint`, `refine_external_footprint_against_wall_ink`, `_polygon_has_self_intersection`. Their bodies were not read: every port PR traces its own quantity first.
- **Authority boundaries crossed:** none. Nothing in this report is wired, issued, sealed or scored.
- **Untouched:** all production modules, `benchmarks/frozen_holdout/full_plan_v2/**`, `documents/sources/*.pdf`, `scripts/check_v2_truth_separation.py`, W10 defaults.
- **Not done:** no private original opened and no replay run. CI states below are public check-run summaries; the private jobs fail before runner steps (MAX, #4135 comment 7082446798), so a red private job says nothing about the code.
- **Method:** for every file a PR changes, compare three blobs (merge base, PR head, main); `git merge-tree` for merge cleanliness; a heuristic scan of added non-comment lines for project names, long hex literals, page-number selectors and quoted door or room codes. Reproducible with git alone. The scan is a list of flags for a human, not a verdict.

## 2. Observed: what main already carries from the Cursor lane

Cursor's ten tasks (#4537) were merged as shadow or review-only modules (#4540, #4552, #4555, #4561, commit `e0130c180`). The order's own warning stands: ticked boxes are not proof of signed customer acceptance, so what is on main still has to be proven on the originals.

| Cursor task | On main (per PR bodies and the module list; behaviour not re-verified here) | Order item |
|---|---|---|
| 01 exterior perimeter graph | `pb_source_native_exterior_perimeter_graph_shadow` (#4540); `pb_source_native_exterior_endpoint_authority_shadow` (`09b5b5818`); `pb_source_native_exterior_edge_path_ownership` (`c16090eaf`, the content of the closed #4349) | 2 |
| 02 inside-face footprint; garage in, porch out, party wall internal | `pb_source_inside_face_thermal_envelope_shadow` (#4540); `pb_source_external_footprint_inside_face_start_shadow` (#4552); `pb_external_footprint_inside_face_runtime`; `pb_source_garage_door_footprint_continuity` (`97a6f6d01`); `pb_source_fabricated_wall_box_closure_runtime` (#4555, wired into the footprint runtime and the PDF extractor) | 2, 3 |
| 03 internal hinged and cavity door census | `pb_source_internal_door_completeness_shadow`, `pb_source_internal_swing_room_barrier` and `pb_source_native_cavity_slider_jamb_shadow` (`353902bbb`); the quarter-swing kind and identity-partition shadows (#4639). The 11-15 donor stack (#4322 to #4343) and #4473 were never merged | 6 |
| 04 cavity and sliding closure, topology only | `pb_source_native_door_topology_closure_shadow` (#4540) | 6 |
| 05 unmatched external opening census | `pb_source_external_opening_instance_census_shadow` (`e0130c180`) | 10 |
| 06 W2/W4 lineage and reversals | `e0130c180` carries #4504's production and test changes byte for byte; the index change #4526 is not merged | 4, 9 |
| 07 finished interior faces, false-wall veto | `pb_source_finished_interior_face_recovery_shadow` (`a05df3bb5`); runtime wiring `pb_source_interior_face_open_plan_runtime` (#4561) | 8 |
| 08 open-plan room rings | `pb_source_open_plan_room_ring_shadow` (`a05df3bb5`); `pb_layered_wall_doorway_room_ring_shadow` | 8 |
| 09 opening-host correlation index | `pb_source_opening_host_correlation_index_shadow` (`a05df3bb5`); the performance PRs #4553 and #4566 are not merged | 9 |
| 10 live-trace diagnostics | `pb_source_native_live_trace_diagnostics_shadow` (`a05df3bb5`); `tools/run_canonical_source_native_preview.py` | 9 |

Owner acceptance for the geometry items is still the open issue #4443: the two fabricated wall boxes gone and genuine alcoves kept, doorway closures that separate rooms but are never walls or wall area, closed non-overlapping room rings where evidence permits, a named missing gap or host for every failed region.

## 3. Observed: donors that are not on main

Blob classes: IDENT = main already has the PR's exact file; NEW = file absent on main; CLEAN = main has not touched the file since the merge base, so the PR change ports as it is; DIVERGED = main changed it too.

| PR | State | What it changes | Against main | Public CI | Universal-gate flags | Proposed |
|---|---|---|---|---|---|---|
| #4450 | open, not draft | Cursor and AntiGravity private-source replay scripts (an executor handoff, "not proof the plan is fixed") | 4 of 6 files IDENT, 1 test NEW (45 lines), 1 script DIVERGED and conflicting | one test job failed, one cancelled | 1: an example command naming a project PDF in a script | do not port: not geometry, and the order says to avoid the old private-source runner; the owner or MAX may close it |
| #4504 | draft | W2/W4 source-revision lineage and wall reversals | the 2 production and 2 test files are IDENT (landed as `e0130c180`); only `.github/workflows/original-w2-w4-source-retention.yml` (35 lines) is NEW | one private job failed | none | no code to port; the workflow is MAX's call; the originals #4415 and #4417 are closed |
| #4526 | draft | W4 filled-strip owner index and collapsed-snap witness grouping: `pb_physical_wall_candidate_authority.py` +44/-16, parity test +171 | CLEAN, merges cleanly | five failed and one cancelled, all private or original-source jobs | none | do not re-implement; show identical candidate and ABSTAIN sets on the originals, then hand MAX the protected parity |
| #4553 | draft | opening-support containment index | same two files as #4566 | six private-job failures | none | superseded by #4566 (its own body says so) |
| #4566 | draft | `pb_physical_opening_authority.py` +33/-6, test +196 | CLEAN, merges cleanly | six private-job failures | none | same handling as #4526 |
| #4573 | draft | reject a false site or roof enclosure in the first trace: `pb_external_footprint_first_trace.py` +118, test +62 | production file DIVERGED, conflicts with main (main added a self-intersection guard, #4577) | all green (15 passed, 7 skipped) | none | re-port onto main; see section 4 |
| #4638 | open, draft (GPT1) | two source-traced wall sections per opening, review only: `pb_opening_two_wall_contact_tags.py` +295, two test files +420, `pb_layered_wall_doorway_room_ring_shadow.py` +27, an owner-rule document, AGENTS.md +30 | 11 commits, 6 files: 4 NEW, 2 CLEAN, merges cleanly | all green (21 passed, 10 skipped) | none | not a donor: the door branch is stacked on it; it stays SHADOW until two genuine wall sections, frame and metric, and issuer lineage are independently authenticated (hub audit 7082492417) |
| #4391 | closed | walk the unbounded exterior face around both dwellings (+830) | 2 files NEW, 2 DIVERGED, 1 CLEAN, merges cleanly | n/a | none | evaluate under item 3: its own body shows it abstains on the dual-dwelling original (branch not unique) |
| #4302, #4349, #4356 | closed | stacked Cursor branches | heads are ancestors of main | n/a | n/a | nothing to port |
| #4257 | closed | Lot16 source-role receipt | conflicts with main | n/a | none | MAX's lane |
| #4322 to #4343 | closed | the 11-15 door stack | the top of the stack differs from main in 30 of 33 files (8 NEW, 15 CLEAN, 7 DIVERGED, 3 IDENT) | n/a | 1: a project name in `pb_source_unique_swing_opening_host_shadow.py` | A is on main (#4639); B (in-swing width) is a pushed branch without a PR; C: the single-wall host nomination is obsolete under the two-wall contract (#4638), keep only its read-only gate diagnostics; D (cased openings) hard-codes a layer name, defer; E (2100 rule) is a fallback only after the owner's "scorable rows" decision |

Open PRs owned by others that this lane consumes and does not edit: #4638 (two-wall opening tags, GPT1), #4647 (footprint trace evidence pair, GPT1), #4642 (green-hatch unique owner, GPT1), #4646, #4648 and #4522 (MAX), #4511 (external door safety guards), #4525 (page guard: already on main and in #4647 per GPT1).

## 4. Inference

- Little of the Cursor lane needs porting. The unique unmerged production code is #4526, #4566 and #4573, plus the door stack remainder (B, C diagnostics, D, E) and #4391 to evaluate. The larger job is proving what is on main on the originals against the #4443 acceptance, not writing it again.
- #4526 and #4566 are blocked on protected original parity, not on code. Local replays on the originals can show that candidate and ABSTAIN sets and source path ids are identical before and after, with real runtime and memory, but that is not signed protected parity.
- #4573 flips a live-path outcome from CANDIDATE to ABSTAIN on a class of footprints, so it needs MAX's retention and promotion review even though it only withholds. Its diff has six absolute constants (25 pt minimum edge, 20 pt minimum segment, 0.2 pt axis tolerance, 0.3 darkness cutoff, 0.2 stroke-weight floor, 512-item cap) next to three relative ones (0.18 of the shorter side, the 65th percentile of observed stroke weights, 25 percent coverage). The re-port must justify or make relative each absolute value; none may come from an expected quantity.
- Item 5 is mechanical now: the door branch sits on #4638's current head and 294 related tests pass.

## 5. Proposed order (each step: its own trace and note first; shadow only; no commercial change)

1. Door branch (item 5): rebased onto #4638 `a649939404` (done, tests and CI guards pass); open as a draft PR once the vehicle is chosen (section 6).
2. #4573 re-port (items 2 and 3): resolve the conflict with #4577, audit the absolute constants, source-neutral positive and negative tests, metamorphic and held-out checks. Expected abstentions: unchanged for every case the veto does not touch; the new `external_footprint_unverified_native_wall_edges` only where a long contour edge has no independent native wall ink.
3. #4526 and #4566 (item 9): identity evidence on the originals, no code change, then to MAX. #4566's file is GPT2-owned, so nothing there is edited and no third support index is written until a single producer-owner handoff exists (hub audit 7082492417).
4. Maryborough doorways (item 7): the four still untagged stop at `wall_ends_not_collinear_across_the_gap` (2), `opening_edge_does_not_meet_wall_end` (1) and a wall end on one side only (1). Work inside the wall-end core, source-relative, no door codes or page coordinates. Expected abstention: a gap whose two ends share no face with the opening stays ABSTAIN. The schedule reader and tag-to-symbol registration stay GPT2's: consume, do not duplicate.
5. 3Laurel doors (item 6): donor piece B (needs a rebase onto main, because #4639 landed as one commit), the two hinged doors whose jamb rows are not at wall ends, slider host corners; host and frame binding for two sections is MAX's.
6. Items 4, 8, 9 and 10: one architecture note each, after steps 1 to 5. Item 8 consumes #4642's hatch ownership instead of duplicating it.

## 6. Decisions and risks for the owner

- **Merge policy.** The order says to merge after exact-head dual-Python, security, P1 and source and customer parity; the standing rule is draft PRs with MAX merging. I keep drafts and do not merge unless told.
- **Vehicle for the door branch.** A PR into `main` now carries #4638's 11 commits and gets exact-head CI; a PR into #4638's branch gets no CI; waiting delays the evidence. Recommendation: draft PR into `main`, retargeted automatically when #4638 lands.
- **#4549.** The closed 30-task Cursor list (all boxes ticked; only #4552, items 01 to 05, is identifiable as shipped) is not named by the order, so it is out of scope unless the owner says otherwise.
- **Hourly Claude automation.** The hub says one is enabled; I have not seen it. One editor per branch.
- **Protected parity.** MAX reports the authorised protected device offline; nothing in this lane can claim signed or customer parity until a protected replay runs.
- **Producer ownership.** The hub audit (7082492417) says #4553 and #4566 are GPT2-owned and asks for one producer-owner handoff before anyone changes the opening-support functions. This lane only gathers evidence on #4566 until GPT2 hands the producer over.

## 7. Benchmark observations that must not influence implementation

The numbers quoted on the hub (zero of 28 doors customer-ready, nine swing witnesses with five two-wall tags, Lot16 page 3 abstaining, seven protected IDs not retained by #4646) are failure-mode observations only. No threshold, tolerance or rule in this plan is derived from them, from a filename, a project name or an expected quantity.

## 8. Update after steps 1 and 2 (23 Nov 2026, later)

- Step 1 is done: the door branch is draft PR #4649 (head `16c743941`, stacked on #4638).
- Step 2 changed: #4573 was not ported verbatim. Draft PR #4650 adds a shadow native-edge support check and a default-off flag instead; its note `docs/engineering/claude_footprint_native_edge_support_20261123.md` holds the measurements. The donor guard compared visible-space polygons with unrotated native rows on rotated sheets, vetoed on missing evidence and ignored filled strips.
- New finding for item 2, not fixed: the footprint polygon is in visible page space, while `refine_external_footprint_against_wall_ink` and `bound_native_drawings_to_footprint`, as `tools/run_original_footprint_first.py` calls them, compare it with unrotated native rows. On the 8 candidate pages of one rotated original the scoped window selects 19,459 rows against 49,836 when derotated. Proposed next change: derotate in that chain, with parity on rotated sheets. It becomes a step after step 2 in section 5.
- The hub audit 7082492417 is already reflected in section 6 (producer ownership of the opening-support functions).
