"""Exact source-only floor seal boundary: never launder workspace or page geometry."""
from dataclasses import replace

import pytest

from pb_live_floor_area_source_closed_export import build_live_floor_area_source_traces
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with, _source_area,
)


def _valid():
    return _claim_with(_source_area())


def test_real_documented_metric_floor_keeps_original_source_receipts():
    traces = build_live_floor_area_source_traces(
        _valid(), workspace_id=7, project_id="project-7"
    )
    assert len(traces) == 1
    trace = next(iter(traces.values()))
    assert trace.workspace_id == 7
    assert trace.source_bbox == (10.0, 10.0, 20.0, 20.0)
    assert {"ev-room", "ev-area"}.issubset(set(trace.evidence_ids))
    assert trace.canonical_entity_ids == ("floor-1",)


@pytest.mark.parametrize("workspace", [True, False, 7.9, 7.0, "7", " 7", None, 0, -1])
def test_floor_export_cannot_coerce_workspace_identity(workspace):
    with pytest.raises(SourceClosedRunConflictError, match="workspace_id"):
        build_live_floor_area_source_traces(
            _valid(), workspace_id=workspace, project_id="project-7"
        )


@pytest.mark.parametrize("polygon", [
    ((10.0, 10.0), (20.0, 10.0), (True, 20.0), (10.0, 20.0)),
    ((10.0, 10.0), (20.0, "10"), (20.0, 20.0), (10.0, 20.0)),
    ((10.0, 10.0), (20.0, 10.0), (20.0, 10**400), (10.0, 20.0)),
    ((10.0, 10.0), (20.0, 10.0), (20.0, float("nan")), (10.0, 20.0)),
    ((0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)),
    ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)),
])
def test_floor_export_refuses_invalid_original_page_polygon(polygon):
    original = _valid()
    broken = replace(
        original, canonical_floors=(
            replace(original.canonical_floors[0], polygon_pdf_pts=polygon),
        )
    )
    with pytest.raises(SourceClosedRunConflictError, match="polygon"):
        build_live_floor_area_source_traces(
            broken, workspace_id=7, project_id="project-7"
        )


@pytest.mark.parametrize("bad", [("ev-room", " ev-area"), ("ev-room", "ev-area ")])
def test_floor_trace_rejects_padded_original_evidence_receipt(bad):
    original = _valid()
    broken = replace(
        original, canonical_floors=(
            replace(original.canonical_floors[0], evidence_ids=bad),
        )
    )
    with pytest.raises(SourceClosedRunConflictError, match="receipts"):
        build_live_floor_area_source_traces(
            broken, workspace_id=7, project_id="project-7"
        )
