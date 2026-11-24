# Why the A110 Office has no ring of its own, and the smallest general repair: a leak-or-merge trace of the protected rooms (MAX directive 7146013608, Claude item 2) - architecture note

Date: 2026-11-25 (Brisbane). Status: PROPOSAL. Note first: no repository code changed, no function claim posted, nothing pushed. Local branch `claude/a110-room-boundary-leak-note-20261125`, cut from origin/main `bd91d5614` (its ring builders are byte-identical to the `3ddfe562d` tree the measurements ran on; the range only touches `vr-editor` files). Orders: the owner's "Yes, start A110", after [#4135 comment 7146013608](https://github.com/BryceCurran86/PlanReader-3D/issues/4135#issuecomment-7146013608) item 2: "start with the A110 rooms needed by the protected finishes, show the source wall or threshold that causes the ring to leak or merge, then claim and implement the smallest general repair ... check the change against 3Laurel's accepted openings and room boundaries and a different plan format."

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` (headings re-checked today; sections 7, 8, 9, 11 and 13 read earlier this session for the P4a note); the P4a census note and PR #4705; the hub directive above; the p11-to-p7 floor correspondence record (#2723); the module and function lists of `pb_layered_wall_doorway_room_face_scope_shadow.py` and `pb_source_maryborough_physical_room_boundary_shadow.py`; the closure loop of the layered builder (`:2328-2440`).
- **Functions traced** (main, via the P4a spies on the real builder, no repository edits): `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings` (strip collection, `_gaps`, the closure loop and `_append_closure`, the sibling-face step, the free-space and ring rule with `_CLOSING_PT = 0.03`); the consumer `pb_layered_wall_doorway_room_face_scope_shadow.layered_ring_scope_overrides` -> `layered_ring_room_face_scope`, which keeps a CANDIDATE ring only when `figured_box_pair_count(...) == 1`.
- **Authority boundaries crossed:** none raised. A ring is candidate topology: no room, area, finish, opening, host or quantity authority. Room names on the page are used only as verification fixtures to say which ring a room sits in; they are not inputs to any rule below.
- **Expected abstentions:** a room whose perimeter leaks has no ring and no reason code; a ring touched by an unresolved collinear gap is ABSTAINED (`open_wall_gap_unresolved`); a ring the room-face scope sees with zero or several figured pairs is dropped there. Sealing a ring therefore makes a room eligible, it does not accept it.
- **Files that stay untouched by this note:** all code. A later build would touch one builder module and add tests (section 3); the preview's fork, the closers, the strip collectors, the room-face scope, `pb_new_source_trace_preview.py`, the door stack (#4638, #4649, #4665), W2-W10, `benchmarks/frozen_holdout/full_plan_v2/**` and `documents/sources/*.pdf` stay untouched.

## 1. Observed repository behaviour (originals read in place; counts, widths and ring areas only; no coordinates)

**1.1 What the protected records need from A110.** MAX's seven protected Maryborough records are three floor areas (Office, Food Prep, Cold Room), two FT3 floor finishes (Office, Food Prep) and two ceiling linings (Office grid ceiling, Food Prep FPB ceiling). MAX says the physical areas already agree, so the A110 question is which wall-bounded ring owns each room, and what bounds it.

**1.2 Method.** The P4a capture (`tools/diag_ring_leak_census.py`, `capture_layered_builder`) on the page's raw `get_drawings()` rows, which is what `layered_ring_scope_overrides` reads. Room labels come from the page's own native words (same unrotated frame as the rows) and only place a point inside a free-space part. Free-space parts are the domain minus the builder's barrier; a neck is the erosion radius at which a room's part separates from the others (neck width = twice the radius); closing, extension and propagation runs add rectangles to the builder's own barrier inputs and recount rings by its own rule (rings matched across runs by 90 percent mutual area overlap). Two builder states: main, and the draft #4683 head `2003868ca` (door-owned strokes no longer mint wall strips).

**Table 1. The layered builder on A110 (page index 6).**

| State | Strips | Raw gaps (collinear) | Closed | Unresolved collinear | Rings (candidate / abstained) | Aperture groups |
|---|---|---|---|---|---|---|
| main | 475 | 433 (44) | 28 | 34 | 171 / 4 | 345 (59 hold two or more gaps; largest 6; 22 hold a closed gap) |
| #4683 head | 461 | 413 (44) | 23 | 36 | 171 / 3 | 327 |

On main the four abstained rings are held open by 1, 1, 1 and 2 unresolved collinear gaps (classes: parallel strokes 2+, perpendicular strokes, perpendicular strokes, partial stroke plus perpendicular strokes).

**Table 2. Where each labelled room sits (free-space part, ring status).**

| Room | main | #4683 head |
|---|---|---|
| Cold Room | own part, candidate ring | own part, candidate ring |
| Freezer | own part, candidate | own part, candidate |
| Laundry | own part, abstained | own part, abstained |
| Airlock | own part, abstained | shared big part |
| PWD | shared big part | own part, candidate |
| **Office** | **shared big part** | **shared big part** |
| M-AMB, F-AMB | shared big part | shared big part |
| **Food Prep**, Wash Up, Dry Store | shared big part | shared big part |

The big part is one enclosed free-space region of about 1.1 million square points that holds seven of the labelled rooms and is ABSTAINED (`open_wall_gap_unresolved`) on both states. It does not touch the exterior: the problem is merging, not leaking to outside.

**1.3 The Office (protected): a wall-bounded room that merges through a closed doorway's end.** Erosion separates the Office from everything else at radius 2.0 pt, so every connection is a neck narrower than 4.0 pt (3.3 median strip thicknesses; the wall band is 6.2 pt thick). The neck is a single place: the end of the Office's own doorway, between the doorway's closure rectangle and the perpendicular wall, where a wall stub shorter than the wall thickness carries no strip (the wall there is hatch under a white fill). The doorway itself is closed on main. Its aperture is one physical opening seen as four raw gaps: two closed twins (one collinear, one not) and two unclosed members of the same aperture whose intervals reach the wall corner; the widest unclosed member extends about 10 pt past the closed ones (a 5.3 pt stub plus the perpendicular wall's own thickness). PWD and M-AMB show the same family of necks (2.8 pt and 4.1 pt): PWD at its own doorway's end, M-AMB along a 58 pt long thin channel beside its partition wall.

**1.4 The #4683 head makes the Office's leak wider, not narrower.** There the Office doorway's aperture is three raw gaps, all unclosed (two carry a source door witness, one is perpendicular strokes); the chord gate sees competing parents and abstains, so the Office connects through the doorway's full width (it separates only at erosion 30 pt; 20 pt keeps it joined). PWD improves there (its doorway's closure runs 56.0 pt instead of 52.1 pt, and it gets its own ring). Of 327 aperture groups exactly one holds a source door witness and no closed member: the Office doorway.

**1.5 Food Prep (protected): not a leak, and not a wall-ring room.** Food Prep stays in one free-space part with F-AMB at every closing radius tried (0 to 8 pt, up to 6.7 median thicknesses), and with Wash Up and Dry Store at every erosion radius up to 30 pt (a connection wider than 60 pt), so no strip pair separates them. The drawing shows wall evidence on its west and north sides and a partition line to its south that stops short of the east with an unclosed raw gap at its end; I did not establish what bounds it on the east, and I did not find a wall that closes it. The finish page gives its floor as figured dimension strings beside the label. So no ring repair of the kind below produces a Food Prep ring; what would is a different authority (section 2, point 3).

**1.5b The two seams the builder already has (so the repair extends them rather than adding a path).** (a) `_append_closure` (`:2342`) pads every closure's barrier rectangle along the run by `_STROKE_PAIR_THICK_MIN` = 1.2 pt, with the comment that frame cracks beside a sourced opening are thinner than a wall and are not rooms. The A110 necks are 2.3 to 4.4 times that pad: thinner than the 6.2 pt wall band, beyond the pad. (b) The sibling-face step (`:2405-2433`) resolves an unresolved gap only when it is collinear, has the orientation of a closed gap, has both ends within `_STROKE_PAIR_FACE_PT` = 0.35 pt of it and overlaps its band; its comment says competing or differently spanned gaps are left unresolved. The Office aperture's unclosed members are excluded by exactly that rule (one is non-collinear, the widest spans 10.6 pt further).

**1.6 Cold Room (protected): already has its ring** (own candidate part on both states).

**Table 3. Candidate repairs, measured as counts (a measurement, never a rule).** Rings recounted by the builder's own rule after adding the stated rectangles to its barrier inputs. "lost" = base rings with no 90 percent partner afterwards; "new" = rings with no partner in the base.

| Repair | A110 | A500 | A501 | A502 | A503 | 3Laurel p3 | 3Laurel p2 |
|---|---|---|---|---|---|---|---|
| Base rings | 175 | 148 | 128 | 133 | 141 | 66 | 4 |
| G. close the finished barrier by 2 median thicknesses | 184 (6 lost, 15 new) | - | - | - | - | 88 (15 lost, 37 new; held open 6 to 23) | 5 (1 lost, 2 new) |
| B. extend every closed closure by one band thickness at both ends | 180 (0 lost, 5 new) | 0 / 0 | 0 / 0 | 0 / 0 | +3 new | 69 (5 lost, 8 new) | 0 / 0 |
| B2. B only for closures at least 3 band thicknesses long, only where the extension meets barrier | 180 (0 lost, 5 new) | 0 / 0 | - | - | +3 new | 67 (1 lost, 2 new) | 0 / 0 |
| **L2. aperture propagation: add the unclosed members of an aperture that already has a closed member, when the member lies within the closed interval widened by 2 band thicknesses** | **176 (0 lost, 1 new = Office, candidate)** | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0 (13 closures added)** | 0 / 0 |

Closures added by L2 per page: A110 11, A500 10, A501 5, A502 3, A503 4, 3Laurel p3 13, p2 0. The Office ring it yields is 28,163 square points with no unresolved collinear gap touching it, so the builder would not abstain on it. The result sits on a plateau: widening by 3, 4 or 8 band thicknesses gives the same counts of unchanged, lost and new rings on A110, 3Laurel p3 and A503; widening by 1 adds closures (10 on A110) but no ring, because it does not reach the wall corner. On the #4683 head L2 changes nothing (the Office aperture has no closed member there).

**1.7 What the rejected variants do (why G, B and B2 are not the smallest safe repair).** G fuses real structure on 3Laurel p3 (23 percent of its rings change, 6 held-open rings become 23); on A110 the rings it loses are thin wall-cavity slivers, but the page it hurts is the one MAX asked me to check. B carves rooms on 3Laurel p3 where a closed gap is thick and a few points long (a 21 pt band closed over 1.1 pt, a 17 pt band over 0.5 pt), so extending by the band thickness walks into the neighbouring room. B2 removes those but still splits one 3Laurel p3 ring (53 by 61 pt into two) through a slit of the same family: that may be a correct repair, but it needs 3Laurel's accepted room list before I can say so, and it does not touch the protected set.

## 2. Inference (not observed; stated so it can be challenged)

1. The Office is lost to the representation of one physical opening, not to a missing door. The builder closes the clear opening and leaves the wall stub between the opening and the perpendicular wall open, because the stub is hatch plus white fill and no existing collector turns it into a strip. The same opening is also present as wider raw gaps whose intervals include the stub; closing only some members of an aperture leaves the stub's slit open. The right unit of closure is the aperture, the unit the P4a census already groups.
2. On the #4683 head the same aperture is entirely unclosed because the chord gate treats three overlapping raw gaps of one opening as competing parents. That is the same defect seen one layer up: one opening counted as several parents. The fix there is the aperture rule inside the gate, not a second closure path (playbook section 7).
3. Food Prep needs a different authority (a finish-region authority bounded by wall faces where they exist and by figured dimension witnesses elsewhere), not ring repair. Treating it as a leak would bend the ring rule to something rings cannot represent.
4. Rings 1.1 million square points wide are not rooms. Even after the Office is sealed the big part still holds the other six labelled rooms; those are separate leaks (PWD and M-AMB: the necks above; F-AMB: its doorway is unclosed on main; Food Prep, Wash Up, Dry Store: no wall between them).

## 3. Proposed change (build only after review; shadow, default off)

**P1 (the smallest general repair; one claim).** Extend the existing sibling-face step (`:2405-2433`), not a parallel path: add an explicit-boolean keyword `aperture_complete_closures: bool = False` (validated the way `wall_end_stroke_closures` is) which, when on, lets that step also resolve an unresolved gap that (a) shares an aperture group (overlapping band and interval, the census definition) with at least one closed gap, (b) has the same orientation (collinear or not), and (c) lies within the closed members' interval widened at each end by at most two band thicknesses of the closed members: one wall stub, which is shorter than the wall is thick, plus the thickness of the wall it meets. It reuses `_append_closure`, so each added closure gets a stable `closure_id`, appears in the result's `closures` and in the rings' `edge_owner_ids`, and its barrier rectangle is padded exactly as today. Flag off: the result is byte-identical (to be proved on the 16-page set used for #4694). Nothing else changes. This deliberately relaxes the step's "differently spanned gaps stay unresolved" comment inside one aperture and one wall stub; section 6 asks the owner to confirm that.

**Exact function claim (to post before any edit):** `pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings` (new default-off keyword and the sibling-face block) and nothing else in that module; new tests `tests/test_layered_aperture_complete_closures_v1.py`. Files not touched: everything listed in section 0.

**P2 (follow-up claim, after #4683 integrates).** Make the P3a/#4683 chord gate count overlapping raw gaps of one aperture group as one parent (the existing `parents_share_one_geometry` idea, widened from identical geometry to one aperture), so the Office doorway on that head closes through its own door witness. Measured on A110 (head `2003868ca`): closing that one group gives the Office a candidate ring of 28,163 square points (the ring count goes from 174 to 176) and PWD keeps its own ring; whether any other ring moves is not yet measured.

**P3 (not proposed now).** Stub sealing for necks no aperture rule reaches (PWD, M-AMB; not protected). It needs a door-frame evidence gate (B2's one 3Laurel split is the open question) and 3Laurel's accepted room list.

**P4 (hand-off, no code).** Food Prep is not a wall ring. Once P1 is built I hand Antigravity and MAX the Office's finished faces and its threshold as shadow evidence (ring edges with their owning strips, the doorway aperture interval and the closures used), and tell them in writing that Food Prep needs a finish-region authority.

## 4. Tests (required before any build merges; AGENTS.md "Required tests for every geometric hypothesis")

Synthetic positives: a door in a wall with a stub, a closed member and a wider unclosed twin gives a room ring; the same with the closed member on the other end; two doors in one wall. Look-alike negatives: a thick band closed over a hairline gap (a column joint) does not propagate; a 750 pt gap that merely overlaps the aperture does not propagate; an unclosed member wider than the allowed widening does not propagate; two nearby apertures stay two groups. Ambiguity and conflict: twins at different bands, a group with two closed members at different intervals, an aperture whose only closed member is itself ambiguous. Metamorphic: translation, rotation by 90 degrees, uniform scale. Invariance: input order, segment splitting, unrelated content, viewport expansion. Deterministic replay with stable ring identifiers; no-mutation of the rows and of the closure list; flag off byte-identical on the 16-page set. Real-page regression, counts only: A110, A500-A503, 3Laurel p3 and p2, Q5446 (raw-row layered run abstains at the structural cap), plus the existing 3Laurel accepted-opening and room-boundary tests that need the owner-local original. Single-line mutants of the helper with every survivor classified.

## 5. Benchmark and fixture observations that must not influence the implementation

Room names and positions were used only to say which ring holds which room. The Office ring that L2 yields (28,163 square points, about 142 by 201 pt) and the Cold Room ring (about 223 by 363 pt) agree with the registered FT3 boxes within a wall thickness at 1:50; I did not use those boxes or any expected quantity to choose the widening: the value 2 comes from the physical argument (a stub shorter than the wall is thick plus the thickness of the wall it meets), the plateau from 2 to 8 shows the counts are not sensitive to it, and the Office page's own minimum (1.7) is reported only as a check. Signed Maryborough quantities and the seven protected records were not read.

## 6. Decisions for the owner and MAX

- **D1.** Build P1 now (independent draft, flag off, one function claim)? It fixes the Office on main only; it does nothing once #4683 integrates, which is why P2 is a separate claim after it. It also relaxes the sibling-face step's "differently spanned gaps stay unresolved" rule inside one aperture; please confirm that is acceptable.
- **D2.** Whether P1 should also mirror into the preview's fork. I recommend no: the preview's A110 has no single-closure leak and its wall evidence is the bigger lever (L1 in the census note).
- **D3.** Who owns the Food Prep finish-region authority (wall faces on two sides, partition, figured chain)? I recommend Antigravity or MAX; it is not a ring problem.
- **D4.** Whether PWD and M-AMB (not protected) justify P3 and its 3Laurel check.

## 7. Not claimed or not run

No code, claim, PR or hub post exists for this change. Not run: the owner-local 3Laurel accepted-opening and room-boundary tests, Lot16, Q5446 (its layered run abstains on raw rows), any signed replay, CI. Counts are from the owner-local originals and are not reproducible from the repository alone. `tools/diag_ring_leak_census.py` (draft #4705) reproduces Table 1; the label-to-part mapping, the necks and Table 3 used local scratch scripts that are not committed. The Office ring is a candidate: whether the room chain accepts it depends on `figured_box_pair_count == 1`, which needs a source producer for trusted native dimensions on that page and is unmeasured (stage 3 of the census plan). The protected finishes themselves (FT3 floors, ceilings) are Antigravity's lane; nothing here changes an issuer, export or customer row.
