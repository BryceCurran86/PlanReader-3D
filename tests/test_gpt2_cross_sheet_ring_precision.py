"""GPT2 synthetic source-ink ring correspondence precision regressions.

These inputs are NOT original PlanReader PDFs, physical room registrations,
metric quantities, customer acceptance or frozen benchmark truth.
"""
from __future__ import annotations

import math

import pytest

from tools.diag_gpt2_source_finish_floor_handoff_shadow import (
    audit_gpt2_original_cross_sheet_ring_correspondence as compare,
)


FLOOR = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
SHIFT = (10.0, 0.0)
SHA = "a" * 64


def _graphs(
    floor_vertices=FLOOR,
    finish_vertices=None,
    *,
    shift=SHIFT,
):
    if finish_vertices is None:
        finish_vertices = tuple((x + shift[0], y + shift[1]) for x, y in FLOOR)

    def source_graph(page, vertices, prefix):
        ids = tuple(f"{prefix}{index}" for index in range(4))
        return {
            "source_sha256": SHA,
            "page_1_based": page,
            "original_native_edge_ids": ids,
            "native_candidate_ring_count": 1,
            "interior_stroke_intersections_and_overlaps": (),
            "native_components": [{
                "source_simple_ring_candidate": {
                    "vertices_pdf_pts": tuple(vertices),
                    "source_edge_ids": ids,
                },
            }],
        }

    floor = source_graph(7, floor_vertices, "f")
    finish = source_graph(11, finish_vertices, "t")
    registration = {
        "status": "original_four_edge_ink_correspondence_with_unclosed_doorway",
        "original_source_sha256": SHA,
        "original_floor_page_id": 7,
        "original_finish_page_id": 11,
        "source_translation_candidate_pdf_pts": shift,
        "original_witnesses": {
            "north": {
                "floor_source": {"identity": "f0"},
                "finish_source": {"identity": "t0"},
            },
        },
    }
    return floor, finish, registration


def _compare(floor_vertices=FLOOR, finish_vertices=None, shift=SHIFT):
    floor, finish, registration = _graphs(
        floor_vertices=floor_vertices,
        finish_vertices=finish_vertices,
        shift=shift,
    )
    return compare(
        floor, finish,
        original_source_registration=registration,
        translation_pdf_pts=shift,
    )


def _assert_candidate_only(result):
    assert result["status"] == "original_source_ink_ring_translation_candidate"
    assert result["first_failure"] == "W4_structural_wall_and_physical_room_identity"
    assert result["geometric_ink_correspondence_only"] is True
    assert result["physical_room_identity_proven"] is False
    assert result["source_finished_face_verified"] is False
    assert result["new_firm_quantities"] == 0


def _assert_abstained(result):
    assert result["status"] == "source_floor_finish_ring_correspondence_abstained"
    assert result["first_failure"] in (
        "competing_cross_sheet_original_perimeter",
        "original_registration_transform_invalid",
    )
    assert result["physical_room_identity_proven"] is False
    assert result["new_firm_quantities"] == 0


def test_matching_ring_with_subquantum_native_float_jitter_retains_ink_candidate():
    finish = (
        (10.0004, 0.0003), (110.0002, -0.0003),
        (110.0001, 100.0004), (9.9997, 100.0002),
    )
    _assert_candidate_only(_compare(finish_vertices=finish))


@pytest.mark.parametrize("order", [
    (0, 1, 2, 3),
    (1, 2, 3, 0),
    (0, 3, 2, 1),
])
def test_crosssheet_valid_cyclic_or_reverse_native_walk(order):
    native = tuple((x + 10, y) for x, y in FLOOR)
    _assert_candidate_only(_compare(finish_vertices=tuple(native[i] for i in order)))


def test_native_perimeter_can_repeat_start_at_end():
    floor = (*FLOOR, FLOOR[0])
    finish = tuple((x + 10, y) for x, y in floor)
    _assert_candidate_only(_compare(floor_vertices=floor, finish_vertices=finish))


@pytest.mark.parametrize("order", [
    (0, 2, 1, 3),
    (0, 1, 3, 2),
])
def test_same_unordered_vertices_with_rewired_perimeter_abstains(order):
    native = tuple((x + 10, y) for x, y in FLOOR)
    _assert_abstained(_compare(finish_vertices=tuple(native[i] for i in order)))


def test_beyond_existing_native_quantization_abstains():
    finish = ((10.002, 0.0), (110.0, 0.0), (110.0, 100.0), (10.0, 100.0))
    _assert_abstained(_compare(finish_vertices=finish))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "0", True, 10**300])
def test_invalid_or_unbounded_native_corner_abstains_without_crashing(value):
    finish = ((value, 0.0), (110.0, 0.0), (110.0, 100.0), (10.0, 100.0))
    _assert_abstained(_compare(finish_vertices=finish))


def test_distinct_source_corners_collapsing_with_rounding_cannot_match():
    floor = ((0.0, 0.0), (0.0004, 0.0), (100.0, 100.0), (0.0, 100.0))
    finish = tuple((x + 10, y) for x, y in floor)
    _assert_abstained(_compare(floor_vertices=floor, finish_vertices=finish))


@pytest.mark.parametrize("shift", [(10**300, 0.0), (float("nan"), 0.0)])
def test_unbounded_or_nonfinite_registration_transform_abstains(shift):
    _assert_abstained(_compare(shift=shift))
