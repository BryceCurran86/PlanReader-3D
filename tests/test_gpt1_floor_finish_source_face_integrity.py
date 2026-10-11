"""GPT1 source-firm floor-finish m² only with valid physical face geometry."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim, _floor


@pytest.mark.parametrize("polygon", [
    ((10., 10.), (20., 20.), (30., 30.)),
    ((10., 10.), (20., 20.), (10., 20.), (20., 10.)),
])
def test_positive_pdf_point_bounding_box_does_not_seal_degenerate_floor_finish(polygon):
    claim = _claim(replace(_floor(), polygon_pdf_pts=polygon))
    with pytest.raises(SourceClosedRunConflictError, match="degenerate"):
        build_live_floor_finish_area_source_traces(
            claim, workspace_id=7, project_id="source-project",
        )


@pytest.mark.parametrize("bad", [True, False, "8.64", float("nan"), float("inf")])
def test_tampered_floor_finish_quantity_cannot_copy_invalid_metric(bad):
    claim = _claim()
    original = copy(claim.floor_finish_quantity_evidence[0])
    object.__setattr__(original, "value", bad)
    tampered = replace(claim, floor_finish_quantity_evidence=(original,))
    with pytest.raises(SourceClosedRunConflictError):
        build_live_floor_finish_area_source_traces(
            tampered, workspace_id=7, project_id="source-project",
        )


@pytest.mark.parametrize("confidence", [True, "0.95", float("nan"), 1.5])
def test_tampered_source_confidence_cannot_authorize_floor_finish(confidence):
    claim = _claim()
    original = copy(claim.floor_finish_quantity_evidence[0])
    object.__setattr__(original, "confidence", confidence)
    tampered = replace(claim, floor_finish_quantity_evidence=(original,))
    with pytest.raises(SourceClosedRunConflictError, match="untyped"):
        build_live_floor_finish_area_source_traces(
            tampered, workspace_id=7, project_id="source-project",
        )


def test_authentic_original_floor_face_still_seals_exact_8_64_m2_finish():
    claim = _claim()
    result = build_live_floor_finish_area_source_traces(
        claim, workspace_id=7, project_id="source-project",
    )
    assert len(result) == 1
    assert next(iter(result.values())).source_bbox == (10.0, 10.0, 20.0, 20.0)
    assert claim.floor_finish_quantity_evidence[0].value == 8.64



@pytest.mark.parametrize("oversized", [10 ** 400, -(10 ** 400)])
def test_original_floor_finish_confidence_overflow_is_blocked_and_not_a_run_crash(oversized):
    claim = _claim()
    tampered_qty = copy(claim.floor_finish_quantity_evidence[0])
    object.__setattr__(tampered_qty, "confidence", oversized)
    with pytest.raises(SourceClosedRunConflictError, match="untyped"):
        build_live_floor_finish_area_source_traces(
            replace(claim, floor_finish_quantity_evidence=(tampered_qty,)),
            workspace_id=7, project_id="source-project",
        )


def test_original_floor_finish_confidence_is_accepted_when_typed_and_finite():
    claim = _claim()
    assert len(build_live_floor_finish_area_source_traces(
        claim, workspace_id=7, project_id="source-project",
    )) == 1



@pytest.mark.parametrize("bad_polygon", [
    ((0., 0.), (10 ** 400, 0.), (10., 20.)),
    ((0., 0.), (True, 0.), (10., 20.)),
    ((0., 0.), ("10", 0.), (10., 20.)),
    ((0., 0.), (float("nan"), 0.), (10., 20.)),
])
def test_floor_finish_untyped_or_overflow_source_polygon_is_conflict(bad_polygon):
    claim = _claim(replace(_floor(), polygon_pdf_pts=bad_polygon))
    with pytest.raises(SourceClosedRunConflictError, match="source polygon is invalid"):
        build_live_floor_finish_area_source_traces(
            claim, workspace_id=7, project_id="source-project",
        )


def test_floor_finish_original_physical_source_square_bbox_preserved():
    traces = build_live_floor_finish_area_source_traces(
        _claim(), workspace_id=7, project_id="source-project",
    )
    assert next(iter(traces.values())).source_bbox == (10.0, 10.0, 20.0, 20.0)
