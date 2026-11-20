"""#4549-16..20 skew, curves, annex islands, raster-vector dedup, thickness."""
from __future__ import annotations

from pb_source_footprint_geometry_hardening_runtime import (
    PointPoly,
    build_curved_chamfer_boundary,
    dedupe_overlapping_raster_vector,
    detect_disjoint_annex_islands,
    estimate_page_skew_correction,
    infer_shared_wall_thickness_role,
    run_footprint_geometry_hardening_stage,
)


def test_16_skew_from_consistent_spans():
    r = estimate_page_skew_correction(
        reference_horizontal_spans=(
            ((0, 0), (100, 2)),
            ((0, 50), (80, 51.5)),
        ),
    )
    assert r["status"] == "CANDIDATE"
    assert abs(r["skew_degrees"]) < 2.0


def test_17_source_preserving_curve_not_densified():
    r = build_curved_chamfer_boundary(((0, 0), (10, 5), (20, 0), (20, 20), (0, 20)))
    assert r["status"] == "CANDIDATE"
    assert r["densified"] is False
    assert r["polygon_pdf_pts"][0] == r["polygon_pdf_pts"][-1]


def test_18_annex_islands_not_silently_dropped():
    r = detect_disjoint_annex_islands(
        (
            PointPoly(((0, 0), (100, 0), (100, 80), (0, 80), (0, 0)), role="footprint"),
            PointPoly(((120, 0), (160, 0), (160, 40), (120, 40), (120, 0)), role="garage"),
        ),
    )
    assert r["retained_annex_count"] == 1
    assert r["retained_annexes"][0]["silently_dropped"] is False


def test_19_raster_overlap_prefers_vector_keeps_unmatched():
    r = dedupe_overlapping_raster_vector(
        raster_segments=(((0, 0), (50, 0)), ((200, 0), (250, 0))),
        vector_segments=(((0, 0), (50, 0)),),
    )
    assert r["raster_suppressed_overlap"] == 1
    assert r["raster_retained_unmatched"] == 1
    assert r["structural_evidence_eliminated"] is False


def test_20_thickness_roles_and_conflict_abstain():
    assert infer_shared_wall_thickness_role(
        thickness_pt=6.0, exterior_labelled=True,
    )["role"] == "external"
    assert infer_shared_wall_thickness_role(
        thickness_pt=3.0, party_labelled=True, exterior_labelled=True,
    )["status"] == "ABSTAINED"


def test_bundle_fail_closed():
    b = run_footprint_geometry_hardening_stage(
        horizontal_spans=(((0, 0), (100, 0)), ((0, 10), (90, 0.2))),
        curved_controls=((0, 0), (5, 2), (10, 0)),
        islands=(PointPoly(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)), role="footprint"),),
        thickness_pt=6.0,
        exterior_labelled=True,
    )
    assert b["measurement_authorized"] is False
    assert "16" in b["tasks_covered"]
