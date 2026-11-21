"""Shadow compiler: one candidate row per physical door once four things are verified.

Synthetic witnesses only: no PDF, project name, file name or benchmark value is an input. The numbers below are
arbitrary test values; the rules (corroboration, precedence of door-specific over U.N.O., base never assumed, one row per
door across views) are what is proved.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

import pb_door_row_evidence_compiler_shadow as mod
from pb_door_row_evidence_compiler_shadow import (
    AXES,
    CONFLICT,
    SOURCE_BASE_ELEVATION,
    SOURCE_BASE_LEVEL_SCOPE,
    SOURCE_DOCUMENT_NOTE,
    SOURCE_ELEVATION,
    SOURCE_PLAN_LABEL,
    SOURCE_SCHEDULE,
    TEXT_CORROBORATED,
    TEXT_RAW,
    VERIFIED,
    BaseWitness,
    DoorRowCompilation,
    DoorRowEvidence,
    DoorWitnesses,
    HeadWitness,
    WallConnectionWitness,
    WidthWitness,
    compile_door,
    compile_door_rows,
    group_witnesses,
)

SCOPE = ("a" * 64, "revision-a")
TAGGED = WallConnectionWitness("TWO_WALL_SECTIONS_TAGGED", ("sec-a", "sec-b"), "STRAIGHT_GAP")
WIDTH = WidthWitness(900.0, SOURCE_PLAN_LABEL, TEXT_CORROBORATED, ("obs-w",))
NOTE = HeadWitness(2000.0, SOURCE_DOCUMENT_NOTE, False, TEXT_CORROBORATED, ("obs-n",))
BASE = BaseWitness(0.0, SOURCE_BASE_ELEVATION)


def door(door_id="door-1", **kw):
    base = dict(walls=(TAGGED,), widths=(WIDTH,), heads=(NOTE,), bases=(BASE,))
    base.update(kw)
    return DoorWitnesses(door_id, **base)


def one(**kw):
    return compile_door(SCOPE, door(**kw))


# ---------------------------------------------------------------------------------------------------------------------
# the positive path and the arithmetic
# ---------------------------------------------------------------------------------------------------------------------


def test_all_four_verified_makes_one_ready_candidate_row_with_head_minus_base():
    row = one()
    assert row.ready and row.row_state == mod.ROW_READY and row.first_open_gate == ""
    assert [a.state for a in row.axes] == [VERIFIED] * 4 and [a.axis for a in row.axes] == list(AXES)
    assert (row.width_mm, row.head_afl_mm, row.base_afl_mm, row.opening_height_mm) == (900.0, 2000.0, 0.0, 2000.0)
    assert row.candidate_area_m2 == pytest.approx(1.8)
    raised = one(bases=(BaseWitness(150.0, SOURCE_BASE_LEVEL_SCOPE),))
    assert raised.ready and raised.opening_height_mm == 1850.0 and raised.candidate_area_m2 == pytest.approx(1.665)


def test_a_door_specific_head_beats_the_document_note_which_applies_only_unless_otherwise_noted():
    specific = HeadWitness(1950.0, SOURCE_SCHEDULE, True, TEXT_CORROBORATED)
    row = one(heads=(NOTE, specific))
    assert row.head_afl_mm == 1950.0 and row.axis("head_level").reason == "door_specific_head_level"
    assert row.axis("head_level").source == SOURCE_SCHEDULE
    assert one(heads=(NOTE,)).axis("head_level").reason == "document_note_applies_unless_otherwise_noted"


def test_a_raw_door_specific_head_blocks_the_note_instead_of_falling_back_to_it():
    raw_specific = HeadWitness(1950.0, SOURCE_ELEVATION, True, TEXT_RAW)
    row = one(heads=(NOTE, raw_specific))
    assert not row.ready and row.axis("head_level").reason == mod.GATE_HEAD_RAW


def test_witnesses_of_one_quantity_that_agree_are_one_value():
    other = WidthWitness(900.4, SOURCE_SCHEDULE, TEXT_CORROBORATED)
    two = one(widths=(WIDTH, other))
    assert two.ready and two.axis("width").source == "+".join(sorted([SOURCE_PLAN_LABEL, SOURCE_SCHEDULE]))
    assert two.width_mm == pytest.approx(900.2)      # their mean: symmetric, so no witness is "first" or "best"
    assert one(widths=(other, WIDTH)).width_mm == two.width_mm


# ---------------------------------------------------------------------------------------------------------------------
# each axis fails at its own named gate
# ---------------------------------------------------------------------------------------------------------------------


def test_wall_connections_need_two_distinct_tagged_sections():
    assert one(walls=()).axis("wall_connections").reason == mod.GATE_WALLS_NOT_TAGGED
    unresolved = WallConnectionWitness("UNRESOLVED", (), "UNRESOLVED", "x")
    assert one(walls=(unresolved,)).axis("wall_connections").reason == mod.GATE_WALLS_NOT_TAGGED
    for ids in (("sec-a",), ("sec-a", "sec-a"), ("sec-a", ""), ("sec-a", "sec-b", "sec-c"), ["sec-a", "sec-b"]):
        bad = WallConnectionWitness("TWO_WALL_SECTIONS_TAGGED", ids)
        assert one(walls=(bad,)).axis("wall_connections").reason == mod.GATE_WALLS_NOT_TWO


def test_tags_from_other_views_enrich_and_competing_tags_conflict():
    unresolved = WallConnectionWitness("UNRESOLVED", (), "UNRESOLVED", "x")
    assert one(walls=(unresolved, TAGGED)).ready          # an unresolved view never vetoes a tagged one
    same_reversed = WallConnectionWitness("TWO_WALL_SECTIONS_TAGGED", ("sec-b", "sec-a"))
    assert one(walls=(TAGGED, same_reversed)).ready
    other = WallConnectionWitness("TWO_WALL_SECTIONS_TAGGED", ("sec-a", "sec-z"))
    row = one(walls=(TAGGED, other))
    assert row.axis("wall_connections").state == CONFLICT and not row.ready


def test_raw_text_never_verifies_a_width_a_head_or_a_base():
    assert one(widths=(replace(WIDTH, text_trust=TEXT_RAW),)).axis("width").reason == mod.GATE_WIDTH_RAW
    assert one(heads=(replace(NOTE, text_trust=TEXT_RAW),)).axis("head_level").reason == mod.GATE_HEAD_NOTE_RAW
    assert one(bases=(replace(BASE, text_trust=TEXT_RAW),)).axis("base_level").reason == mod.GATE_BASE_RAW
    # a raw witness does not hide a corroborated one
    assert one(widths=(replace(WIDTH, text_trust=TEXT_RAW, value_mm=111.0), WIDTH)).ready


def test_missing_witnesses_name_their_axis():
    assert one(widths=()).axis("width").reason == mod.GATE_WIDTH_MISSING
    assert one(heads=()).axis("head_level").reason == mod.GATE_HEAD_MISSING
    assert one(bases=()).axis("base_level").reason == mod.GATE_BASE_UNVERIFIED


def test_the_base_is_never_assumed_a_head_level_alone_is_not_an_opening_height():
    row = one(bases=())
    assert not row.ready and row.opening_height_mm is None and row.candidate_area_m2 is None
    assert row.first_open_gate == f"base_level:{mod.GATE_BASE_UNVERIFIED}"
    assert row.head_afl_mm == 2000.0 and row.base_afl_mm is None


def test_disagreeing_witnesses_conflict_and_none_is_chosen():
    assert one(widths=(WIDTH, WidthWitness(920.0, SOURCE_SCHEDULE, TEXT_CORROBORATED))).axis("width").state == CONFLICT
    assert one(heads=(HeadWitness(2040.0, SOURCE_SCHEDULE, True, TEXT_CORROBORATED),
                      HeadWitness(2100.0, SOURCE_ELEVATION, True, TEXT_CORROBORATED))).axis("head_level").state == CONFLICT
    assert one(heads=(NOTE, replace(NOTE, head_afl_mm=2100.0))).axis("head_level").state == CONFLICT
    assert one(bases=(BASE, BaseWitness(100.0, SOURCE_BASE_LEVEL_SCOPE))).axis("base_level").state == CONFLICT


def test_agreement_tolerance_boundary_is_exact():
    tol = mod.AGREE_TOL_MM
    assert one(widths=(WIDTH, replace(WIDTH, value_mm=900.0 + tol, source=SOURCE_SCHEDULE))).axis("width").state == VERIFIED
    assert one(widths=(WIDTH, replace(WIDTH, value_mm=900.0 + tol + 0.01, source=SOURCE_SCHEDULE))).axis("width").state == CONFLICT
    assert one(bases=(BASE, replace(BASE, base_afl_mm=tol, source=SOURCE_BASE_LEVEL_SCOPE))).axis("base_level").state == VERIFIED
    assert one(bases=(BASE, replace(BASE, base_afl_mm=tol + 0.01, source=SOURCE_BASE_LEVEL_SCOPE))).axis("base_level").state == CONFLICT


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf"), "900", None, True])
def test_invalid_numbers_are_rejected_on_every_axis(bad):
    assert one(widths=(replace(WIDTH, value_mm=bad),)).axis("width").reason == mod.GATE_WIDTH_INVALID
    assert one(heads=(replace(NOTE, head_afl_mm=bad),)).axis("head_level").reason == mod.GATE_HEAD_INVALID


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), "0", None, True])
def test_invalid_base_values_are_rejected(bad):
    assert one(bases=(replace(BASE, base_afl_mm=bad),)).axis("base_level").reason == mod.GATE_BASE_INVALID


def test_a_base_at_or_above_the_head_is_not_an_opening():
    for base in (2000.0, 2500.0):
        row = one(bases=(BaseWitness(base, SOURCE_BASE_LEVEL_SCOPE),))
        assert not row.ready and row.axis("base_level").reason == mod.GATE_HEIGHT_NOT_POSITIVE
    assert one(bases=(BaseWitness(1999.0, SOURCE_BASE_LEVEL_SCOPE),)).opening_height_mm == 1.0


def test_first_open_gate_follows_the_axis_order():
    row = one(walls=(), widths=(), heads=(), bases=())
    assert row.first_open_gate == f"wall_connections:{mod.GATE_WALLS_NOT_TAGGED}"
    assert one(widths=(), heads=(), bases=()).first_open_gate == f"width:{mod.GATE_WIDTH_MISSING}"
    assert one(heads=(), bases=()).first_open_gate == f"head_level:{mod.GATE_HEAD_MISSING}"


# ---------------------------------------------------------------------------------------------------------------------
# identity: one row per physical door, across every view
# ---------------------------------------------------------------------------------------------------------------------


def test_every_view_of_one_door_enriches_one_row_and_never_makes_another():
    plan = DoorWitnesses("door-1", walls=(TAGGED,), widths=(WIDTH,))
    inset = DoorWitnesses("door-1", widths=(replace(WIDTH, source=SOURCE_SCHEDULE),))
    schedule = DoorWitnesses("door-1", heads=(NOTE,))
    elevation = DoorWitnesses("door-1", bases=(BASE,))
    result = compile_door_rows(SCOPE, [plan, inset, schedule, elevation])
    assert len(result.rows) == 1 and result.rows[0].ready
    assert result.rows[0].axis("width").source == "+".join(sorted([SOURCE_PLAN_LABEL, SOURCE_SCHEDULE]))
    other = compile_door_rows(SCOPE, [plan, DoorWitnesses("door-2", widths=(WIDTH,)), schedule])
    assert [r.door_id for r in other.rows] == ["door-1", "door-2"]


def test_a_witness_without_a_door_identity_fails_closed_instead_of_being_dropped():
    for bad in (DoorWitnesses("", widths=(WIDTH,)), DoorWitnesses("  "), "x", None):
        result = compile_door_rows(SCOPE, [door(), bad])
        assert result.status == mod.ABSTAINED and result.reason_codes == (mod.GATE_DOOR_INVALID,) and result.rows == ()


@pytest.mark.parametrize("scope", [(), ("a" * 64,), ("a" * 64, ""), ("a" * 64, 7), ["a" * 64, "r"], None])
def test_invalid_scope_abstains(scope):
    result = compile_door_rows(scope, [door()])
    assert result.status == mod.ABSTAINED and result.reason_codes == (mod.GATE_SCOPE_INVALID,) and result.rows == ()


def test_order_replay_and_inputs_do_not_change_rows():
    doors = [door("door-b"), door("door-a", widths=()), door("door-c", bases=())]
    before = copy.deepcopy(doors)
    first = compile_door_rows(SCOPE, doors)
    assert first == compile_door_rows(SCOPE, list(reversed(doors))) == compile_door_rows(SCOPE, copy.deepcopy(doors))
    assert doors == before
    assert [r.door_id for r in first.rows] == ["door-a", "door-b", "door-c"]
    extra = compile_door_rows(SCOPE, doors + [door("door-z")])
    assert [r for r in extra.rows if r.door_id != "door-z"] == list(first.rows)


def test_row_ids_depend_on_scope_and_door_not_on_witness_values():
    a = one()
    b = compile_door(("b" * 64, "revision-a"), door())
    assert a.row_id != b.row_id
    assert compile_door(SCOPE, door("door-2")).row_id != a.row_id      # two doors in one scope are two rows
    assert one(widths=(replace(WIDTH, value_mm=910.0),)).row_id == a.row_id


# ---------------------------------------------------------------------------------------------------------------------
# authority and privacy
# ---------------------------------------------------------------------------------------------------------------------

FLAGS = ("quantity_issued", "customer_row_issued", "physical_host_authorized", "physical_opening_authenticated",
         "kind_authorized", "frame_authorized", "frozen_benchmark_scored")


def test_no_row_or_compilation_can_carry_authority_and_a_ready_row_needs_every_axis():
    row = one()
    for name in FLAGS:
        assert getattr(row, name) is False and row.to_dict()[name] is False
        with pytest.raises(ValueError):
            DoorRowEvidence(**{**row.__dict__, name: True})
    comp = compile_door_rows(SCOPE, [door()])
    for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored"):
        assert getattr(comp, name) is False
        with pytest.raises(ValueError):
            DoorRowCompilation(**{**comp.__dict__, name: True})
    not_ready = one(bases=())
    with pytest.raises(ValueError):
        DoorRowEvidence(**{**not_ready.__dict__, "row_state": mod.ROW_READY})
    assert row.next_step == mod.NEXT_STEP and "promotion_review" in mod.NEXT_STEP


def test_public_summary_is_counts_only():
    comp = compile_door_rows(SCOPE, [door("door-1"), door("door-2", bases=()), door("door-3", widths=())])
    summary = comp.to_public_summary()
    assert summary["physical_doors"] == 3 and summary["ready_for_existing_issuer"] == 1 and summary["not_ready"] == 2
    assert summary["axis_states"]["base_level"] == {"ABSTAINED": 1, "VERIFIED": 2}
    assert summary["first_open_gate"] == {"": 1, f"base_level:{mod.GATE_BASE_UNVERIFIED}": 1,
                                          f"width:{mod.GATE_WIDTH_MISSING}": 1}
    text = json.dumps(summary)
    assert not any(r.door_id in text for r in comp.rows)
    assert not re.search(r"\d+\.\d", text.replace("1.0.0", ""))
    assert summary["quantity_issued"] is False and summary["customer_row_issued"] is False


def test_group_witnesses_is_a_pure_union_keyed_by_door_id():
    merged = group_witnesses([DoorWitnesses("d", widths=(WIDTH,)), DoorWitnesses("d", heads=(NOTE,)),
                              DoorWitnesses("e")])
    assert [d.door_id for d in merged] == ["d", "e"]
    assert merged[0].widths == (WIDTH,) and merged[0].heads == (NOTE,) and merged[1].walls == ()


# ---------------------------------------------------------------------------------------------------------------------
# structure guards
# ---------------------------------------------------------------------------------------------------------------------

MODULE_PATH = Path(mod.__file__)


def test_compiler_imports_only_stable_ids_and_carries_no_project_or_height_literal():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert {m for m in imported if m.startswith("pb_")} == {"pb_migration_contracts"}
    lowered = source.lower()
    for word in ("laurel", "maryborough", "lot16", "acacia", "2100", "2040", "870", "920", "720"):
        assert word not in lowered, word
    for name in ("quantity_issued", "customer_row_issued", "physical_host_authorized"):
        assert f"{name}=True" not in source.replace(" ", "")
