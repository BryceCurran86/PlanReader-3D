"""A doorway-bounded original source floor is a ring, not a point collection."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.diag_gpt2_source_finish_floor_handoff_shadow import (
    audit_gpt2_original_doorway_bound_floor_finish_correspondence as audit,
)

SHA = "f" * 64
FLOOR = ((0., 0.), (4., 0.), (4., 4.), (0., 4.))
SHIFT = (10., 20.)
FINISH = tuple((x + SHIFT[0], y + SHIFT[1]) for x, y in FLOOR)


def _case():
    floor = {
        "status": "source_jamb_bound_open_door_perimeter_candidate_only",
        "source_jamb_roles_same_sha_rechecked": True,
        "source_wall_and_jamb_geometry_independently_recomputed": True,
        "original_source_sha256": SHA,
        "original_page_1_based": 7,
        "original_source_perimeter_side_ids": ("f1", "f2", "f3", "f4"),
        "source_ink_ring_with_explicit_virtual_door_gap_pdf_pts": FLOOR,
        "source_virtual_door_connector_pdf_pts": (FLOOR[-1], FLOOR[0]),
    }
    finish = {
        **floor,
        "original_page_1_based": 11,
        "original_source_perimeter_side_ids": ("t1", "t2", "t3", "t4"),
        "source_ink_ring_with_explicit_virtual_door_gap_pdf_pts": FINISH,
        "source_virtual_door_connector_pdf_pts": (FINISH[-1], FINISH[0]),
    }
    registration = {
        "status": "original_four_edge_ink_correspondence_with_unclosed_doorway",
        "original_source_sha256": SHA,
        "original_floor_page_id": 7,
        "original_finish_page_id": 11,
        "source_translation_candidate_pdf_pts": SHIFT,
        "original_top_gap_pdf_pts": (FLOOR[-1], FLOOR[0]),
        "original_witnesses": {
            role: {
                "floor_source": {"identity": "f" + str(index)},
                "finish_source": {"identity": "t" + str(index)},
                "matched_original_ink_only": True,
            }
            for index, role in enumerate(
                ("left", "right", "bottom", "top_partial"), start=1
            )
        },
    }
    return floor, finish, registration


def _audit(floor, finish, reg):
    return audit(floor, finish, source_registration=reg,
                 translation_pdf_pts=SHIFT)


def test_original_closed_ink_edge_cycle_matches_without_metric_authority():
    floor, finish, reg = _case()
    row = _audit(floor, finish, reg)
    assert row["status"] == "original_source_ink_ring_translation_candidate"
    assert row["geometric_ink_correspondence_only"] is True
    assert row["source_virtual_door_closure_is_physical_wall"] is False
    assert row["source_finished_face_verified"] is False
    assert row["new_firm_quantities"] == 0


@pytest.mark.parametrize("reorder", [
    lambda points: points[1:] + points[:1],
    lambda points: tuple(reversed(points)),
    lambda points: tuple(reversed(points[2:] + points[:2])),
])
def test_same_original_edge_cycle_survives_rotation_or_reversed_native_order(reorder):
    floor, finish, reg = _case()
    finish["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"] = reorder(FINISH)
    row = _audit(floor, finish, reg)
    assert row["status"] == "original_source_ink_ring_translation_candidate"
    assert row["new_firm_quantities"] == 0


@pytest.mark.parametrize("wrong_vertices", [
    (FINISH[0], FINISH[2], FINISH[1], FINISH[3]),  # bow-tie, same point set
    (FINISH[0], FINISH[1], FINISH[1], FINISH[3]),  # duplicated source vertex
    (FINISH[0], FINISH[1], (float("nan"), 24.), FINISH[3]),
    (FINISH[0], FINISH[1], (float("inf"), 24.), FINISH[3]),
    (FINISH[0], FINISH[1], ("foreign", 24.), FINISH[3]),
])
def test_same_coordinate_set_cannot_hide_invalid_or_differently_joined_room_ring(
    wrong_vertices,
):
    floor, finish, reg = _case()
    finish["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"] = wrong_vertices
    row = _audit(floor, finish, reg)
    assert row["status"] == "original_doorway_floor_finish_correspondence_abstained"
    assert row["first_failure"] == "source_doorway_bounded_ring_geometry_conflict"
    assert row["new_firm_quantities"] == 0


@pytest.mark.parametrize("bad", [
    ((0., 0.), (4., 4.)),  # a diagonal, NOT a source-open doorway closing edge
    ((0., 0.), (0., 0.)),
    ((0., 0.), ("bad", 4.)),
    ((0., 0.),),
])
def test_door_connector_must_be_its_actual_perimeter_edge(bad):
    floor, finish, reg = _case()
    floor["source_virtual_door_connector_pdf_pts"] = bad
    if len(bad) == 2 and all(
        isinstance(p, tuple) and len(p) == 2
        and all(isinstance(v, (int, float)) for v in p)
        for p in bad
    ):
        finish["source_virtual_door_connector_pdf_pts"] = tuple(
            (x + SHIFT[0], y + SHIFT[1]) for x, y in bad
        )
    row = _audit(floor, finish, reg)
    assert row["first_failure"] == "source_original_doorway_registration_gap_conflict"
    assert row["new_firm_quantities"] == 0


def test_original_source_jamb_sha_or_registration_still_gate_correspondence():
    floor, finish, reg = _case()
    corrupted = deepcopy(finish)
    corrupted["original_source_sha256"] = "0" * 64
    result = _audit(floor, corrupted, reg)
    assert result["first_failure"] == "original_cross_sheet_doorway_source_sha_conflict"
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("omitted", [
    "left", "right", "bottom", "top_partial",
])
def test_missing_one_of_four_original_side_witnesses_never_claims_correspondence(
    omitted,
):
    floor, finish, reg = _case()
    del reg["original_witnesses"][omitted]
    result = _audit(floor, finish, reg)
    assert result["first_failure"] == "original_four_side_witnesses_missing"
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("role", ["left", "right", "bottom", "top_partial"])
def test_missing_original_ink_role_match_requires_abstention(role):
    floor, finish, reg = _case()
    reg["original_witnesses"][role]["matched_original_ink_only"] = False
    result = _audit(floor, finish, reg)
    assert result["first_failure"] == "original_four_side_witnesses_missing"


@pytest.mark.parametrize("page_role", ["floor_source", "finish_source"])
def test_repeated_native_wall_ink_source_receipt_cannot_own_two_distinct_sides(
    page_role,
):
    floor, finish, reg = _case()
    pair = reg["original_witnesses"]
    pair["right"][page_role]["identity"] = pair["left"][page_role]["identity"]
    result = _audit(floor, finish, reg)
    assert result["first_failure"] == "original_four_side_source_witness_alias_conflict"


@pytest.mark.parametrize("bad_gap", [
    ((0., 0.), (4., 0.)),   # existing wall edge, not source ink doorway gap
    ((0., 0.), (4., 4.)),   # diagonal between corners
    ((0., 0.), (0., 0.)),   # no opening
    ((0., 0.), ("missing", 4.)),
    None,
])
def test_original_issuer_top_gap_must_be_same_as_both_source_bound_doorways(
    bad_gap,
):
    floor, finish, reg = _case()
    reg["original_top_gap_pdf_pts"] = bad_gap
    result = _audit(floor, finish, reg)
    assert result["first_failure"] == "source_original_doorway_registration_gap_conflict"
    assert result["new_firm_quantities"] == 0


def test_reversed_native_gap_order_is_not_a_new_doorway():
    floor, finish, reg = _case()
    reg["original_top_gap_pdf_pts"] = tuple(
        reversed(reg["original_top_gap_pdf_pts"])
    )
    result = _audit(floor, finish, reg)
    assert result["status"] == "original_source_ink_ring_translation_candidate"
    assert result["new_firm_quantities"] == 0
