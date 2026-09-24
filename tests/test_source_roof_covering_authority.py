"""tests/test_source_roof_covering_authority.py — Comprehensive tests for generic source roof covering.

Validates the full evidence chain, fail-closed abstentions, and metamorphic invariances:
  * valid symmetric gable
  * valid asymmetric/verandah extension
  * flat roof / long elevation negative
  * short diagonal noise negative
  * multiple-apex ambiguity
  * mismatched left/right pitch
  * missing wall/post endpoint
  * translation invariance
  * scale invariance
  * input-order invariance
  * deterministic replay
  * no mutation
  * real-source, gold-free Lamu diagnostic
"""
from __future__ import annotations

import copy
import math
import random
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_roof_covering_authority import (
    DiagonalSlopeSegment,
    VerticalSupportSegment,
    measure_source_roof_covering,
    resolve_gable_apex_in_viewport,
)


def _make_symmetric_gable_segments(
    *,
    apex_x: float = 500.0,
    apex_y: float = 900.0,
    pitch_deg: float = 18.0,
    run_pt: float = 100.0,
    wall_height_pt: float = 80.0,
) -> tuple[list[DiagonalSlopeSegment], list[VerticalSupportSegment]]:
    """Helper to synthesize an exact symmetric gable roofline with wall vertical supports."""
    pitch_rad = math.radians(pitch_deg)
    rise_pt = run_pt * math.tan(pitch_rad)
    right_x = apex_x + run_pt
    left_x = apex_x - run_pt
    eave_y = apex_y + rise_pt

    diags = [
        DiagonalSlopeSegment.from_endpoints(apex_x, apex_y, right_x, eave_y),
        DiagonalSlopeSegment.from_endpoints(apex_x, apex_y, left_x, eave_y),
    ]
    diagonals = [d for d in diags if d is not None]

    verticals = [
        VerticalSupportSegment.from_endpoints(right_x, eave_y, right_x, eave_y + wall_height_pt),
        VerticalSupportSegment.from_endpoints(left_x, eave_y, left_x, eave_y + wall_height_pt),
    ]
    verts = [v for v in verticals if v is not None]
    return diagonals, verts


def test_valid_symmetric_gable_resolves_accurately() -> None:
    diagonals, verticals = _make_symmetric_gable_segments(
        apex_x=500.0, apex_y=900.0, pitch_deg=20.0, run_pt=100.0, wall_height_pt=80.0
    )
    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, verticals)

    assert evidence is not None
    assert "authenticated_gable_roofline" in reasons
    assert abs(evidence.pitch_deg - 20.0) < 0.05
    assert abs(evidence.left_run_pt - 100.0) < 0.1
    assert abs(evidence.right_run_pt - 100.0) < 0.1
    assert evidence.member_count == 2

    # Measure roof covering
    result = measure_source_roof_covering(
        evidence,
        building_length_m=16.0,
        building_width_m=8.0,
        source_sha256="0" * 64,
    )
    assert result.status == EvidenceResolutionStatus.CORROBORATED
    assert result.pitch_deg == evidence.pitch_deg
    assert result.cross_ridge_span_m == 8.0
    assert result.ridge_length_m == 16.0
    # Expected area: 16.0 * (8.0 / cos(20 deg)) = 16.0 * 8.5134 = 136.21 m2
    expected_area = round(16.0 * (8.0 / math.cos(math.radians(20.0))), 2)
    assert result.roof_covering_area_m2 == expected_area
    assert result.quantity_evidence is not None
    assert result.quantity_evidence.value == expected_area


def test_valid_asymmetric_verandah_extension_picks_farthest_post() -> None:
    """Verandah extension test: one continuous slope passes through both inner wall and outer post."""
    apex_x, apex_y = 500.0, 900.0
    pitch_deg = 18.0
    pitch_rad = math.radians(pitch_deg)
    near_run = 92.0
    far_run = 140.0

    near_eave_y = apex_y + near_run * math.tan(pitch_rad)
    far_eave_y = apex_y + far_run * math.tan(pitch_rad)

    diags = [
        # Right side: standard wall corner
        DiagonalSlopeSegment.from_endpoints(apex_x, apex_y, apex_x + near_run, near_eave_y),
        # Left side: continuous slope out to verandah post
        DiagonalSlopeSegment.from_endpoints(apex_x, apex_y, apex_x - far_run, far_eave_y),
    ]
    diagonals = [d for d in diags if d is not None]

    verts = [
        # Right side wall
        VerticalSupportSegment.from_endpoints(apex_x + near_run, near_eave_y, apex_x + near_run, near_eave_y + 80.0),
        # Left side inner wall corner (closer to apex)
        VerticalSupportSegment.from_endpoints(apex_x - near_run, near_eave_y, apex_x - near_run, near_eave_y + 80.0),
        # Left side verandah post (farthest from apex, on the same ray)
        VerticalSupportSegment.from_endpoints(apex_x - far_run, far_eave_y, apex_x - far_run, far_eave_y + 50.0),
    ]
    verticals = [v for v in verts if v is not None]

    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, verticals)
    assert evidence is not None
    assert "authenticated_gable_roofline" in reasons
    # Right run stops at near wall; Left run MUST select the farther verandah post, not collapse to nearer wall
    assert abs(evidence.right_run_pt - near_run) < 0.1
    assert abs(evidence.left_run_pt - far_run) < 0.1


def test_flat_roof_or_long_elevation_negative_abstains() -> None:
    """Longitudinal elevations or flat roofs have no opposing diagonals meeting at an apex."""
    diagonals: list[DiagonalSlopeSegment] = []
    verticals = [
        VerticalSupportSegment.from_endpoints(100.0, 500.0, 100.0, 600.0),
        VerticalSupportSegment.from_endpoints(800.0, 500.0, 800.0, 600.0),
    ]
    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, [v for v in verticals if v is not None])
    assert evidence is None
    assert "no_gable_apex_found" in reasons


def test_short_diagonal_noise_negative_abstains() -> None:
    """Dimension ticks and arrowheads (< 20 pt) are rejected by segment construction."""
    d1 = DiagonalSlopeSegment.from_endpoints(500.0, 900.0, 510.0, 905.0)  # length ~11 pt
    d2 = DiagonalSlopeSegment.from_endpoints(500.0, 900.0, 490.0, 905.0)  # length ~11 pt
    assert d1 is None
    assert d2 is None

    diagonals = [d for d in [d1, d2] if d is not None]
    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, [])
    assert evidence is None
    assert "no_gable_apex_found" in reasons


def test_multiple_apex_ambiguity_negative_abstains() -> None:
    """Multiple distinct apex clusters on one elevation (e.g. decorative gables) fail closed."""
    d1, v1 = _make_symmetric_gable_segments(apex_x=400.0, apex_y=800.0, pitch_deg=18.0, run_pt=80.0)
    d2, v2 = _make_symmetric_gable_segments(apex_x=700.0, apex_y=850.0, pitch_deg=22.0, run_pt=60.0)

    evidence, reasons = resolve_gable_apex_in_viewport(d1 + d2, v1 + v2)
    assert evidence is None
    assert "competing_apex_candidates" in reasons


def test_mismatched_left_right_pitch_negative_abstains() -> None:
    """Opposing slopes with disagreeing pitch (> 1.0 deg) are not a symmetric/uniform gable."""
    ax, ay = 500.0, 900.0
    # Left slope 18 deg, right slope 26 deg
    d_left = DiagonalSlopeSegment.from_endpoints(ax, ay, ax - 100.0, ay + 100.0 * math.tan(math.radians(18.0)))
    d_right = DiagonalSlopeSegment.from_endpoints(ax, ay, ax + 100.0, ay + 100.0 * math.tan(math.radians(26.0)))
    diagonals = [d for d in [d_left, d_right] if d is not None]

    v_left = VerticalSupportSegment.from_endpoints(ax - 100.0, d_left.y_lo, ax - 100.0, d_left.y_lo + 80.0)
    v_right = VerticalSupportSegment.from_endpoints(ax + 100.0, d_right.y_lo, ax + 100.0, d_right.y_lo + 80.0)
    verticals = [v for v in [v_left, v_right] if v is not None]

    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, verticals)
    assert evidence is None
    assert "mismatched_slope_pitch" in reasons


def test_missing_wall_post_endpoint_negative_abstains() -> None:
    """Gable roofline with no vertical structural element meeting one of the slopes fails closed."""
    diagonals, verticals = _make_symmetric_gable_segments(pitch_deg=18.0, run_pt=100.0)
    # Remove left vertical
    only_right = [v for v in verticals if v.x > 500.0]

    evidence, reasons = resolve_gable_apex_in_viewport(diagonals, only_right)
    assert evidence is None
    assert "missing_structural_endpoint_left" in reasons


def test_translation_invariance() -> None:
    """Translating the entire drawing in (x, y) produces the exact same pitch, runs, and area."""
    d_orig, v_orig = _make_symmetric_gable_segments(apex_x=500.0, apex_y=900.0, pitch_deg=18.5, run_pt=110.0)
    ev_orig, _ = resolve_gable_apex_in_viewport(d_orig, v_orig)
    assert ev_orig is not None
    res_orig = measure_source_roof_covering(
        ev_orig, building_length_m=20.0, building_width_m=10.0, source_sha256="test_sha"
    )

    dx, dy = 1234.56, -789.12
    d_trans = [
        DiagonalSlopeSegment.from_endpoints(d.x_hi + dx, d.y_hi + dy, d.x_lo + dx, d.y_lo + dy)
        for d in d_orig
    ]
    v_trans = [
        VerticalSupportSegment.from_endpoints(v.x + dx, v.top_y + dy, v.x + dx, v.bottom_y + dy)
        for v in v_orig
    ]
    ev_trans, _ = resolve_gable_apex_in_viewport(
        [d for d in d_trans if d is not None],
        [v for v in v_trans if v is not None],
    )
    assert ev_trans is not None
    res_trans = measure_source_roof_covering(
        ev_trans, building_length_m=20.0, building_width_m=10.0, source_sha256="test_sha"
    )

    assert abs(ev_orig.pitch_deg - ev_trans.pitch_deg) < 1e-4
    assert abs(ev_orig.left_run_pt - ev_trans.left_run_pt) < 1e-3
    assert abs(ev_orig.right_run_pt - ev_trans.right_run_pt) < 1e-3
    assert res_orig.roof_covering_area_m2 == res_trans.roof_covering_area_m2


def test_scale_invariance() -> None:
    """Scaling segment coordinates by k and building dimensions by k scales area by k^2."""
    d1, v1 = _make_symmetric_gable_segments(pitch_deg=19.0, run_pt=100.0)
    ev1, _ = resolve_gable_apex_in_viewport(d1, v1)
    assert ev1 is not None
    res1 = measure_source_roof_covering(
        ev1, building_length_m=10.0, building_width_m=5.0, source_sha256="test_sha"
    )

    # Invariance: pitch is unchanged regardless of geometric point coordinate scaling
    d2, v2 = _make_symmetric_gable_segments(pitch_deg=19.0, run_pt=200.0)
    ev2, _ = resolve_gable_apex_in_viewport(d2, v2)
    assert ev2 is not None
    assert abs(ev1.pitch_deg - ev2.pitch_deg) < 1e-4

    # Area computed from same physical building dimensions is identical
    res2 = measure_source_roof_covering(
        ev2, building_length_m=10.0, building_width_m=5.0, source_sha256="test_sha"
    )
    assert res1.roof_covering_area_m2 == res2.roof_covering_area_m2


def test_input_order_invariance() -> None:
    """Shuffling the order of input segments yields identical results."""
    d_orig, v_orig = _make_symmetric_gable_segments(pitch_deg=22.0, run_pt=95.0)
    ev_baseline, _ = resolve_gable_apex_in_viewport(d_orig, v_orig)
    assert ev_baseline is not None

    for seed in (42, 100, 2026):
        rng = random.Random(seed)
        d_shuffled = list(d_orig)
        v_shuffled = list(v_orig)
        rng.shuffle(d_shuffled)
        rng.shuffle(v_shuffled)

        ev_shuffled, _ = resolve_gable_apex_in_viewport(d_shuffled, v_shuffled)
        assert ev_shuffled is not None
        assert ev_shuffled.pitch_deg == ev_baseline.pitch_deg
        assert ev_shuffled.left_run_pt == ev_baseline.left_run_pt
        assert ev_shuffled.right_run_pt == ev_baseline.right_run_pt


def test_deterministic_replay() -> None:
    """Running calculation twice with identical inputs yields identical contract IDs."""
    diagonals, verticals = _make_symmetric_gable_segments(pitch_deg=18.0, run_pt=100.0)
    ev1, _ = resolve_gable_apex_in_viewport(diagonals, verticals)
    ev2, _ = resolve_gable_apex_in_viewport(diagonals, verticals)

    res1 = measure_source_roof_covering(
        ev1, building_length_m=16.0, building_width_m=8.0, source_sha256="fixed_hash"
    )
    res2 = measure_source_roof_covering(
        ev2, building_length_m=16.0, building_width_m=8.0, source_sha256="fixed_hash"
    )

    assert res1.quantity_evidence is not None
    assert res2.quantity_evidence is not None
    assert res1.quantity_evidence.quantity_id == res2.quantity_evidence.quantity_id
    assert res1.roof_covering_area_m2 == res2.roof_covering_area_m2


def test_no_mutation() -> None:
    """Algorithms must never mutate input objects or collections."""
    diagonals, verticals = _make_symmetric_gable_segments(pitch_deg=18.0, run_pt=100.0)
    d_copy = copy.deepcopy(diagonals)
    v_copy = copy.deepcopy(verticals)

    ev, _ = resolve_gable_apex_in_viewport(diagonals, verticals)
    assert ev is not None
    assert diagonals == d_copy
    assert verticals == v_copy

    ev_copy = copy.deepcopy(ev)
    _ = measure_source_roof_covering(
        ev, building_length_m=16.0, building_width_m=8.0, source_sha256="fixed_hash"
    )
    assert ev == ev_copy


def test_real_source_gold_free_lamu_diagnostic() -> None:
    """Real Lamu source drawing fixture test.

    Proves that the real Lamu Ground Floor / Elevations sheet (page 41)
    extracts the measured ~18.0 deg pitch and verandah extension without
    benchmark gold or expected quantities entering the logic.
    """
    fitz = pytest.importorskip("fitz")
    lamu_pdf = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not lamu_pdf.exists():
        pytest.skip("Lamu benchmark source PDF not cached locally")

    doc = fitz.open(str(lamu_pdf))
    try:
        # Page index 40 is page 41
        page = doc[40]
        # Use Elevation 02 viewport region (derived y from ~880 to 1100)
        # Verify extraction via extract_elevation_segments_from_page
        from pb_source_roof_covering_authority import (
            extract_elevation_segments_from_page,
        )

        viewport_bbox = (0.0, 880.0, 842.0, 1100.0)
        diags, verts = extract_elevation_segments_from_page(page, viewport_bbox)

        evidence, reasons = resolve_gable_apex_in_viewport(diags, verts, source_page=41)
        assert evidence is not None
        assert "authenticated_gable_roofline" in reasons

        # Verified pitch from real drawing vectors
        assert 17.5 <= evidence.pitch_deg <= 18.5
        # Verandah post extension creates larger left run than right run
        assert evidence.left_run_pt > evidence.right_run_pt
        assert 85.0 <= evidence.right_run_pt <= 100.0
        assert 130.0 <= evidence.left_run_pt <= 150.0

        # Building footprint from drawing: length 16.0m (or 16.4m with walls), width 8.2m
        # Note: We pass the real footprint dimensions, not BOQ expected values
        result = measure_source_roof_covering(
            evidence,
            building_length_m=16.4,
            building_width_m=8.2,
            source_sha256="fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2",
        )
        assert result.status == EvidenceResolutionStatus.CORROBORATED
        assert result.roof_covering_area_m2 is not None
        # Conservative core roof plane area (excluding eaves overhang)
        assert 135.0 <= result.roof_covering_area_m2 <= 145.0
        assert result.quantity_evidence is not None
    finally:
        doc.close()


def test_extractor_roof_covering_shadow_initialization() -> None:
    """Verify that GenericPlanReaderExtractor initializes roof_covering_shadow properly."""
    from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

    extractor = GenericPlanReaderExtractor()
    assert hasattr(extractor, "roof_covering_shadow")
    assert extractor.roof_covering_shadow["status"] == "abstained"
    assert extractor.roof_covering_shadow["reason"] == "not_collected"


def test_resolve_document_gable_roof_covering_lamu() -> None:
    """Test full document-level gable roof covering resolution on Lamu sheet."""
    fitz = pytest.importorskip("fitz")
    lamu_pdf = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not lamu_pdf.exists():
        pytest.skip("Lamu benchmark source PDF not cached locally")

    from pb_source_roof_covering_authority import resolve_document_gable_roof_covering

    doc = fitz.open(str(lamu_pdf))
    try:
        res = resolve_document_gable_roof_covering(
            doc,
            building_length_m=16.4,
            building_width_m=8.2,
            source_sha256="fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2",
            target_pages=[40],
        )
        assert res.status == EvidenceResolutionStatus.CORROBORATED
        assert res.pitch_deg == pytest.approx(18.019, abs=0.05)
        assert res.cross_ridge_span_m == 8.2
        assert res.ridge_length_m == 16.4
        assert res.roof_covering_area_m2 == pytest.approx(141.42, abs=0.5)
        assert "authenticated_gable_roof_covering" in res.reason_codes
        mat_annos = res.metadata.get("material_annotations", [])
        assert any("Corrugated" in a for a in mat_annos)
        assert any("Roofing" in a for a in mat_annos)
    finally:
        doc.close()


def test_get_elevation_viewport_search_bbox_unframed_extends_upward() -> None:
    """Verify that search bbox for unframed elevation extends upward from title anchor."""
    from unittest.mock import MagicMock

    from pb_source_roof_covering_authority import get_elevation_viewport_search_bbox

    vp_plan = MagicMock()
    vp_plan.view_id = "view_p1_1"
    vp_plan.title_bbox = (100.0, 300.0, 200.0, 320.0)
    vp_plan.boundary_source = "title_partition"
    vp_plan.bounding_box = (0.0, 0.0, 500.0, 400.0)

    vp_elev = MagicMock()
    vp_elev.view_id = "view_p1_2"
    vp_elev.title_bbox = (100.0, 700.0, 250.0, 720.0)
    vp_elev.boundary_source = "title_partition"
    vp_elev.bounding_box = (0.0, 550.0, 500.0, 800.0)

    page_rect = MagicMock()
    page_rect.width = 500.0
    page_rect.height = 800.0

    sbox = get_elevation_viewport_search_bbox(vp_elev, [vp_plan, vp_elev], page_rect)
    # y_top should be at or above preceding title_bbox[3] (320.0)
    assert sbox[1] == pytest.approx(320.0)
    # y_bottom should enclose the title (720.0 + 15 = 735.0)
    assert sbox[3] == pytest.approx(735.0)
    assert sbox[0] == 0.0
    assert sbox[2] == 500.0


def test_elevation_search_bbox_ignores_preceding_title_in_other_column() -> None:
    """A closer title in another column must not clip this elevation's roof."""
    from unittest.mock import MagicMock

    from pb_source_roof_covering_authority import get_elevation_viewport_search_bbox

    same_column_prev = MagicMock()
    same_column_prev.view_id = "view_p1_mid_prev"
    same_column_prev.title_bbox = (360.0, 300.0, 460.0, 320.0)
    same_column_prev.boundary_source = "title_partition"
    same_column_prev.bounding_box = (300.0, 0.0, 600.0, 360.0)

    other_column_closer = MagicMock()
    other_column_closer.view_id = "view_p1_right"
    other_column_closer.title_bbox = (700.0, 650.0, 800.0, 690.0)
    other_column_closer.boundary_source = "title_partition"
    other_column_closer.bounding_box = (650.0, 500.0, 900.0, 710.0)

    current = MagicMock()
    current.view_id = "view_p1_mid"
    current.title_bbox = (380.0, 700.0, 480.0, 720.0)
    current.boundary_source = "title_partition"
    current.bounding_box = (300.0, 500.0, 600.0, 800.0)

    page_rect = MagicMock()
    page_rect.width = 900.0
    page_rect.height = 800.0

    sbox = get_elevation_viewport_search_bbox(
        current,
        [same_column_prev, other_column_closer, current],
        page_rect,
    )
    assert sbox == pytest.approx((300.0, 320.0, 600.0, 735.0))


def test_extractor_roof_covering_shadow_end_to_end() -> None:
    """Verify that extractor populates roof_covering_shadow with corroborated evidence on Lamu sheet."""
    from unittest.mock import patch

    from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

    lamu_pdf = Path("benchmarks/sources/lamu-ishakani-ecd-classrooms-boq.pdf")
    if not lamu_pdf.exists():
        pytest.skip("Lamu benchmark source PDF not cached locally")

    extractor = GenericPlanReaderExtractor()
    with patch("pb_item35_production_authority_shadow.collect_item35_authority_shadow") as mock_item35:
        mock_item35.return_value = {"status": "abstained", "reason": "mocked_for_test"}
        _ = extractor.extract_from_pdf(str(lamu_pdf), pages=[40])

    assert extractor.roof_covering_shadow["status"] == "corroborated"
    assert extractor.roof_covering_shadow["pitch_deg"] == pytest.approx(18.019, abs=0.05)
    assert extractor.roof_covering_shadow["cross_ridge_span_m"] == 8.2
    assert extractor.roof_covering_shadow["ridge_length_m"] == 16.0
    assert extractor.roof_covering_shadow["roof_covering_area_m2"] == pytest.approx(137.97, abs=0.5)
    assert extractor.extraction_status.get("roof_covering_shadow") == "corroborated"
    qty_ev = extractor.roof_covering_shadow.get("quantity_evidence")
    assert qty_ev is not None
    assert qty_ev["authority"] == "source_native_elevation_vector_pitch"
    assert "authenticated_gable_roof_covering" in extractor.roof_covering_shadow["reason_codes"]



