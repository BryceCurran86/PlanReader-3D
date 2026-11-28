"""Tests for generic coincident fixture boundary support shadow (Item 1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb_source_coincident_fixture_boundary_support_shadow import (
    evaluate_coincident_fixture_boundary_support_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "a" * 64


def _seg(x1: float, y1: float, x2: float, y2: float, *, width: float = 1.2, color=(0.0, 0.0, 0.0), typ="s"):
    return {
        "type": typ,
        "width": width,
        "color": color,
        "items": [("l", (x1, y1), (x2, y2))],
    }


def test_four_structural_walls_corroborated_directly():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),   # L
        _seg(90, 10, 90, 60, width=1.2),   # R
        _seg(10, 10, 90, 10, width=1.2),   # T
        _seg(10, 60, 90, 60, width=1.2),   # B
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert res.supported is True
    assert res.support_mode == "four_structural_walls"
    assert res.structural_sides_passed == 4
    assert res.commercial_projection_allowed is False
    assert res.shadow_only is True


def test_three_walls_plus_exact_coincident_fixture_edge_and_backing_wall_corroborated():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),   # L structural
        _seg(90, 10, 90, 60, width=1.2),   # R structural
        _seg(10, 10, 90, 10, width=1.2),   # T structural
        _seg(10, 60, 90, 60, width=0.48),  # B exact coincident fixture/hob line (dy=0, cov=1.0)
        _seg(10, 85, 90, 85, width=1.2),   # Exterior structural wall behind built-in fixture (dy=25pt)
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=152,
    )
    assert res.supported is True
    assert res.support_mode == "three_structural_walls_plus_coincident_fixture_edge"
    assert res.coincident_fixture_side == "B"
    assert res.commercial_projection_allowed is False


def test_nearby_unrelated_offset_mark_rejected_no_blanket_snap_widening():
    """A 0.48pt line offset by 1.5pt (>0.25pt) MUST be rejected — no snap widening."""
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),
        _seg(90, 10, 90, 60, width=1.2),
        _seg(10, 10, 90, 10, width=1.2),
        _seg(10, 61.5, 90, 61.5, width=0.48),  # 1.5pt away -> NOT coincident
        _seg(10, 85, 90, 85, width=1.2),
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert res.supported is False
    assert "coincident_boundary_stroke_unavailable" in res.reason_codes


def test_short_dimension_tick_or_partial_stroke_rejected():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),
        _seg(90, 10, 90, 60, width=1.2),
        _seg(10, 10, 90, 10, width=1.2),
        _seg(10, 60, 40, 60, width=0.48),  # only 37.5% coverage (<90%)
        _seg(10, 85, 90, 85, width=1.2),
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert res.supported is False
    assert "coincident_boundary_coverage_incomplete" in res.reason_codes


def test_thin_hatch_line_under_0_40pt_rejected():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),
        _seg(90, 10, 90, 60, width=1.2),
        _seg(10, 10, 90, 10, width=1.2),
        _seg(10, 60, 90, 60, width=0.24),  # hairline hatch weight <0.40pt
        _seg(10, 85, 90, 85, width=1.2),
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert res.supported is False
    assert "coincident_boundary_stroke_unavailable" in res.reason_codes


def test_missing_exterior_backing_wall_abstains():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),
        _seg(90, 10, 90, 60, width=1.2),
        _seg(10, 10, 90, 10, width=1.2),
        _seg(10, 60, 90, 60, width=0.48),
    ]
    res = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert res.supported is False
    assert "exterior_structural_backing_wall_unavailable" in res.reason_codes


def test_missing_interior_hatch_or_only_two_walls_abstains():
    drawings = [
        _seg(10, 10, 10, 60, width=1.2),
        _seg(90, 10, 90, 60, width=1.2),
        _seg(10, 10, 90, 10, width=1.2),
        _seg(10, 60, 90, 60, width=0.48),
        _seg(10, 85, 90, 85, width=1.2),
    ]
    r_no_hatch = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings, bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=0,
    )
    assert r_no_hatch.supported is False
    assert "interior_finish_hatch_uncorroborated" in r_no_hatch.reason_codes

    r_two_walls = evaluate_coincident_fixture_boundary_support_shadow(
        drawings=drawings[:2] + drawings[3:], bbox_pts=(10, 10, 90, 60),
        source_sha256=_SHA, page_number=2, hatch_support_count=50,
    )
    assert r_two_walls.supported is False
    assert "insufficient_structural_wall_sides" in r_two_walls.reason_codes


def test_zero_job_specific_shared_source_rules():
    path = Path(__file__).resolve().parents[1] / "pb_source_coincident_fixture_boundary_support_shadow.py"
    assert audit_shared_source(path.read_text(encoding="utf-8"), filename=path.name) == ()
