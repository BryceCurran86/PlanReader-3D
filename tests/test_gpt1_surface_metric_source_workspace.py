"""Q01/Q02 source-sealed metric finishes may not launder workspace or evidence IDs."""
from dataclasses import replace
import pytest

from pb_live_floor_finish_area_source_closed_export import build_live_floor_finish_area_source_traces
from pb_live_ceiling_area_source_closed_export import build_live_ceiling_area_source_traces
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim as finish_claim, _floor, _quantity
from tests.test_live_ceiling_area_quantity_publication import _result


def test_original_floor_finish_and_ceiling_keep_source_traces_without_changes():
    finish = build_live_floor_finish_area_source_traces(
        finish_claim(), workspace_id=13, project_id="source-project"
    )
    assert tuple(finish) == ("floor-finish-q1",)
    assert finish["floor-finish-q1"].workspace_id == 13
    ceiling = build_live_ceiling_area_source_traces(
        _result(), workspace_id=13, project_id="source-project"
    )
    assert len(ceiling) == 1
    assert next(iter(ceiling.values())).workspace_id == 13


@pytest.mark.parametrize("workspace", [True, False, 13.0, 13.8, "13", " 13", -1, 0, None])
@pytest.mark.parametrize("family", ["floor_finish", "ceiling_area"])
def test_metric_surface_trace_cannot_coerce_original_workspace(workspace, family):
    if family == "floor_finish":
        runner = lambda: build_live_floor_finish_area_source_traces(
            finish_claim(), workspace_id=workspace, project_id="source-project"
        )
    else:
        runner = lambda: build_live_ceiling_area_source_traces(
            _result(), workspace_id=workspace, project_id="source-project"
        )
    with pytest.raises(SourceClosedRunConflictError, match="workspace_id"):
        runner()


@pytest.mark.parametrize("padded", [" ev-area", "ev-area "])
def test_final_floor_finish_source_receipts_cannot_be_trimmed(padded):
    floor = replace(_floor(), evidence_ids=("ev-room", padded, "ev-occ", "ev-def"))
    with pytest.raises(SourceClosedRunConflictError, match="source evidence receipts"):
        build_live_floor_finish_area_source_traces(
            finish_claim(floor), workspace_id=13, project_id="source-project"
        )
