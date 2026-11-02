# Claude lane: first-failing-gate census and ranked candidates (2026-11-02)

**Status.** Architecture report for review, per `AGENTS.md` ("First deliverable on a new change"). No code, test, workflow, threshold or truth file changes in this PR. It grants no authority and is not an input to any producer. Written after reading `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (sections 8, 11, 13) and `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`. Only counts and public module names appear here; no expected quantity, item id, or private drawing content was used.

**Request.** The owner asked for "the next 20 major implementations for accuracy". The evidence below supports six candidates, two of which are blocked on an owner decision and two of which sit in a module another lane owns. Padding the list to 20 would mean choosing work from a target instead of from a failing gate, which `AGENTS.md` point 4 forbids. The list is therefore short on purpose.

## 1. Observed repository behaviour

Command, run locally against the SHA-verified original Lot16 PDF on `main` `86c0193c1` (the same invocation as `.github/workflows/test-gptmax-lot16-host-frame-gpt1-gate.yml`, which needs `PYTHONPATH=.`):

`tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py --page-id 3` with the archived signed run and customer rows.

| Quantity | Count |
|---|---:|
| physical openings | 21 |
| authenticated hosts | 15 |
| complete whole-wall frames | 9 |
| signed area quantities retained | 8 |

First remaining gate per opening (`first_remaining_gate`): host unavailable 6, whole-wall frame unavailable 6, filling kind unproven 3, source figured pair unproven 1, width/height axis authority unproven 5. The five axis rows are already signed; that gate only decides a new GPT1 handoff, not their retained value.

Reason codes behind the host and frame gates (production seams named):
- Host unavailable, 6 openings: all carry `no_authenticated_host_wall_band` plus `raster_source_band_{left x5, right x1}_source_primitive_unmapped` (`pb_opening_host_binding_authority.py:3161`; shadow ledger `pb_g17_flank_w4_end_reach_shadow.py`).
- Host present, frame unavailable, 6 openings: `aligned_fragment_distinctness_unproven` x3 (unsigned), `connected_edge_unproven` x2 (signed), `aligned_opening_binding_unavailable` x1 (signed). Source: `pb_opening_host_frame_authority.py` lines 730, 744, 1248, 1256.
- So 3 of the 8 retained signed rows do not currently have a source-reproved whole-wall frame. They are retained values, not re-proved ones.

## 2. Inference (not observed)

- **Host and frame work alone moves no new Lot16 area item.** All 13 unsigned openings also fail the printed two-number pair test (`label.status == corroborated` with two positive dimension values). The census tool couples axis authority to that pair, so independent door-height routes are not measured here; that is GPT1's `kind_axis_shadow` territory. The consequence stands: opening a host or frame gate is necessary and not sufficient.
- The largest block to new Lot16 door areas is therefore a second axis, which the accuracy-levers document already routes to an owner decision (section 4: door-height convention under `USER_APPROVED`), not to geometry.

## 3. Ownership map

| Gate | Module | Active work found | Owner |
|---|---|---|---|
| host: raster band to source primitive | `pb_opening_host_binding_authority` | `pb_g17_flank_w4_end_reach_shadow` | GPT MAX |
| frame: connected edge / fragment distinctness | `pb_opening_host_frame_authority` | `pb_frame_unproven_pair_*`, `pb_whole_wall_frame_readiness_shadow`, open #4167 | GPT MAX |
| kind / axes | `diag_cursor_lot16_kind_axis_shadow` | existing shadow | GPT1 |
| rooms and finishes | GPT2 modules | rooms/finishes lane (the F.07 plan-frame shadow #3848 is Claude support only) | GPT2 |
| physical opening identity, source roles | `pb_physical_opening_authority` | merged #4148, #4158, #4160 | Claude |

## 4. Proposed candidates (ranked; each needs its own trace before code)

1. **Door-height decision memo, then a design-only approved-record schema.** First failing gate: no second axis for 13/13 unsigned openings. Needs the owner's decision (use the existing `USER_APPROVED` authority type with source, scope and approver recorded, or keep abstaining). No default value is implemented. Ceiling: bounded by the host, frame and kind gates that stay independent.
2. **Re-measure the Maryborough callout to strip to whole-aperture chain on current `main`.** The earlier "no whole-aperture CANDIDATE" result (fill masks, record_id collisions, clip polygons) was taken on 2026-10-31, before #4148, #4126 and #4160. Measurement only, no code, in my lane.
3. **Joint tag, leader and schedule ownership graph for framed windows** (playbook section 13, priority 4). Paint evidence is exhausted (S3 negative), so the next evidence is ownership by tag or schedule row. Shadow module, largest of the six; needs a trace of `resolve_hosted_opening_spans` and the tag extractors first.
4. **Independent exact-head review of open PRs that change host or frame authority**, against section 10 of the playbook. Concrete example: #4167 (ready for review) changes the raster centreline tolerance in `pb_opening_host_frame_authority.py` from `wall_thickness / 2 + allowance` to a fixed 1.0001 pt, with an end-to-end test on the Lot16 original and a mechanism derived from three named openings. Questions a review should answer: is the fixed tolerance rotation and scale invariant, was it chosen from a failure mode or from the target openings, and do signed outputs stay byte-identical (levers document point 6a). Comment-only; no approval claim.
5. *(MAX-owned; do not start without coordination)* Frame aligned-fragment distinctness, 3 openings. Zero new quantities alone, per section 2.
6. *(MAX-owned; do not start without coordination)* Host raster band to source primitive, 6 openings. Same.

## 5. Benchmark observations that must not influence implementation

The Lot16 counts above come from production receipts read after the producer, as in `#2807`. No expected quantity, tolerance or identity map was read. Opening ids and benchmark item ids are deliberately absent.

## 6. Untouched

`pb_physical_opening_authority.py`, every `pb_opening_host_*` module, workflows, tests, benchmark and truth files, and all committed signed outputs.

## 7. Stop for review

Proposed first step on approval: candidate 2 (measurement), then candidate 1 (memo to the owner). Candidates 3 and 4 follow only on an explicit go-ahead.

## 8. Follow-up status (same day)

- **Candidate 2 done (measurement).** Maryborough callout, strip and aperture chain re-measured on current main: unchanged since 2026-10-31, no regression from #4148, #4126, #4158 or #4160. Result and the `fontTools` setup trap are in the comment on this PR.
- **Candidate 4 done (comment-only review).** #4167 at head `9791293db`: two existing fail-closed tests fail at that head and in its own public run, the branch is 112 commits behind main, and the section 9 tests are missing. See the comment on #4167.
- **Candidate 1 drafted.** `claude_door_height_owner_decision_memo_20261102.md`. Finding: a height approval would move only 1 of 13 unsigned Lot16 openings today; the other 12 fail an earlier host, frame or kind gate.
- Candidates 3, 5 and 6 not started.
