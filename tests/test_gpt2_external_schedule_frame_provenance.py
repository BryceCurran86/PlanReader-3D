"""A source schedule title must not claim an unrelated physical plan frame."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

import pb_viewport_segmentation as v

FRAME = (10., 10., 300., 300.)
OUTSIDE = (320., 100., 410., 120.)
INSIDE = (50., 90., 180., 112.)


@pytest.fixture()
def isolated_frame(monkeypatch):
    monkeypatch.setattr(v, "_text_fragments", lambda _page: [])
    monkeypatch.setattr(v, "_frame_candidates_for_title", lambda *a, **k: [FRAME])
    monkeypatch.setattr(v, "_rejected_ownership_frame", lambda *a, **k: False)
    monkeypatch.setattr(v, "_extract_scales_for_bbox", lambda *a, **k: (None, None, False, []))
    return v.ViewportLayoutCalibration(
        median_word_height_pt=8., title_frame_gap_pt=20.,
        minimum_frame_span_pt=25., title_separation_pt=25.,
        page_width_pt=600., page_height_pt=600.,
    )


@pytest.mark.parametrize("kind", [
    v.DrawingViewType.SCHEDULE.value,
    v.DrawingViewType.LEGEND.value,
    v.DrawingViewType.SPECIFICATION.value,
])
def test_external_semantic_table_title_cannot_claim_non_table_plan(
    monkeypatch, isolated_frame, kind,
):
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a: False)
    anchor = v._TitleAnchor("INTERNAL FINISHES SCHEDULE", OUTSIDE, kind)
    viewports, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME,), isolated_frame, page_number=11,
    )
    assert not viewports
    assert consumed == set()


def test_inside_source_frame_remains_admissible_without_grid(
    monkeypatch, isolated_frame,
):
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a: False)
    anchor = v._TitleAnchor(
        "INTERNAL FINISHES SCHEDULE", INSIDE, v.DrawingViewType.SCHEDULE.value
    )
    viewports, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME,), isolated_frame, page_number=2,
    )
    assert consumed == {0}
    assert len(viewports) == 1
    assert viewports[0].bounding_box == FRAME
    assert viewports[0].status == v.ViewportSegmentationStatus.RESOLVED.value


def test_external_schedule_with_source_positive_table_grid_still_admissible(
    monkeypatch, isolated_frame,
):
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a, **k: True)
    anchor = v._TitleAnchor(
        "INTERNAL FINISHES SCHEDULE", OUTSIDE, v.DrawingViewType.SCHEDULE.value
    )
    viewports, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME,), isolated_frame, page_number=5,
    )
    assert consumed == {0}
    assert len(viewports) == 1
    assert viewports[0].status == v.ViewportSegmentationStatus.RESOLVED.value
    assert viewports[0].bounding_box == FRAME


def test_actual_floor_plan_frame_not_changed_by_semantic_table_rule(
    monkeypatch, isolated_frame,
):
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a: False)
    anchor = v._TitleAnchor("FLOOR PLAN", OUTSIDE, v.DrawingViewType.FLOOR_PLAN.value)
    viewports, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME,), isolated_frame, page_number=1,
    )
    assert consumed == {0}
    assert len(viewports) == 1
    assert viewports[0].view_type == v.DrawingViewType.FLOOR_PLAN.value


def test_external_title_with_two_competing_closed_cell_frames_stays_ambiguous(
    monkeypatch, isolated_frame,
):
    # When TWO geometrically bound frames have separate genuine source
    # cell-grid proof, the producer must not arbitrarily choose one.
    second = (10., 340., 160., 480.)
    monkeypatch.setattr(v, "_frame_candidates_for_title", lambda *a, **k: [FRAME, second])
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a, **k: True)
    anchor = v._TitleAnchor(
        "INTERNAL FINISHES SCHEDULE", OUTSIDE, v.DrawingViewType.SCHEDULE.value
    )
    views, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME, second), isolated_frame, page_number=11,
    )
    assert consumed == {0}
    assert len(views) == 1
    assert views[0].status == v.ViewportSegmentationStatus.AMBIGUOUS.value
    assert views[0].bounding_box is None


def test_source_enclosed_title_ignores_other_table_shaped_drawing_frames(
    monkeypatch, isolated_frame,
):
    # The enclosing frame has independent source spatial ownership; the
    # fail-closed external-binding criterion must not erase it.
    second = (10., 340., 160., 480.)
    monkeypatch.setattr(v, "_frame_looks_like_table", lambda *a, **k: True)
    anchor = v._TitleAnchor(
        "INTERNAL FINISHES SCHEDULE", INSIDE, v.DrawingViewType.SCHEDULE.value
    )
    views, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME, second), isolated_frame, page_number=11,
    )
    assert consumed == {0}
    assert len(views) == 1
    assert views[0].bounding_box == FRAME


def test_external_source_line_grid_without_closed_table_cells_abstains(
    monkeypatch, isolated_frame,
):
    # A construction drawing's intersecting wall strokes can resemble a
    # schedule line grid. Source-CLOSED cells are required externally.
    monkeypatch.setattr(
        v, "_frame_looks_like_table",
        lambda *a, **kw: kw.get("allow_line_grid_only", True),
    )
    anchor = v._TitleAnchor(
        "INTERNAL FINISHES SCHEDULE", OUTSIDE, v.DrawingViewType.SCHEDULE.value
    )
    views, consumed = v._frame_resolved_viewports(
        SimpleNamespace(), (anchor,), (FRAME,), isolated_frame, page_number=11,
    )
    assert views == []
    assert consumed == set()
