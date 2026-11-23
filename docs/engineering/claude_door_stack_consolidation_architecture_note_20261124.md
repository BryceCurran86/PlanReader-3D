# Door stack consolidation: one current-main candidate (MAX item 2) - architecture note

Date: 2026-11-24 (Brisbane). Status: PROPOSAL. Nothing here is merged, pushed, posted or wired. Planned branch (local until approved): `claude/door-integration-candidate-20261124`, cut from the #4649 head `29c73bbfc5ceaa9acfc813bec33d48dc36d2a8e3` (main `ba4696b8ed8d150bdcac7bb96b89e60c851cba06`). Owner order: #2608 comment 7100270347 item 2 ("put the door code on one current-main candidate"); MAX's integration audit #4135 comment 7100241880 item 4 ("one production owner only"). Shadow only; no authority, quantity or score is touched.

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md` (every section of the live file: main `ba4696b8e` plus #4649's all-pages section), `docs/AI_ENGINEERING_PLAYBOOK.md` (all), `CANONICAL_TRACE_ROUTE_CONTRACT_20261120.md`, `ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `AUTONOMOUS_COMPLETION_QUEUES_20261110.md` (execution rules and the handoff format), `OWNER_ALL_PAGES_SOURCE_EVIDENCE_RULE_20261121.md`, `.github/workflows/ci.yml` (the step list), my three door reports of 21 and 22 Nov, hub comments 7091696157, 7090154226, 7092735539, 7100241880 and #2608 comment 7100270347. Not re-read for this note: `wall_topology_observability_architecture.md`, `planreader_wall_room_topology_spec.md`, `planreader_public_tender_benchmarks.md` (this change touches neither the W2-W10 stack nor the extractor/evaluator boundary).
- **Functions traced:** contract `pb_opening_two_wall_contact_tags.tag_opening_to_two_wall_sections`, `tag_native_segmented_doorway_chords`, `_point`, `_vector_at_contact` and #4655's `_finite_source_number`; ring wiring `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings` (dark-painted branch) and `LayeredRoomRingResult.source_two_wall_opening_tags`; chord producer `pb_source_segmented_door_swing_shadow.propose_source_owned_doorway_chords`; core `pb_source_door_wall_end_sections.build_contract_inputs`, `_group_end`, `_anchor_touches`; front end `pb_source_internal_door_two_wall_tags.tag_internal_door_marks`, `_receipt`; mark producers `pb_source_internal_door_completeness_shadow.inspect_source_internal_door_completeness` and `pb_source_internal_swing_room_barrier.detect_source_internal_swing_room_barriers`; compiler `pb_door_row_evidence_compiler_shadow`; base proof `pb_door_base_level_scope_shadow.prove_door_bases`; route `pb_new_source_trace_preview.source_native_trace_preview` and `scripts/check_canonical_trace_route.py::verify_route_contract`.
- **Authority boundaries crossed:** none raised. Every output carries `physical_host_authorized=False`, `measurement_authorized=False` and, in the front end and compiler, all seven authority flags False by construction. A tag is topology only (AGENTS.md all-pages rule); a closure chord connects room topology only; `READY_FOR_EXISTING_ISSUER` is evidence for the authority-promotion review, not an issuance.
- **Expected abstentions, predicted before any test:** a zero-width chord (new); a non-list/tuple chord or drawing collection (new, one UNRESOLVED tag); a jamb row that does not meet its wall end within the contract tolerance; two sections competing at one contact; a doorway at the face of a passing wall; a wall that runs through the other contact; a straight gap whose ends are not collinear.
- **Files that stay untouched:** `pb_planreader_pdf_extractor.py`, `pb_new_source_trace_preview.py` and `pb_next_wall_ring_preview.py` (item 3), `pb_source_internal_swing_room_barrier.py` and `pb_source_swing_door_footprint_continuity.py` (the producer defect in section 1.6 is a separate change), the layered ring module beyond the 27 lines it already carries from #4638, W10, JobHub, `benchmarks/frozen_holdout/full_plan_v2/**`, `scripts/check_v2_truth_separation.py`, the 20,000-primitive cap and the 2.5 pt snap.

## 1. Observed repository behaviour

**1.1 The stack (GitHub, 24 Nov).** Linear: #4638 is inside #4654, which is inside #4655; #4649 contains #4638 but not #4654/#4655.

| PR | Head | State | Adds on top of the previous |
|---|---|---|---|
| #4638 (GPT1) | `a64993940` | draft, DIRTY vs main | the contract `pb_opening_two_wall_contact_tags.py` (295 lines), 27 lines of wiring in the layered ring module, 2 test files, the all-pages owner rule (doc and AGENTS.md section) |
| #4654 | `3cef11844` | draft, DIRTY | 2 commits: coerced native wall-end coordinates fail closed |
| #4655 | `e5b8e497a` | draft, DIRTY | 10 more: oversized integers, malformed collections, per-invocation native-line cache, zero-width chord |
| #4649 (this lane) | `29c73bbfc` | draft, mergeable; public CI run 45209583114: `test (3.13)` and `test (3.14)` success, 21 of 25 checks success, 4 skipped | wall-end core, internal-door front end, door row compiler, base-level proof, 3 reports |

The three DIRTY PRs conflict with main in `AGENTS.md` only (tested for #4655 with `git merge-tree`: one conflict, the same hunk I resolved in #4649; #4638 and #4654 carry that hunk). No other open PR touches the door-stack files.

**1.2 The 12 guard commits** change two files (+180/-20): `pb_opening_two_wall_contact_tags.py` and its test file. `_point` and the chord adapter reject a native number whose conversion overflows; the adapter returns one UNRESOLVED tag `source_chord_collection_invalid` for a non-list/tuple `drawings` or `chords`, rejects a non-mapping chord, rejects a zero-width chord (`lo >= hi`, was `lo > hi`), and validates each native single-stroke row once per invocation in a cache keyed by native index (never shared across calls; a rejected row is cached as `None`).

**1.3 Reachability.** There are two ring builders with the same name. `pb_new_source_trace_preview` imports `build_layered_wall_doorway_room_rings` from `pb_next_wall_ring_preview` (viewport-aware, no `dark_painted_wall_source` option, no segmented-swing producer). #4638's wiring is in `pb_layered_wall_doorway_room_ring_shadow` (no viewport option), inside the `dark_painted_wall_source` branch. `scripts/check_canonical_trace_route.py` only checks the call NAME, so it passes for either module, and `CANONICAL_TRACE_ROUTE_CONTRACT_20261120.md` names the shadow module. The shadow builder is reached with the option ON from the wall-role/junction shadow and two tools; the two live composition modules (`pb_live_canonical_room_composition`, `pb_live_physical_net_wall_integration`) forward an opt-in keyword `layered_dark_painted_wall_source` (default False) to it, and no non-test caller passes True. The new field `source_two_wall_opening_tags` has no reader anywhere. My core, front end, compiler and base proof are imported by nothing in production.

**1.4 Two front ends, one contract.** The ring adapter reads single-stroke wall ends named by a chord (section ids `native-wall-end:<n>`); my core reads wall-end GROUPS of any convention (id `stable_contract_id("native_wall_end_section", scope + sorted paths)`; ordered by the group's lowest path id, so swapping first and second changes nothing).

**1.5 Experiments run for this note (scratch tree, nothing committed or pushed).**
- Merging #4655 into #4649: `git merge-tree` clean; the scratch merge changes exactly the two files above.
- The same 71 test files I used for the #4649 merge (guards, the 19 ring tests, the AGENTS.md readers, the tests main changed): 2,022 passed, 8 skipped, 12 failed. The 12 are the symlink-privilege nodes of `tests/test_gpt3_original_source_preflight.py` that also fail on clean main (WinError 1314). #4649 alone: 2,003 passed, same 12, same 8 skips.
- 3Laurel page 3, strict internal door inventory plus two-wall tags, run in both trees: byte-identical output (14 marks, 12 tagged, 2 unresolved).
- Layered ring with `dark_painted_wall_source=True` on real pages, every result field compared (the addresses of the private record seal are normalised; the same tree twice is identical): identical whole-result digests, before and after, on 3 Maryborough inset pages, 1 page of the 3Laurel set, and the Maryborough floor plan with two option sets (that page abstains, see 1.8). Runtime unchanged.
- Every one of those real runs yields 0 segmented-swing chords, so the ring adapter that #4655 hardens has been exercised on synthetic inputs only; no real page has fed it a chord.
- The repository's own real-source tests for the door and dark-painted-wall producers, run with the local Maryborough original (they skip in public CI): 6 files, 70 passed and 2 failed in BOTH trees. The same 2 fail on clean main (see 1.8).

**1.6 The two unresolved 3Laurel internal marks (counts and gate names only).** Both are hinged swings. Both receipts come from path 1 of `detect_source_internal_swing_room_barriers` (the exterior-bridge matcher run with the internal layer pattern and a 0.75 pt cap tolerance); path 2 (short-stub recovery) refuses a jamb or host row claimed twice, paths 1 and 3 do not. The two receipts claim one jamb row between them. First failing gate in my core, for both: `opening_edge_does_not_meet_wall_end`: none of the recorded jamb rows meets either host end within the contract's 0.18 pt tolerance (one row meets a host end along the wall axis but misses the host's thickness by 0.28 pt, which is inside the detector's own 0.75 pt cap tolerance; every other pair misses by 20 pt or more on at least one axis). On a local visual reading (not a measurement, not published) each door appears to abut a perpendicular wall strip on at least one side, the class my 21 Nov report keeps as "reported, not tagged" because the contract needs a section that ends at the contact.

**1.7 First-gate counts already measured (public reports, counts only).** 3Laurel page 3, 14 internal marks: wall sections tagged 12, unresolved 2 (above); with the opt-in glyph text trust width 14 of 14 and head 14 of 14; base proof 3 of 14 (8 `closure_not_bounded_by_two_distinct_rooms`, 2 `door_matches_competing_closures`, 1 `level_text_not_corroborated`); 3 rows READY_FOR_EXISTING_ISSUER, nothing issued. Maryborough, 28 doors: 0 compile; the first failing gate for all 28 is door code to symbol identity; amenity insets A500 to A503 hold 9 swing doorways, 5 tagged.

**1.8 A finding on main that the door stack did not cause (same producer, same pinned original, known-good against current).** The dark-painted layered ring on the Maryborough floor plan (page 7 of the 31-page set, 109,354 native rows) runs at `e93dbfe2e` and abstains at the 20,000-primitive cap (`unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport`) from `3ce1d9b18e0bead25df2863321de944c81cfe1ee` (18 Nov, "fix(acacia): close three collinear host gaps from source jamb/glazing evidence") through current main. That commit makes `_source_wall_ink_candidate_drawings` retain every unfilled non-green stroke as doorway/glazing evidence: the set the cap counts grows from 15,937 rows (16,099 primitives) to 45,021 rows (45,189 primitives); green exclusion is unchanged (64,333 rows). Result on that page at `e93dbfe2e`: CANDIDATE, 118 wall strips, 6 rings, 12 segmented-swing witnesses, 2 chords, 5 closures (2 swing doorways, 3 stroke closures); at `3ce1d9b18` and on main: ABSTAINED, every count 0. This is why the two real-source tests of 12 and 13 Nov fail on main, why the whole-page ring finds no door closure there, and why the ring adapter above has never seen a real chord. (An earlier commit, `111001522` of 13 Nov, made the closure count of the same test stale, 2 expected and 5 found, by design.) Public CI cannot see either failure: both tests skip without the private original, so only an owner-local run shows them.

## 2. Inference

1. Consolidation is a merge plus proof, not new geometry: the candidate tree is the #4649 tree plus a 2-file delta. The risk sits in the three documented behaviour deltas and in the one live-reachable seam (the ring wiring), not in the core or compiler.
2. The guards matter before item 3: when the dark-painted and segmented-swing producers move into the viewport-aware builder, the tag call becomes reachable from the canonical preview, and an unguarded exception there would break the preview. Today the seam is reachable only from shadow code and an opt-in keyword.
3. The cap regression of 1.8 is upstream of every door result on the Maryborough floor plan: until the cap counts the wall-candidate set (as it did) and not the retained evidence strokes, no door closure, chord or tag can come from that page, with or without this stack. It is a candidate cause for part of MAX's item 3.
4. The two unresolved marks are a producer-receipt defect (a jamb row owned by two receipts), not a drawing fact and not a core failure; the core refuses correctly. Showing both true wall sections for them needs correct owned anchors and, where a door abuts a perpendicular wall, a section that ends at the contact: neither exists today.
5. Two ring builders and a guard that checks a name are the deeper duplication behind item 3; this note does not resolve it.

## 3. Proposed change (shadow, no new authority)

1. **One integration branch.** From the #4649 head, `git merge --no-ff e5b8e497a260c4b87042114edf1eb24417f5f015` (#4655; contains #4654 and #4638). No rebase, no force-push, nothing pushed to #4638, #4654 or #4655. One definition of the contract file remains (the #4655 version, a superset). Both parent SHAs are recorded in the merge message.
2. **Differential tests (tests only):** `tests/test_door_stack_consolidation_differential_v1.py` with goldens generated from the "before" trees (section 4), plus a cross-front-end agreement test on the domain both front ends accept, an AST pin that no production module reads `source_two_wall_opening_tags`, a pin that tags carry no width or area field, and a seeded fuzz that never raises and always returns flags False.
3. **Fixes only for what a failing differential proves**, each as its own commit with a test that fails first. None is expected.
4. **Real-data replay (counts only, local originals):** the ring field comparison of 1.5 on every page that yields a chord, the 3Laurel tag run, and, if the owner-local benchmark is available on this head, signed Lot16 and Maryborough byte retention (otherwise reported UNVERIFIED, not claimed).
5. **Handoff (needs your yes to post):** one proposed integration head and per-door first-gate counts on #2608 and #4135 in the "Every completed handoff" format (producer SHA, dependency heads, functions changed, tests run and skipped, source roles and positive/negative status, retention, remaining reason, next claimed task). The candidate is also the "throwaway integration branch" of the ACCURACY_LEVERS rule 7: open it as a draft "do not merge" PR so path-triggered CI runs on the exact result; MAX may merge it, or merge the four PRs in order and compare `git rev-parse HEAD^{tree}`.

Not in the candidate: #4657 (item 4), #4662, the producer fix, any face-contact vocabulary and the cap regression (section 7), anything in item 3 or 4.

## 4. Differential matrix and predicted outcome (written before running it)

| Case | Entry | Predicted before vs after |
|---|---|---|
| valid straight gap, hairline wall ends | adapter | identical tags, reasons, section ids, order |
| contacts reversed (left and right swapped) | adapter, core | mirrored tag, same id set; the core's output identical |
| the same chord twice | adapter | two tags in index order, identical content, no de-duplication |
| zero-width chord | adapter | DELTA: `source_chord_receipt_invalid` (was tagged or a junction) |
| infinite, NaN or oversized-integer widths | adapter | identical (invalid); the contract's `_point` no longer raises |
| non-list/tuple collections | adapter | DELTA: one UNRESOLVED `source_chord_collection_invalid` |
| perpendicular ends meeting (junction, corner, angled) | contract, core | identical `WALL_JUNCTION`, `ANGLED_OPENING` |
| cavity-slider pocket (two lips), solid strip, outlined wall | core | identical `STRAIGHT_GAP` |
| solid pier between two openings | contract, core | identical: two tags share the pier section, none spans it |
| doorway at the face of a passing wall | core | identical abstain (`..far_thicker..` or no wall end) |
| two sections competing at one contact | contract | identical, ids sorted |
| translation, rotation, mirroring | all | identical decisions and section ids |
| uniform scale | all | identical above the 0.18 pt absolute contract tolerance; documented limit |
| a wall end drawn as one stroke or split in two | adapter, core | adapter retains ambiguity; core tags (a group); no front end invents a section |
| two calls with the drawings changed between | adapter | the second call sees the change (the cache is per invocation) |

Receipt order is the chord index for the adapter and `(symbol_kind, mark path ids, entry id)` for the front end; source path ids are carried unchanged. The goldens pin both.

## 5. Validation plan

Synthetic positives and look-alike negatives per section 4; metamorphic and order invariance; deterministic replay and stable ids; no-mutation of inputs; a proof that default behaviour of every live caller is unchanged (the new field has no reader, so the only observable change is the three deltas, each pinned); single-line mutation testing of the new tests; `ruff --select F821,F823`, the five CI guards, and the exact-head Python 3.13 and 3.14 run before any claim. Real-data checks as in 3.4.

## 6. Benchmark observations that must not influence the implementation

None was used. The 3Laurel and Maryborough counts above are development-drawing observations that revealed failure modes (a shared jamb row; no tag-to-symbol rule). No threshold changes: the 0.18 pt endpoint tolerance is the contract's, the 6.0 thickness-to-edge ratio is the core's scale-free rule, and `lo >= hi` is a validity rule. Expected quantities, tolerances and the frozen identity maps stay out.

## 7. Decisions for the owner

1. **Shape.** (a) New branch from #4649 plus #4655, as in section 3 (recommended: conflict-free, old PRs untouched); (b) wait for the other Claude lane to rebase #4654/#4655 on main and merge them in order; (c) one more stacked PR on #4655.
2. **Hub claim first.** Post a [CLAIM] on #4135 (door-stack consolidation; the files; "I will not push to #4638, #4654 or #4655"; ask the other lane to freeze their heads) before building, so no competing consolidation starts. Needs your yes.
3. **The two 3Laurel marks.** (a) Report the exact gates and stop (recommended for item 2); (b) also add the cross-receipt exclusivity of path 2 to path 1 of `detect_source_internal_swing_room_barriers` as a separate PR: it changes the live-reachable internal-door inventory (hinged hosted marks 8 to 6 on this plan, both marks become NEEDS_HOST) and does not by itself tag them; (c) design a face-contact vocabulary in the contract for doors that abut a passing wall (a contract change, GPT1's file).
4. **Ids.** Keep both section-id vocabularies (recommended: no consumer reads either, and changing the ring ids would break #4638/#4655 tests).
5. **Goldens.** Commit the differential goldens as test data (recommended) or keep the comparison as a one-off script.
6. **The cap regression of 1.8.** (a) A separate small PR, not in this candidate, that makes the cap count the wall-candidate set again while keeping the evidence strokes available to the closure searches (recommended: it restores the two failing real-source tests and the A110 door producer, and is the likeliest first step of item 3); (b) fold it into item 3; (c) leave it. It is the other Claude lane's and the Acacia work's territory as much as mine, so say who owns it.

## 8. Coordination

Only #4638, #4654, #4655 and #4649 touch the door-stack production files. #4657 (item 4, A600 schedule reader) and #4662 (junction prefilter) are separate. #4654/#4655 and #4638 are owned by other lanes: their branches are never pushed to; the candidate pins exact SHAs and I re-merge if either moves, saying so. MAX merges; nothing here is merged by me.
