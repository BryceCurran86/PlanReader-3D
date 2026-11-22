"""Shadow base-level proof: both adjoining floors are on the finished-floor slab.

Synthetic scenes only: no PDF, project name, file name or benchmark value is an input. The proof rests on five links
(one closure, two rooms, a level statement, no mark in either room, sheets that agree on how many marks exist) plus
text-integrity trust; each link has its own named gate and its own negative test.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import math
import random
import re
from pathlib import Path

import pytest

import pb_door_base_level_scope_shadow as mod
from pb_door_base_level_scope_shadow import (
    GATE_COMPETING_CLOSURES,
    GATE_INPUT_INVALID,
    GATE_NO_CLOSURE,
    GATE_NO_PLAN_TEXT,
    GATE_NO_STATEMENT,
    GATE_NOT_RECONCILED,
    GATE_NOT_TWO_ROOMS,
    GATE_ROOM_MARKED,
    GATE_SCOPE_INVALID,
    GATE_TEXT_RAW,
    PROOF_REASON,
    DoorClosure,
    DoorTopologyInput,
    RoomRegion,
    TextBlock,
    TextWord,
    is_level_statement,
    level_marks,
    prove_door_bases,
    statement_corroborated,
)
from pb_door_row_evidence_compiler_shadow import (
    SOURCE_PLAN_LABEL,
    TEXT_CORROBORATED,
    DoorWitnesses,
    HeadWitness,
    SOURCE_DOCUMENT_NOTE,
    WallConnectionWitness,
    WidthWitness,
    compile_door_rows,
)

SCOPE = ("a" * 64, "revision-a")
PLAN = "3"
SHEET = "6"


def square(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def words(text, x, y, *, size=10.0, corroborated=True, line=0):
    out = []
    for i, token in enumerate(text.split()):
        out.append(TextWord(token, (x + i * size * 4, y, x + i * size * 4 + size * 3, y + size), corroborated, line))
    return tuple(out)


def block(page, block_id, text, x, y, *, corroborated=True):
    return TextBlock(page, block_id, words(text, x, y, corroborated=corroborated), (f"obs-{page}-{block_id}",))


def W(text, bbox, corroborated=True, line=0):
    return TextWord(text, bbox, corroborated, line)


def B(page, block_id, *ws):
    return TextBlock(page, block_id, tuple(ws), (f"obs-{page}-{block_id}",))


# Rooms A | B share the closure c1 (door d1); room C | D share c2 (door d2); E is a lone room at c3 (an outside door).
ROOMS = (
    RoomRegion("room-a", square(0, 0, 100, 100), ("c1",)),
    RoomRegion("room-b", square(100, 0, 200, 100), ("c1",)),
    RoomRegion("room-c", square(0, 200, 100, 300), ("c2",)),
    RoomRegion("room-d", square(100, 200, 200, 300), ("c2",)),
    RoomRegion("room-e", square(300, 0, 400, 100), ("c3",)),
)
CLOSURES = (DoorClosure("c1", (11, 50)), DoorClosure("c2", (21, 51)), DoorClosure("c3", (31, 52)))
DOORS = (
    DoorTopologyInput("d1", (10, 11, 12)),
    DoorTopologyInput("d2", (20, 21, 22)),
    DoorTopologyInput("d3", (30, 31, 32)),
)
STATEMENT = block(SHEET, "s1", "SERVICE SLAB STEPPED DOWN 100mm FROM FFL", 500, 500)
SHEET_MARK = block(SHEET, "m1", "100 STEP", 600, 600)
PLAN_MARK_OUTSIDE = block(PLAN, "p1", "100 STEP DOWN", 700, 700)         # in no room
PLAN_TEXT = block(PLAN, "t1", "LIVING", 20, 20)                         # a plain label inside room-a
BLOCKS = (STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, PLAN_TEXT)


def prove(**kw):
    args = dict(plan_page_id=PLAN, doors=DOORS, closures=CLOSURES, rooms=ROOMS, blocks=BLOCKS)
    args.update(kw)
    return prove_door_bases(SCOPE, **args)


def door(review, door_id):
    return next(d for d in review.doors if d.door_id == door_id)


# ---------------------------------------------------------------------------------------------------------------------
# the positive proof
# ---------------------------------------------------------------------------------------------------------------------


def test_a_door_between_two_unmarked_rooms_is_proven_to_sit_on_the_finished_floor_slab():
    review = prove()
    d1, d2 = door(review, "d1"), door(review, "d2")
    assert d1.verified and d1.reason == PROOF_REASON and d1.closure_id == "c1" and d1.room_ids == ("room-a", "room-b")
    assert d2.verified and d2.room_ids == ("room-c", "room-d")
    assert review.reason_codes == () and review.statement_pages == (SHEET,) and review.plan_mark_count == 1
    assert review.sheet_mark_counts == ((SHEET, 1),)
    assert d1.evidence_observation_ids == tuple(sorted({"obs-6-s1", "obs-3-p1"}))
    assert d1.marks_in_rooms == 0 and d1.next_step == mod.NEXT_STEP


def test_a_door_to_the_outside_or_open_space_is_not_an_interior_door_and_abstains():
    d3 = door(prove(), "d3")
    assert not d3.verified and d3.reason == GATE_NOT_TWO_ROOMS and d3.room_ids == ("room-e",)


# ---------------------------------------------------------------------------------------------------------------------
# topology gates
# ---------------------------------------------------------------------------------------------------------------------


def test_door_closure_ownership_is_exact_and_never_nearest():
    none = DoorTopologyInput("d1", (900, 901))
    assert door(prove(doors=(none,)), "d1").reason == GATE_NO_CLOSURE
    two = DoorTopologyInput("d1", (11, 21))      # its paths belong to two different closures
    assert door(prove(doors=(two,)), "d1").reason == GATE_COMPETING_CLOSURES
    assert door(prove(doors=(DoorTopologyInput("d1", ()),)), "d1").reason == GATE_NO_CLOSURE


def test_a_closure_must_bound_exactly_two_distinct_rooms():
    one_room = tuple(r for r in ROOMS if r.room_id != "room-b")
    assert door(prove(rooms=one_room), "d1").reason == GATE_NOT_TWO_ROOMS
    three = ROOMS + (RoomRegion("room-x", square(0, 400, 50, 450), ("c1",)),)
    d1 = door(prove(rooms=three), "d1")
    assert d1.reason == GATE_NOT_TWO_ROOMS and len(d1.room_ids) == 3
    none = tuple(RoomRegion(r.room_id, r.polygon, ()) for r in ROOMS)
    assert door(prove(rooms=none), "d1").reason == GATE_NOT_TWO_ROOMS
    # a room that lists the same closure twice is still ONE room
    twice = (RoomRegion("room-a", square(0, 0, 100, 100), ("c1", "c1")),) + ROOMS[1:]
    assert door(prove(rooms=twice), "d1").verified


# ---------------------------------------------------------------------------------------------------------------------
# document gates
# ---------------------------------------------------------------------------------------------------------------------


def test_without_a_level_statement_the_absence_of_a_mark_means_nothing():
    review = prove(blocks=(SHEET_MARK, PLAN_MARK_OUTSIDE, PLAN_TEXT))
    assert review.reason_codes == (GATE_NO_STATEMENT,)
    assert all(d.reason in (GATE_NO_STATEMENT, GATE_NOT_TWO_ROOMS) for d in review.doors)
    assert door(review, "d1").reason == GATE_NO_STATEMENT


def test_a_missing_plan_page_text_abstains():
    review = prove(blocks=(STATEMENT, SHEET_MARK))
    assert review.reason_codes == (GATE_NO_PLAN_TEXT,) and door(review, "d1").reason == GATE_NO_PLAN_TEXT


def test_raw_statement_or_raw_mark_text_never_verifies():
    raw_statement = block(SHEET, "s1", "SERVICE SLAB STEPPED DOWN 100mm FROM FFL", 500, 500, corroborated=False)
    assert door(prove(blocks=(raw_statement, SHEET_MARK, PLAN_MARK_OUTSIDE, PLAN_TEXT)), "d1").reason == GATE_TEXT_RAW
    raw_mark = block(PLAN, "p1", "100 STEP DOWN", 700, 700, corroborated=False)
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, raw_mark, PLAN_TEXT)), "d1").reason == GATE_TEXT_RAW
    raw_sheet_mark = block(SHEET, "m1", "100 STEP", 600, 600, corroborated=False)
    assert door(prove(blocks=(STATEMENT, raw_sheet_mark, PLAN_MARK_OUTSIDE, PLAN_TEXT)), "d1").reason == GATE_TEXT_RAW


def test_a_word_the_text_authority_could_not_read_inside_a_room_blocks_that_room():
    unreadable_inside = block(PLAN, "t1", "L1VING", 20, 20, corroborated=False)
    review = prove(blocks=(STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, unreadable_inside))
    assert door(review, "d1").reason == GATE_TEXT_RAW and door(review, "d2").verified    # d2's rooms hold no such word
    unreadable_far = block(PLAN, "t1", "L1VING", 800, 800, corroborated=False)
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, unreadable_far)), "d1").verified
    unreadable_on_other_sheet = block(SHEET, "t9", "L1VING", 20, 20, corroborated=False)
    assert door(prove(blocks=BLOCKS + (unreadable_on_other_sheet,)), "d1").verified   # another sheet's text is not this plan


def test_every_sheet_that_marks_level_changes_must_agree_with_the_plan_on_how_many():
    extra_plan = block(PLAN, "p2", "100 STEP DOWN", 750, 750)
    assert prove(blocks=BLOCKS + (extra_plan,)).reason_codes == (GATE_NOT_RECONCILED,)     # plan 2, sheet 1
    extra_sheet = block(SHEET, "m2", "100 STEP", 650, 650)
    assert prove(blocks=BLOCKS + (extra_sheet,)).reason_codes == (GATE_NOT_RECONCILED,)    # plan 1, sheet 2
    no_plan_marks = (STATEMENT, SHEET_MARK, PLAN_TEXT)
    assert prove(blocks=no_plan_marks).reason_codes == (GATE_NOT_RECONCILED,)              # plan 0, sheet 1
    # a statement-only sheet (no marks of its own) has nothing to reconcile
    statement_only = (STATEMENT, PLAN_MARK_OUTSIDE, PLAN_TEXT)
    assert prove(blocks=statement_only).reason_codes == () and door(prove(blocks=statement_only), "d1").verified
    # the statement may sit on the plan page itself
    on_plan = (block(PLAN, "s1", "ALL SLAB STEPPED DOWN 100mm FROM FFL", 800, 800), PLAN_MARK_OUTSIDE, PLAN_TEXT)
    review = prove(blocks=on_plan)
    assert review.statement_pages == (PLAN,) and review.reason_codes == () and door(review, "d1").verified


# ---------------------------------------------------------------------------------------------------------------------
# the marks themselves
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("room_x,room_y,door_id", [(30, 50, "d1"), (150, 50, "d1"), (30, 250, "d2")])
def test_a_level_mark_inside_either_adjoining_room_blocks_the_door(room_x, room_y, door_id):
    inside = block(PLAN, "p9", "STEP", room_x, room_y)          # one word: its centre is (x + 15, y + 5)
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    review = prove(blocks=BLOCKS + (inside, sheet))
    d = door(review, door_id)
    assert not d.verified and d.reason == GATE_ROOM_MARKED and d.marks_in_rooms >= 1


def test_a_mark_in_one_room_blocks_only_the_doors_that_open_into_it():
    inside_c = block(PLAN, "p9", "50 STEP DOWN", 20, 220)
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    review = prove(blocks=BLOCKS + (inside_c, sheet))
    assert door(review, "d1").verified and door(review, "d2").reason == GATE_ROOM_MARKED


def test_a_mark_on_a_room_boundary_counts_as_inside():
    # word centre exactly on the shared wall x = 100
    on_wall = B(PLAN, "p9", W("STEP", (95.0, 40.0, 105.0, 50.0)))
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    assert door(prove(blocks=BLOCKS + (on_wall, sheet)), "d1").reason == GATE_ROOM_MARKED
    just_out = B(PLAN, "p9", W("STEP", (-12.0, 40.0, -0.002, 50.0)))
    assert door(prove(blocks=BLOCKS + (just_out, sheet)), "d1").verified


def test_concave_rooms_and_winding_order_do_not_matter():
    l_shape = ((0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100))
    rooms = (RoomRegion("room-a", l_shape, ("c1",)), RoomRegion("room-b", tuple(reversed(square(100, 0, 200, 100))), ("c1",)))
    in_notch = block(PLAN, "p9", "STEP", 70, 70)       # centre (82, 75): inside the bounding box but outside the L
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    only_two = (DoorTopologyInput("d1", (10, 11, 12)),)
    review = prove(rooms=rooms, doors=only_two, blocks=BLOCKS + (in_notch, sheet))
    assert door(review, "d1").verified
    in_arm = block(PLAN, "p9", "STEP", 10, 70)         # centre (22, 75): inside the L's vertical arm
    assert door(prove(rooms=rooms, doors=only_two, blocks=BLOCKS + (in_arm, sheet)), "d1").reason == GATE_ROOM_MARKED


# ---------------------------------------------------------------------------------------------------------------------
# vocabulary (policy), with look-alikes
# ---------------------------------------------------------------------------------------------------------------------


def blk(text, page=PLAN):
    return block(page, "b", text, 0, 0)


@pytest.mark.parametrize("text", ["100 STEP DOWN", "step", "STEP,", "(STEP)", "STEPPED", "SUNKEN SLAB", "RAMP 1:14",
                                  "TO STAIR", "STEPS", "RAISED FLOOR", "DEPRESSED"])
def test_level_change_words_are_marks(text):
    assert len(level_marks([blk(text)])) >= 1


@pytest.mark.parametrize("text", ["STEPHEN", "FOOTSTEP", "PREPARED", "RAMPART", "STAIRWELL", "UPSTEP", "OVERSTEPPED",
                                  "LIVING", "100", "", "FFL"])
def test_look_alike_words_are_not_marks(text):
    assert level_marks([blk(text)]) == ()


def test_a_statement_pairs_a_level_word_with_a_floor_datum_and_is_not_itself_a_mark():
    assert is_level_statement(blk("SLAB STEPPED DOWN 100mm FROM FFL"))
    assert is_level_statement(blk("raised 50 above affl"))
    assert not is_level_statement(blk("100 STEP DOWN"))
    assert not is_level_statement(blk("STEPHEN 100 FROM FFL"))               # look-alikes never define a statement
    assert not is_level_statement(blk("FOOTSTEP 100 FROM AFFL"))
    assert not is_level_statement(blk("FFL T.B.C."))
    assert not is_level_statement(blk("TOWEL RAIL HEIGHT 1200 AFL"))
    assert not is_level_statement(blk("HANDRAIL TO STAIRS 1000 AFFL"))       # a stair note defines no annotation rule
    assert len(level_marks([blk("HANDRAIL TO STAIRS 1000 AFFL")])) == 1        # so it is a MARK: a stair is a level change
    assert len(level_marks([blk("STAIR")])) == 1
    assert level_marks([blk("SLAB STEPPED DOWN 100mm FROM FFL")]) == ()
    assert len(level_marks([blk("SLAB STEPPED DOWN 100mm FROM FFL"), blk("100 STEP")])) == 1


# ---------------------------------------------------------------------------------------------------------------------
# input validation, authority, privacy
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scope", [(), ("a" * 64,), ("a" * 64, ""), ("a" * 64, 7), ["a" * 64, "r"], None])
def test_invalid_scope_abstains(scope):
    review = prove_door_bases(scope, plan_page_id=PLAN, doors=DOORS, closures=CLOSURES, rooms=ROOMS, blocks=BLOCKS)
    assert review.reason_codes == (GATE_SCOPE_INVALID,) and review.doors == ()


def test_invalid_inputs_fail_closed_instead_of_being_dropped():
    nan_room = (RoomRegion("room-a", ((0, 0), (1, 0), (float("nan"), 1)), ("c1",)),) + ROOMS[1:]
    cases = [
        dict(plan_page_id=""), dict(plan_page_id=3),
        dict(doors=DOORS + (DoorTopologyInput("d1", (1,)),)),
        dict(doors=(DoorTopologyInput("", (1,)),)),
        dict(doors=(DoorTopologyInput("d1", (True,)),)),
        dict(doors=(DoorTopologyInput("d1", (-1,)),)),
        dict(closures=CLOSURES + (DoorClosure("c1", (1,)),)),
        dict(closures=(DoorClosure("", (1,)),)),
        dict(rooms=ROOMS + (RoomRegion("room-a", square(0, 0, 1, 1), ()),)),
        dict(rooms=(RoomRegion("room-a", ((0, 0), (1, 0)), ("c1",)),)),
        dict(rooms=nan_room),
        dict(blocks=BLOCKS + ("not a block",)),
        dict(blocks=(B(PLAN, "b", W("STEP", (0, 0, 1))),)),
        dict(blocks=(B("", "b"),)),
        dict(blocks=(TextBlock(PLAN, 5, (W("STEP", (0, 0, 1, 1)),), ()),)),
        dict(blocks=(TextBlock(PLAN, None, (W("STEP", (0, 0, 1, 1)),), ()),)),
        dict(blocks=(B(PLAN, "b", W("STEP", (0, 0, 1, 1), corroborated="yes")),)),
        dict(blocks=(B(PLAN, "b", W("STEP", (0, 0, 1, 1), line="0")),)),
        dict(blocks=(B(PLAN, "b", W("STEP", (0, 0, 1, 1), line=True)),)),
        dict(blocks=(TextBlock(PLAN, "b", [W("STEP", (0, 0, 1, 1))], ()),)),
    ]
    for case in cases:
        review = prove(**case)
        assert review.reason_codes == (GATE_INPUT_INVALID,) and review.doors == (), case


FLAGS = ("quantity_issued", "customer_row_issued", "physical_host_authorized", "kind_authorized", "frame_authorized",
         "frozen_benchmark_scored")


def test_no_proof_or_review_can_carry_authority():
    review = prove()
    d1 = door(review, "d1")
    for name in FLAGS:
        assert getattr(d1, name) is False
        with pytest.raises(ValueError):
            type(d1)(**{**d1.__dict__, name: True})
    for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored"):
        with pytest.raises(ValueError):
            type(review)(**{**review.__dict__, name: True})


def test_public_summary_is_counts_only():
    review = prove()
    summary = review.to_public_summary()
    assert summary["doors"] == 3 and summary["verified"] == 2 and summary["abstained"] == 1
    assert summary["by_reason"] == {GATE_NOT_TWO_ROOMS: 1, PROOF_REASON: 2}
    assert summary["statement_pages"] == 1 and summary["plan_level_marks"] == 1 and summary["other_sheet_level_marks"] == [1]
    text = json.dumps(summary)
    for ident in ("d1", "d2", "d3", "c1", "room-a", "obs-"):
        assert ident not in text
    assert not re.search(r"\d+\.\d", text.replace("1.0.0", ""))


def test_base_witnesses_exist_only_for_verified_doors_and_feed_the_compiler():
    review = prove()
    witnesses = review.to_base_witnesses()
    assert sorted(witnesses) == ["d1", "d2"] and "d3" not in witnesses
    base = witnesses["d1"][0]
    assert (base.base_afl_mm, base.source, base.text_trust) == (0.0, "level_scope_proof", TEXT_CORROBORATED)
    walls = WallConnectionWitness("TWO_WALL_SECTIONS_TAGGED", ("sec-a", "sec-b"))
    width = WidthWitness(900.0, SOURCE_PLAN_LABEL, TEXT_CORROBORATED)
    head = HeadWitness(2000.0, SOURCE_DOCUMENT_NOTE, False, TEXT_CORROBORATED)
    compiled = compile_door_rows(SCOPE, [
        DoorWitnesses(d, walls=(walls,), widths=(width,), heads=(head,), bases=witnesses.get(d, ())) for d in ("d1", "d3")
    ])
    ready = {r.door_id: r for r in compiled.rows}
    assert ready["d1"].ready and ready["d1"].opening_height_mm == 2000.0
    assert not ready["d3"].ready and "base_level" in ready["d3"].first_open_gate


# ---------------------------------------------------------------------------------------------------------------------
# invariances
# ---------------------------------------------------------------------------------------------------------------------


TRANSFORMS = {
    "translate": lambda x, y: (x + 1234.5, y - 987.25),
    "rotate90": lambda x, y: (-y, x),
    "rotate180": lambda x, y: (-x, -y),
    "mirror_x": lambda x, y: (-x, y),
    "scale": lambda x, y: (x * 3.0, y * 3.0),
}


def transform_scene_blocks(blocks, fn):
    out = []
    for b in blocks:
        ws = []
        for w in b.words:
            a, c = fn(w.bbox[0], w.bbox[1]), fn(w.bbox[2], w.bbox[3])
            ws.append(TextWord(w.text, (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])),
                               w.corroborated, w.line))
        out.append(TextBlock(b.page_id, b.block_id, tuple(ws), b.observation_ids))
    return tuple(out)


@pytest.mark.parametrize("name", sorted(TRANSFORMS))
def test_proof_is_invariant_under_translation_rotation_mirroring_and_scale(name):
    fn = TRANSFORMS[name]
    rooms = tuple(RoomRegion(r.room_id, tuple(fn(*p) for p in r.polygon), r.boundary_closure_ids) for r in ROOMS)
    for extra in ((), (block(PLAN, "p9", "STEP", 30, 50), block(SHEET, "m2", "50 STEP", 650, 650))):
        scene = BLOCKS + extra
        base = prove(blocks=scene)
        moved = prove(rooms=rooms, blocks=transform_scene_blocks(scene, fn))
        assert [(d.door_id, d.state, d.reason) for d in moved.doors] == [(d.door_id, d.state, d.reason) for d in base.doors]


def test_input_order_replay_unrelated_content_and_no_mutation():
    base = prove()
    rng = random.Random(7)
    for _ in range(5):
        doors, closures, rooms, blocks = list(DOORS), list(CLOSURES), list(ROOMS), list(BLOCKS)
        for seq in (doors, closures, rooms, blocks):
            rng.shuffle(seq)
        assert prove(doors=tuple(doors), closures=tuple(closures), rooms=tuple(rooms), blocks=tuple(blocks)) == base
    assert prove() == base == prove(blocks=copy.deepcopy(BLOCKS))
    noise = tuple(block(PLAN, f"n{i}", "WIN 1200 x 900", 500 + i, 800 + i) for i in range(30))
    far_room = RoomRegion("room-z", square(900, 900, 950, 950), ("c9",))
    assert prove(blocks=BLOCKS + noise, rooms=ROOMS + (far_room,)).doors == base.doors
    before = (copy.deepcopy(DOORS), copy.deepcopy(CLOSURES), copy.deepcopy(ROOMS), copy.deepcopy(BLOCKS))
    prove()
    assert (DOORS, CLOSURES, ROOMS, BLOCKS) == before


def test_a_mark_on_any_edge_of_a_room_counts_as_inside_even_with_one_room_to_test():
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    for centre_x, centre_y in ((200.0, 50.0), (150.0, 0.0), (150.0, 100.0), (0.0, 50.0), (0.0, 0.0), (200.0, 100.0)):
        on_edge = B(PLAN, "p9", W("STEP", (centre_x - 5, centre_y - 5, centre_x + 5, centre_y + 5)))
        assert door(prove(blocks=BLOCKS + (on_edge, sheet)), "d1").reason == GATE_ROOM_MARKED, (centre_x, centre_y)


def test_a_point_on_the_extension_of_an_edge_line_is_not_on_the_edge():
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    for centre_x, centre_y in ((350.0, 200.0), (350.0, 300.0), (-50.0, 250.0), (250.0, 250.0)):
        beside = B(PLAN, "p9", W("STEP", (centre_x - 5, centre_y - 5, centre_x + 5, centre_y + 5)))
        assert door(prove(blocks=BLOCKS + (beside, sheet)), "d2").verified, (centre_x, centre_y)


def test_a_mark_is_placed_by_the_centre_of_its_box_not_by_a_corner():
    sheet = block(SHEET, "m2", "50 STEP", 650, 650)
    straddling_left = B(PLAN, "p9", W("STEP", (-5.0, 40.0, 25.0, 50.0)))   # centre (10, 45)
    assert door(prove(blocks=BLOCKS + (straddling_left, sheet)), "d1").reason == GATE_ROOM_MARKED
    straddling_top = B(PLAN, "p9", W("STEP", (40.0, 95.0, 70.0, 125.0)))    # centre (55, 110)
    assert door(prove(blocks=BLOCKS + (straddling_top, sheet)), "d1").verified
    straddling_out = B(PLAN, "p9", W("STEP", (-25.0, 40.0, 5.0, 50.0)))    # centre (-10, 45)
    assert door(prove(blocks=BLOCKS + (straddling_out, sheet)), "d1").verified


def test_more_invalid_inputs_fail_closed():
    for case in (
        dict(blocks=(B(PLAN, "b", W("STEP", (0.0, 0.0, float("nan"), 1.0))),)),
        dict(blocks=(B(PLAN, "b", W("STEP", (True, 0.0, 1.0, 1.0))),)),
        dict(rooms=(RoomRegion("room-a", ((0, 0), (1, 0), (True, 1)), ("c1",)),)),
        dict(closures=(DoorClosure("c1", (True,)),)),
        dict(closures=(DoorClosure("c1", (1.0,)),)),
    ):
        review = prove(**case)
        assert review.reason_codes == (GATE_INPUT_INVALID,) and review.doors == (), case


def test_datum_words_are_whole_tokens_and_afl_is_one():
    assert is_level_statement(blk("RAISED 50 AFL"))
    assert not is_level_statement(blk("STEPPED 100 AFLAME"))
    assert not is_level_statement(blk("STEPPED 100 FFLS"))


def test_a_value_glued_to_the_word_is_still_a_mark_and_marks_are_ordered_deterministically():
    assert len(level_marks([blk("100STEP")])) == 1
    first, second = block(PLAN, "a", "STEP", 0, 0), block(SHEET, "b", "STEP", 0, 0)
    assert level_marks([second, first]) == level_marks([first, second])
    assert [m.page_id for m in level_marks([second, first])] == sorted([PLAN, SHEET])


def test_marks_of_other_sheets_never_land_in_the_plans_rooms():
    # the level sheet's own mark sits at coordinates that would be inside room-a if it were on the plan
    sheet_inside_coordinates = block(SHEET, "m1", "100 STEP", 20, 20)
    review = prove(blocks=(STATEMENT, sheet_inside_coordinates, PLAN_MARK_OUTSIDE, PLAN_TEXT))
    assert review.reason_codes == () and door(review, "d1").verified


def test_an_unreadable_word_in_either_room_blocks_and_only_verified_doors_carry_evidence():
    in_second_room = block(PLAN, "t1", "L1VING", 140, 20, corroborated=False)     # inside room-b only
    review = prove(blocks=(STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, in_second_room))
    assert door(review, "d1").reason == GATE_TEXT_RAW
    good = prove()
    for d in good.doors:
        assert bool(d.evidence_observation_ids) == d.verified
    assert door(good, "d3").evidence_observation_ids == ()


def test_the_plan_page_may_carry_the_statement_and_is_not_its_own_other_sheet():
    on_plan = (block(PLAN, "s1", "ALL SLAB STEPPED DOWN 100mm FROM FFL", 800, 800), PLAN_MARK_OUTSIDE, PLAN_TEXT)
    review = prove(blocks=on_plan)
    assert review.statement_pages == (PLAN,) and review.sheet_mark_counts == ()
    assert review.to_public_summary()["other_sheet_level_marks"] == []


def test_competing_closures_report_no_closure_id():
    two = DoorTopologyInput("d1", (11, 21))
    d1 = door(prove(doors=(two,)), "d1")
    assert d1.closure_id is None and d1.room_ids == ()


def multi_line_statement(*, unverified_word=None, corroborate_all=True):
    """A producer block that holds the real statement on lines 0 to 2 and an UNRELATED sentence on lines 3 to 4."""
    spec = [
        ("SERVICE", 0), ("SLAB", 0), ("STEPPED", 1), ("DOWN", 1), ("100mm", 2), ("FROM", 2), ("FFL", 2),
        ("NO", 3), ("FALL", 3), ("TO", 3), ("FLOOR", 3), ("WASTES", 4), ("AS", 4), ("THE", 4),
    ]
    ws = []
    for i, (text, line) in enumerate(spec):
        ok = corroborate_all and text != unverified_word
        ws.append(TextWord(text, (500.0 + i * 40, 500.0 + line * 12, 530.0 + i * 40, 510.0 + line * 12), ok, line))
    return TextBlock(SHEET, "s1", tuple(ws), ("obs-6-s1",))


def test_a_garbled_word_in_an_unrelated_sentence_of_the_same_block_does_not_unverify_the_statement():
    garbled_elsewhere = multi_line_statement(unverified_word="TO")                  # line 3: another sentence
    assert is_level_statement(garbled_elsewhere) and statement_corroborated(garbled_elsewhere)
    review = prove(blocks=(garbled_elsewhere, SHEET_MARK, PLAN_MARK_OUTSIDE, PLAN_TEXT))
    assert review.reason_codes == () and door(review, "d1").verified


def test_a_garbled_word_on_a_line_that_carries_the_statement_does_unverify_it():
    for word in ("STEPPED", "DOWN", "100mm", "FROM", "FFL", "SERVICE", "SLAB"):
        ws = multi_line_statement(unverified_word=word)
        carries = word not in ("SERVICE", "SLAB")          # lines 1 and 2 carry the step-like word and the datum word
        assert statement_corroborated(ws) is (not carries), word
    unverified = multi_line_statement(unverified_word="FFL")
    review = prove(blocks=(unverified, SHEET_MARK, PLAN_MARK_OUTSIDE, PLAN_TEXT))
    assert review.reason_codes == (GATE_TEXT_RAW,) and door(review, "d1").reason == GATE_TEXT_RAW


def test_a_mark_is_corroborated_by_its_own_word_not_by_its_neighbours():
    own_unverified = B(PLAN, "p1", W("100", (700, 700, 730, 710)), W("STEP", (740, 700, 770, 710), False), W("DOWN", (780, 700, 810, 710)))
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, own_unverified, PLAN_TEXT)), "d1").reason == GATE_TEXT_RAW
    neighbours_unverified = B(PLAN, "p1", W("100", (700, 700, 730, 710), False), W("STEP", (740, 700, 770, 710)),
                              W("DOWN", (780, 700, 810, 710), False))
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, neighbours_unverified, PLAN_TEXT)), "d1").verified
    assert level_marks([neighbours_unverified])[0].corroborated is True
    assert level_marks([own_unverified])[0].corroborated is False


def test_unreadable_words_are_judged_one_by_one_by_where_they_sit():
    mixed = B(PLAN, "t1", W("LIVING", (20, 20, 50, 30), True), W("L1VING", (300, 800, 330, 810), False))   # bad word far away
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, mixed)), "d1").verified
    mixed_inside = B(PLAN, "t1", W("LIVING", (300, 800, 330, 810), True), W("L1VING", (20, 20, 50, 30), False))   # bad word in room-a
    assert door(prove(blocks=(STATEMENT, SHEET_MARK, PLAN_MARK_OUTSIDE, mixed_inside)), "d1").reason == GATE_TEXT_RAW


def test_words_must_say_their_trust_and_their_line():
    for bad_word in (TextWord("STEP", (0, 0, 1, 1), None, 0), TextWord("STEP", (0, 0, 1, 1), True, None),
                     TextWord("STEP", (0, 0, 1, 1), True, 1.5)):
        review = prove(blocks=BLOCKS + (B(PLAN, "zz", bad_word),))
        assert review.reason_codes == (GATE_INPUT_INVALID,), bad_word
    assert "corroborated" in TextWord.__dataclass_fields__ and TextWord.__dataclass_fields__["corroborated"].default is dataclasses.MISSING


# ---------------------------------------------------------------------------------------------------------------------
# structure guards
# ---------------------------------------------------------------------------------------------------------------------

MODULE_PATH = Path(mod.__file__)


def test_module_imports_only_the_compiler_and_carries_no_project_or_height_literal():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert {m for m in imported if m.startswith("pb_")} == {"pb_door_row_evidence_compiler_shadow"}
    lowered = source.lower()
    for word in ("laurel", "maryborough", "lot16", "acacia", "alfresco", "porch", "2100", "100mm", "014e9f68", "slab plan"):
        assert word not in lowered, word
    for name in FLAGS:
        assert f"{name}=True" not in source.replace(" ", "")
