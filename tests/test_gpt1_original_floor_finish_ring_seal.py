"""A positive shoelace is not authority for a self-crossing physical floor."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    _original_floor_polygon_is_simple,
    build_live_floor_finish_area_source_traces,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim, _floor, _quantity


RECTANGLE = ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))
L_SHAPE = ((0.0, 0.0), (10.0, 0.0), (10.0, 2.0),
           (4.0, 2.0), (4.0, 6.0), (0.0, 6.0))
# Strictly positive signed shoelace, but two non-adjacent source edges cross.
INVALID_POSITIVE_AREA = ((0.0, 0.0), (8.0, 0.0), (0.0, 8.0),
                         (8.0, 8.0), (0.0, 12.0))


@pytest.mark.parametrize("ring", [
    RECTANGLE, RECTANGLE + (RECTANGLE[0],), L_SHAPE,
    tuple(reversed(RECTANGLE)), tuple(reversed(L_SHAPE)),
])
def test_independent_simple_floor_perimeters_stay_eligible(ring):
    assert _original_floor_polygon_is_simple(ring)


def test_physical_translation_scale_and_orthogonal_rotation_preserve_simple_ring():
    original = L_SHAPE
    variants = [
        tuple((x + 200, y - 40) for x, y in original),
        tuple((x * 2.0, y * 2.0) for x, y in original),
        tuple((-y, x) for x, y in original),
        tuple((x, y) for x, y in original[:2]) + (
            (10.0, 1.0), (10.0, 2.0)
        ) + original[3:],
    ]
    assert all(_original_floor_polygon_is_simple(ring) for ring in variants)


@pytest.mark.parametrize("ring", [
    INVALID_POSITIVE_AREA,
    ((0, 0), (10, 10), (0, 10), (10, 0)),
    ((0, 0), (10, 0), (10, 10), (8, 8), (10, 10), (0, 10)),
    ((0, 0), (10, 0), (10, 10), (0, 0), (0, 10)),
    ((0, 0), (5, 0), (10, 0)),
    ((0, 0), (0, 0), (10, 0), (10, 10), (0, 10)),
])
def test_crossing_repeated_and_degenerate_floor_faces_are_not_physical_perimeters(ring):
    assert not _original_floor_polygon_is_simple(ring)


def test_positive_shoelace_self_crossing_cannot_be_source_sealed():
    floor = replace(_floor(), polygon_pdf_pts=INVALID_POSITIVE_AREA)
    with pytest.raises(
        SourceClosedRunConflictError, match="self-intersects or is invalid"
    ):
        build_live_floor_finish_area_source_traces(
            _claim(floor), workspace_id=1, project_id="project-1",
        )


def test_original_sealable_rectangle_retains_its_existing_quantity_lineage():
    claim = _claim()
    traces = build_live_floor_finish_area_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )
    assert set(traces) == {"floor-finish-q1"}
    assert _original_floor_polygon_is_simple(claim.canonical_floors[0].polygon_pdf_pts)


@pytest.mark.parametrize("broken", [
    ((0, 0), (1, float("nan")), (1, 1), (0, 1)),
    ((0, 0), (1, float("inf")), (1, 1), (0, 1)),
    ((0, 0), (True, 0), (1, 1), (0, 1)),
])
def test_nonfinite_or_boolean_source_coordinate_never_mints_area(broken):
    # The commercial caller independently verifies typed finite vertices.
    # GEOS should not become a competing positive authority on those inputs.
    assert not _original_floor_polygon_is_simple(broken)


@pytest.mark.parametrize("copied_source_sha", ["not-a-real-pdf-source", "g" * 64, 37])
def test_two_matching_but_nonsha_source_ids_cannot_seal_finish(copied_source_sha):
    original = _claim()
    floor = replace(original.canonical_floors[0], source_sha256=copied_source_sha)
    quantity = replace(
        original.floor_finish_quantity_evidence[0],
        metadata={
            **dict(original.floor_finish_quantity_evidence[0].metadata),
            "source_sha256": copied_source_sha,
        },
    )
    compromised = replace(
        original, canonical_floors=(floor,),
        floor_finish_quantity_evidence=(quantity,),
    )
    with pytest.raises(SourceClosedRunConflictError, match="source SHA is malformed"):
        build_live_floor_finish_area_source_traces(
            compromised, workspace_id=1, project_id="project-1"
        )


@pytest.mark.parametrize("bad", [None, "", True, 12, " room-area-id", "room-area-id "])
def test_floor_finish_requires_one_exact_canonical_metric_area_receipt(bad):
    floor = replace(_floor(), metric_area_quantity_id=bad)
    with pytest.raises(SourceClosedRunConflictError, match="metric area receipt is missing"):
        build_live_floor_finish_area_source_traces(
            _claim(floor), workspace_id=1, project_id="project-1"
        )


@pytest.mark.parametrize("field", ["finish_code", "semantic_finish"])
@pytest.mark.parametrize("bad", ["", " padded", "padded ", True, 12, None])
def test_finish_cannot_seal_with_untyped_or_missing_source_material_code(field, bad):
    original = _claim()
    source_quantity = original.floor_finish_quantity_evidence[0]
    altered = replace(
        source_quantity,
        metadata={**dict(source_quantity.metadata), field: bad},
    )
    claim = replace(original, floor_finish_quantity_evidence=(altered,))
    with pytest.raises(SourceClosedRunConflictError, match="source material identity is malformed"):
        build_live_floor_finish_area_source_traces(
            claim, workspace_id=1, project_id="project-1"
        )


def test_valid_uppercase_source_sha_still_passes_source_seal():
    original = _claim()
    uppercase_digest = "AB" * 32
    floor = replace(original.canonical_floors[0], source_sha256=uppercase_digest)
    quantity = replace(
        original.floor_finish_quantity_evidence[0],
        metadata={
            **dict(original.floor_finish_quantity_evidence[0].metadata),
            "source_sha256": uppercase_digest,
        },
    )
    claim = replace(
        original, canonical_floors=(floor,),
        floor_finish_quantity_evidence=(quantity,),
    )
    traces = build_live_floor_finish_area_source_traces(
        claim, workspace_id=1, project_id="project-1"
    )
    assert tuple(traces) == ("floor-finish-q1",)
