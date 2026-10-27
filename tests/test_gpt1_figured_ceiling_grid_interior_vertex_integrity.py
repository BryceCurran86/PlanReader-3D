"""Geometry integrity of source-figured grid panel takeoff, no FIRM grant."""
from dataclasses import replace

import pytest

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_figured_ceiling_grid_shadow import (
    DocumentedCeilingGridSystem,
    measure_source_figured_ceiling_grid_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status

SHA = "a" * 64
SIMPLE = ((0, 0), (10000, 0), (10000, 5000), (0, 5000))


def _ceiling(ring=SIMPLE):
    return FiguredPolygonMetricShadow(
        Status.CANDIDATE, ("source_figured_axes",), 50.0, tuple(ring),
        ("original_axis_x", "original_axis_y"), (), SHA,
        "rev", "7", "source-ceiling-room",
    )


def _grid(origin=(0.0, 0.0)):
    return DocumentedCeilingGridSystem(
        "source-ceiling-surface", origin, 1000.0, 1000.0, 0.0,
        ("original-grid-module",), ("original-grid-origin",),
        SHA, "rev", "7",
    )


@pytest.mark.parametrize("bad_ring", (
    ((0, 0), (10000, 0), (10000, 0), (10000, 5000), (0, 5000)),
    ((0, 0), (10000, 0), (10000, 5000), (10000, 5000), (0, 5000)),
    ((0, 0), (10000, 0), (10000, 5000), (0, 5000), (10000, 0)),
))
def test_geos_valid_duplicate_interior_source_corner_cannot_issue_grid_panels(
    bad_ring,
):
    # Shapely accepts some repeated-source-interior corners as a valid
    # positive-area Polygon. That is not a physical ring edge-owner receipt.
    result = measure_source_figured_ceiling_grid_shadow(
        _ceiling(bad_ring), _grid(),
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ("original_ceiling_grid_physical_polygon_invalid",)
    assert result.full_panel_count_candidate is None
    assert result.cut_panel_count_candidate is None
    assert result.grid_tee_length_m_by_axis is None
    assert result.diagnostic_only


def test_exact_final_ring_closure_and_open_ring_preserve_grid_counts_and_tees():
    open_case = measure_source_figured_ceiling_grid_shadow(_ceiling(), _grid())
    closed_case = measure_source_figured_ceiling_grid_shadow(
        _ceiling(SIMPLE + (SIMPLE[0],)), _grid()
    )
    assert open_case == closed_case
    assert open_case.status is Status.CANDIDATE
    assert open_case.full_panel_count_candidate == 50
    assert open_case.cut_panel_count_candidate == 0
    assert open_case.coverage_area_m2 == 50.0
    assert open_case.grid_tee_length_m_by_axis == (45.0, 40.0)
    assert open_case.diagnostic_only


def test_grid_translation_preserves_source_pitched_panel_area_and_count():
    dx, dy = 2000, 3000
    translated = tuple((x+dx, y+dy) for x, y in SIMPLE)
    before = measure_source_figured_ceiling_grid_shadow(_ceiling(), _grid())
    after = measure_source_figured_ceiling_grid_shadow(
        _ceiling(translated), _grid((float(dx), float(dy))),
    )
    assert before.status is after.status is Status.CANDIDATE
    assert before.full_panel_count_candidate == after.full_panel_count_candidate
    assert before.cut_panel_count_candidate == after.cut_panel_count_candidate
    assert before.coverage_area_m2 == after.coverage_area_m2
    assert before.grid_tee_length_m_by_axis == after.grid_tee_length_m_by_axis


@pytest.mark.parametrize("invalid", (True, None, float("inf"), float("nan")))
def test_untyped_or_nonfinite_grid_vertex_can_never_claim_source_panel_count(invalid):
    ring = list(SIMPLE)
    ring[1] = (invalid, 0)
    result = measure_source_figured_ceiling_grid_shadow(
        _ceiling(tuple(ring)), _grid()
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ("original_ceiling_grid_physical_polygon_invalid",)
    assert result.total_panel_count_candidate is None
