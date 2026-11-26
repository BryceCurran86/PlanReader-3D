"""Tests for generic same-page figured-dimension scale corroboration & open-plan boundary shadow."""
from __future__ import annotations

from dataclasses import replace
import pytest

from pb_source_same_page_figured_scale_shadow import (
    OpenPlanBoundaryExtractionReport,
    OrthogonalFiguredSpanWitness,
    SamePageFiguredScaleReport,
    ShadowRoomMetricEstimate,
    corroborate_same_page_figured_scale_shadow,
    extract_open_plan_multi_wall_boundary_candidates_shadow,
    measure_room_face_from_same_page_scale_shadow,
)

_SHA = "a" * 64
_PAGE_RECT = (0.0, 0.0, 842.0, 595.0)
_VP_ID = "vp-first-floor-plan"
_VP_RECT = (40.0, 40.0, 760.0, 540.0)


def _w(
    wid: str,
    *,
    page: int = 2,
    viewport_id: str = _VP_ID,
    axis: str = "x",
    mm: float = 3000.0,
    pts: float = 85.03937,
    pids: tuple[int, ...] = (10, 11, 12, 13),
    bbox: tuple[float, float, float, float] = (100.0, 100.0, 185.0, 110.0),
    sha: str = _SHA,
) -> OrthogonalFiguredSpanWitness:
    return OrthogonalFiguredSpanWitness(
        witness_id=wid,
        source_sha256=sha,
        page_number=page,
        viewport_id=viewport_id,
        axis=axis,
        figured_mm=mm,
        span_pdf_pts=pts,
        source_path_ids=pids,
        bbox_pdf_pts=bbox,
    )


def test_same_page_orthogonal_scale_corroborates_room_without_internal_figures() -> None:
    report = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        target_viewport_bbox_pdf_pts=_VP_RECT,
        witnesses=(
            _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937, pids=(10, 11, 12, 13)),
            _w("v1", page=2, axis="y", mm=2400.0, pts=68.031496, pids=(20, 21, 22, 23)),
        ),
        target_room_bbox_pdf_pts=(300.0, 200.0, 380.0, 260.0),
        reference_mm_per_pt_x=35.277778,
        reference_mm_per_pt_y=35.277778,
        reference_page_rect_pts=_PAGE_RECT,
    )
    assert report.status == "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW"
    assert report.viewport_id == _VP_ID
    assert report.commercial_projection_allowed is False
    assert report.shadow_only is True
    assert report.isotropy_error is not None and report.isotropy_error < 1e-4
    assert report.supporting_source_path_ids == (10, 11, 12, 13, 20, 21, 22, 23)

    est = measure_room_face_from_same_page_scale_shadow(
        scale_report=report,
        finished_width_pts=80.0,
        finished_depth_pts=60.0,
    )
    assert est.status == "SHADOW_METRIC_COMPUTED"
    assert est.commercial_projection_allowed is False
    assert est.width_m == pytest.approx(2.822222, rel=1e-4)
    assert est.depth_m == pytest.approx(2.116667, rel=1e-4)
    assert est.area_m2 == pytest.approx(5.973704, rel=1e-4)


def test_cross_page_only_witnesses_cannot_authorize_target_page() -> None:
    report = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h-p1", page=1, axis="x", mm=3000.0, pts=85.03937),
            _w("v-p1", page=1, axis="y", mm=2400.0, pts=68.031496),
        ),
    )
    assert report.status == "ABSTAINED"
    assert "missing_same_page_orthogonal_figured_witnesses" in report.reason_codes


def test_conflicting_same_page_witnesses_veto_scale() -> None:
    report = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937),
            _w("h2", page=2, axis="x", mm=3000.0, pts=95.0),  # >10% disagreement
            _w("v1", page=2, axis="y", mm=2400.0, pts=68.031496),
        ),
    )
    assert report.status == "ABSTAINED"
    assert "same_page_scale_axis_conflict" in report.reason_codes


def test_anisotropic_xy_scale_abstains() -> None:
    report = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937),
            _w("v1", page=2, axis="y", mm=2400.0, pts=75.0),  # anisotropic
        ),
    )
    assert report.status == "ABSTAINED"
    assert "same_page_scale_anisotropy_conflict" in report.reason_codes


def test_reference_calibration_mismatch_and_sha_mismatch_abstain() -> None:
    r_ref = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937),
            _w("v1", page=2, axis="y", mm=2400.0, pts=68.031496),
        ),
        reference_mm_per_pt_x=50.0,
        reference_mm_per_pt_y=50.0,
    )
    assert r_ref.status == "ABSTAINED"
    assert "reference_calibration_mismatch" in r_ref.reason_codes

    r_sha = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(_w("h1", page=2, axis="x", sha="b" * 64),),
    )
    assert r_sha.status == "ABSTAINED"
    assert "cross_revision_witness_sha_mismatch" in r_sha.reason_codes


def test_strict_sha256_and_tolerance_ceiling_enforcement() -> None:
    witnesses = (
        _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937),
        _w("v1", page=2, axis="y", mm=2400.0, pts=68.031496),
    )
    for bad_sha in ("a" * 16, "A" * 64, "z" * 64, ""):
        r = corroborate_same_page_figured_scale_shadow(
            source_sha256=bad_sha,
            page_number=2,
            target_viewport_id=_VP_ID,
            page_rect_pts=_PAGE_RECT,
            witnesses=witnesses,
        )
        assert r.status == "ABSTAINED"
        assert "invalid_scale_input_or_provenance" in r.reason_codes

    r_tol_high = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=witnesses,
        max_rel_tolerance=0.05,
    )
    assert r_tol_high.status == "ABSTAINED"
    assert "scale_tolerance_exceeds_ceiling" in r_tol_high.reason_codes

    r_tol_bool = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=witnesses,
        max_rel_tolerance=True,  # type: ignore[arg-type]
    )
    assert r_tol_bool.status == "ABSTAINED"
    assert "invalid_scale_input_or_provenance" in r_tol_bool.reason_codes


def test_mixed_viewport_and_duplicate_or_untyped_witnesses_abstain() -> None:
    r_mixed_vp = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h1", page=2, viewport_id=_VP_ID, axis="x", mm=3000.0, pts=85.03937),
            _w("v1", page=2, viewport_id="vp-detail-1to20", axis="y", mm=2400.0, pts=68.031496),
        ),
    )
    assert r_mixed_vp.status == "ABSTAINED"
    assert "mixed_viewport_witness_scope_conflict" in r_mixed_vp.reason_codes

    r_outside_vp = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        target_viewport_bbox_pdf_pts=(40.0, 40.0, 400.0, 400.0),
        witnesses=(
            _w("h1", page=2, axis="x", bbox=(100.0, 100.0, 185.0, 110.0)),
            _w("v1", page=2, axis="y", bbox=(500.0, 100.0, 510.0, 180.0)),
        ),
    )
    assert r_outside_vp.status == "ABSTAINED"
    assert "witness_outside_target_viewport_bbox" in r_outside_vp.reason_codes

    r_dup = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("dup-id", page=2, axis="x", mm=3000.0, pts=85.03937),
            _w("dup-id", page=2, axis="y", mm=2400.0, pts=68.031496),
        ),
    )
    assert r_dup.status == "ABSTAINED"
    assert "duplicate_witness_id_conflict" in r_dup.reason_codes

    r_untyped = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=({"witness_id": "h1"},),  # type: ignore[arg-type]
    )
    assert r_untyped.status == "ABSTAINED"
    assert "invalid_witness_type" in r_untyped.reason_codes


def test_shadow_only_immutability_guards() -> None:
    report = corroborate_same_page_figured_scale_shadow(
        source_sha256=_SHA,
        page_number=2,
        target_viewport_id=_VP_ID,
        page_rect_pts=_PAGE_RECT,
        witnesses=(
            _w("h1", page=2, axis="x", mm=3000.0, pts=85.03937),
            _w("v1", page=2, axis="y", mm=2400.0, pts=68.031496),
        ),
    )
    with pytest.raises(ValueError):
        replace(report, commercial_projection_allowed=True)
    est = measure_room_face_from_same_page_scale_shadow(
        scale_report=report, finished_width_pts=50.0, finished_depth_pts=40.0
    )
    with pytest.raises(ValueError):
        replace(est, commercial_projection_allowed=True)


def test_open_plan_multi_wall_boundary_candidate_extraction() -> None:
    drawings = [
        {"width": 1.2, "color": (0.0, 0.0, 0.0), "rect": (100.0, 100.0, 260.0, 101.2)},
        {"width": 1.2, "color": (0.0, 0.0, 0.0), "rect": (100.0, 220.0, 260.0, 221.2)},
        {"width": 1.2, "color": (0.0, 0.0, 0.0), "rect": (100.0, 100.0, 101.2, 220.0)},
        {"width": 0.2, "color": (0.0, 0.0, 0.0), "rect": (100.0, 150.0, 260.0, 150.2)},  # thin hatch ignored
        {"width": 1.2, "color": (0.8, 0.8, 0.8), "rect": (260.0, 100.0, 261.2, 220.0)},  # light gray ignored
    ]
    res = extract_open_plan_multi_wall_boundary_candidates_shadow(
        drawings=drawings,
        source_sha256=_SHA,
        page_number=1,
        seed_point_pdf_pts=(180.0, 160.0),
    )
    assert isinstance(res, OpenPlanBoundaryExtractionReport)
    assert res.status == "BOUNDARY_CANDIDATES_COLLECTED_SHADOW"
    assert len(res.horizontal_candidates) == 2
    assert len(res.vertical_candidates) == 1
    assert res.commercial_projection_allowed is False
    with pytest.raises(ValueError):
        replace(res, commercial_projection_allowed=True)
