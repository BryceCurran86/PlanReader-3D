"""Tests for pb_source_room_figured_dimension_witness_shadow.py (Items 18 & 19).

Proves producer-owned figured room dimension and wall witness recovery:
- Positive synthetic proof of room face internal wall witness alignment.
- Rejection of missing orientation pairs, unaligned witness lines, scale inconsistency.
- Conflict on competing/ambiguous dimension pairs (never nearest/first).
- Strict non-publishing shadow gates (commercial_projection_allowed=False, takeoff_eligible=False).
- Metamorphic translation invariance and no-mutation checks.
"""

from __future__ import annotations

import copy

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_figured_dimension_witness_shadow import (
    COMPETING_FIGURED_DIMENSION_PAIRS,
    DIMENSION_ORIENTATION_PAIR_UNAVAILABLE,
    INVALID_ROOM_POLYGON,
    SOURCE_ROOM_FIGURED_WITNESS_RESOLVED,
    WITNESS_WALL_ALIGNMENT_UNRESOLVED,
    SourceBoundDimensionCandidate,
    SourceRoomFaceBoundaryEdge,
    SourceRoomFiguredWitnessSelector,
    evaluate_source_room_figured_witness_shadow,
)

SAMPLE_SHA = "a" * 64


def _make_selector(
    *,
    document_id: str = "doc_test_1",
    revision_id: str = "rev_test_1",
    source_sha256: str = SAMPLE_SHA,
    snapshot_id: str = "snap_test_1",
    page_id: str = "7",
    physical_room_id: str = "room_laundry_1",
    room_label: str = "LAUNDRY",
) -> SourceRoomFiguredWitnessSelector:
    return SourceRoomFiguredWitnessSelector(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        physical_room_id=physical_room_id,
        room_label=room_label,
    )


def _make_room_geometry(
    x0: float = 100.0,
    y0: float = 100.0,
    w_pt: float = 165.5,
    h_pt: float = 504.4,
):
    """Return rectangle polygon and four bounding wall edges."""
    x1 = x0 + w_pt
    y1 = y0 + h_pt
    polygon = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    edges = (
        SourceRoomFaceBoundaryEdge(
            wall_id="wall_north", start_pt=(x0, y0), end_pt=(x1, y0)
        ),
        SourceRoomFaceBoundaryEdge(
            wall_id="wall_east", start_pt=(x1, y0), end_pt=(x1, y1)
        ),
        SourceRoomFaceBoundaryEdge(
            wall_id="wall_south", start_pt=(x1, y1), end_pt=(x0, y1)
        ),
        SourceRoomFaceBoundaryEdge(
            wall_id="wall_west", start_pt=(x0, y1), end_pt=(x0, y0)
        ),
    )
    return polygon, edges


def test_positive_room_figured_witness_candidate():
    """Authentic rectangular room face with matching horizontal and vertical dimensions."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 165.5, 504.4)

    # 1655 mm wide, 5044 mm high (scale = 0.1 pt/mm)
    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_1655",
        value_mm=1655.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 80.0), (265.5, 80.0)),
        witness_geometries=(
            (100.0, 75.0, 100.0, 105.0),
            (265.5, 75.0, 265.5, 105.0),
        ),
        witness_observation_ids=("obs_w_left", "obs_w_right"),
    )
    v_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_v_5044",
        value_mm=5044.0,
        orientation="vertical",
        endpoints_pt=((280.0, 100.0), (280.0, 604.4)),
        witness_geometries=(
            (260.0, 100.0, 285.0, 100.0),
            (260.0, 604.4, 285.0, 604.4),
        ),
        witness_observation_ids=("obs_w_top", "obs_w_bottom"),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim, v_dim),
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_ROOM_FIGURED_WITNESS_RESOLVED in result.reason_codes
    assert result.record is not None
    rec = result.record
    assert rec.physical_room_id == "room_laundry_1"
    assert rec.room_label == "LAUNDRY"
    assert rec.horizontal_value_mm == 1655.0
    assert rec.vertical_value_mm == 5044.0
    assert rec.figured_area_m2 == pytest.approx(8.34782, abs=1e-5)
    assert rec.horizontal_bounding_wall_ids == ("wall_east", "wall_west")
    assert rec.vertical_bounding_wall_ids == ("wall_north", "wall_south")
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False
    assert rec.diagnostic_only is True


def test_missing_orientation_dimension_pair_unavailable():
    """Fails closed when vertical dimension is missing."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 165.5, 504.4)

    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_1655",
        value_mm=1655.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 80.0), (265.5, 80.0)),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim,),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert DIMENSION_ORIENTATION_PAIR_UNAVAILABLE in result.reason_codes
    assert result.record is None


def test_unaligned_witness_lines_abstains():
    """Fails closed when witness lines are offset beyond snap tolerance."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 165.5, 504.4)

    # Offset horizontal dimension by 10 pt (beyond 2.5 pt tolerance)
    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_offset",
        value_mm=1655.0,
        orientation="horizontal",
        endpoints_pt=((110.0, 80.0), (275.5, 80.0)),
    )
    v_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_v_5044",
        value_mm=5044.0,
        orientation="vertical",
        endpoints_pt=((280.0, 100.0), (280.0, 604.4)),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim, v_dim),
        snap_tolerance_pt=2.5,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert WITNESS_WALL_ALIGNMENT_UNRESOLVED in result.reason_codes
    assert result.record is None


def test_scale_inconsistent_dimension_pair_abstains():
    """Fails closed when figured millimeters contradict the geometric aspect ratio."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 200.0, 200.0)  # 1:1 aspect ratio

    # Dimension values give 1:4 ratio (1000mm x 4000mm)
    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_1000",
        value_mm=1000.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 80.0), (300.0, 80.0)),
    )
    v_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_v_4000",
        value_mm=4000.0,
        orientation="vertical",
        endpoints_pt=((320.0, 100.0), (320.0, 300.0)),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim, v_dim),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert WITNESS_WALL_ALIGNMENT_UNRESOLVED in result.reason_codes
    assert result.record is None


def test_competing_dimension_pairs_fails_closed():
    """Two competing dimension pairs for the same room face result in CONFLICT."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 200.0, 200.0)

    # First pair: 2000mm x 2000mm
    h_dim1 = SourceBoundDimensionCandidate(
        dimension_id="dim_h_2000_a",
        value_mm=2000.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 80.0), (300.0, 80.0)),
    )
    v_dim1 = SourceBoundDimensionCandidate(
        dimension_id="dim_v_2000_a",
        value_mm=2000.0,
        orientation="vertical",
        endpoints_pt=((320.0, 100.0), (320.0, 300.0)),
    )
    # Second competing pair: 2050mm x 2050mm with identical endpoints
    h_dim2 = SourceBoundDimensionCandidate(
        dimension_id="dim_h_2050_b",
        value_mm=2050.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 70.0), (300.0, 70.0)),
    )
    v_dim2 = SourceBoundDimensionCandidate(
        dimension_id="dim_v_2050_b",
        value_mm=2050.0,
        orientation="vertical",
        endpoints_pt=((330.0, 100.0), (330.0, 300.0)),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim1, v_dim1, h_dim2, v_dim2),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FIGURED_DIMENSION_PAIRS in result.reason_codes
    assert result.record is None


def test_invalid_polygon_fails_closed():
    """Degenerate polygon fails closed."""
    selector = _make_selector()
    degenerate = ((0.0, 0.0), (1.0, 1.0))
    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=degenerate,
        bounding_edges=(),
        dimensions=(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert INVALID_ROOM_POLYGON in result.reason_codes


def test_invalid_selector_fails():
    """Selector with invalid SHA must raise ValueError."""
    with pytest.raises(ValueError, match="source_sha256"):
        _make_selector(source_sha256="not_a_sha")


def test_metamorphic_translation_invariance():
    """Translating the entire room and dimension geometry preserves the evaluated result."""
    selector = _make_selector()
    dx, dy = 350.0, 500.0
    polygon, edges = _make_room_geometry(100.0 + dx, 100.0 + dy, 165.5, 504.4)

    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_1655_t",
        value_mm=1655.0,
        orientation="horizontal",
        endpoints_pt=((100.0 + dx, 80.0 + dy), (265.5 + dx, 80.0 + dy)),
    )
    v_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_v_5044_t",
        value_mm=5044.0,
        orientation="vertical",
        endpoints_pt=((280.0 + dx, 100.0 + dy), (280.0 + dx, 604.4 + dy)),
    )

    result = evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=(h_dim, v_dim),
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.record is not None
    assert result.record.figured_area_m2 == pytest.approx(8.34782, abs=1e-5)


def test_input_no_mutation():
    """Verify evaluator does not mutate input lists or tuples."""
    selector = _make_selector()
    polygon, edges = _make_room_geometry(100.0, 100.0, 165.5, 504.4)
    h_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_h_1655",
        value_mm=1655.0,
        orientation="horizontal",
        endpoints_pt=((100.0, 80.0), (265.5, 80.0)),
    )
    v_dim = SourceBoundDimensionCandidate(
        dimension_id="dim_v_5044",
        value_mm=5044.0,
        orientation="vertical",
        endpoints_pt=((280.0, 100.0), (280.0, 604.4)),
    )

    dims = [h_dim, v_dim]
    orig_dims = copy.deepcopy(dims)
    orig_edges = copy.deepcopy(edges)
    orig_polygon = copy.deepcopy(polygon)

    evaluate_source_room_figured_witness_shadow(
        selector,
        room_face_polygon_pdf_pts=polygon,
        bounding_edges=edges,
        dimensions=dims,
    )

    assert dims == orig_dims
    assert edges == orig_edges
    assert polygon == orig_polygon
