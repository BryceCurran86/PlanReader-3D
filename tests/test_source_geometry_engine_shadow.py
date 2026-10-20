"""Unit tests for Producer-Owned Source Geometry Engine Shadow Authority.

Tests positive, negative, and aggregation scenarios under strict evaluator separation.
"""

from types import SimpleNamespace
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_geometry_engine_shadow import (
    CompiledSourcePlanGeometryReceipt,
    GEOMETRY_COMPILATION_EMPTY,
    SOURCE_GEOMETRY_ENGINE_CANDIDATE,
    SOURCE_GEOMETRY_ENGINE_RESOLVED,
    SourceGeometryEngine,
)

SAMPLE_SHA = "a" * 64


def test_positive_full_plan_geometry_compilation():
    engine = SourceGeometryEngine()

    # Add walls: 2 walls of length 4.5m and 5.5m = 10.0m total
    engine.add_wall_run(SimpleNamespace(length_m=4.5))
    engine.add_wall_run(SimpleNamespace(length_m=5.5))

    # Add openings: 2 doors of void area 1.8m² and 2.1m² = 3.9m² total
    engine.add_opening(SimpleNamespace(opening_area_sqm=1.8))
    engine.add_opening(SimpleNamespace(opening_area_sqm=2.1))

    # Add rooms: 2 rooms of internal floor area 25.0m² and 15.0m² = 40.0m² total
    engine.add_room(SimpleNamespace(area_sqm=25.0))
    engine.add_room(SimpleNamespace(area_sqm=15.0))

    # Add ceiling: 1 ceiling region of 38.0m²
    engine.add_ceiling(SimpleNamespace(area_sqm=38.0))

    # Add vertical void: 1 stair void of 4.0m²
    engine.add_vertical_void(SimpleNamespace(area_sqm=4.0))

    receipt = engine.compile_plan_geometry(
        document_id="doc_plan_01",
        revision_id="rev_01",
        source_sha256=SAMPLE_SHA,
        page_id="3",
    )

    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_GEOMETRY_ENGINE_RESOLVED in receipt.reason_codes
    assert receipt.total_wall_runs_count == 2
    assert pytest.approx(receipt.total_wall_length_m, rel=1e-3) == 10.0
    assert receipt.total_openings_count == 2
    assert pytest.approx(receipt.total_opening_void_area_sqm, rel=1e-3) == 3.9
    assert receipt.total_rooms_count == 2
    assert pytest.approx(receipt.total_internal_floor_area_sqm, rel=1e-3) == 40.0
    assert receipt.total_ceilings_count == 1
    assert pytest.approx(receipt.total_ceiling_area_sqm, rel=1e-3) == 38.0
    assert receipt.total_vertical_voids_count == 1
    assert pytest.approx(receipt.total_vertical_void_deduction_sqm, rel=1e-3) == 4.0
    # Net floor area = 40.0 - 4.0 = 36.0m²
    assert pytest.approx(receipt.net_floor_area_sqm, rel=1e-3) == 36.0

    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False


def test_negative_empty_engine_abstains():
    engine = SourceGeometryEngine()
    receipt = engine.compile_plan_geometry(
        document_id="doc_empty",
        revision_id="rev_01",
        source_sha256=SAMPLE_SHA,
        page_id="1",
    )

    assert receipt.status == EvidenceResolutionStatus.ABSTAINED
    assert GEOMETRY_COMPILATION_EMPTY in receipt.reason_codes
    assert receipt.total_wall_runs_count == 0
    assert receipt.total_openings_count == 0


def test_sealed_constructor_enforcement():
    with pytest.raises(TypeError, match="producer-owned"):
        CompiledSourcePlanGeometryReceipt(
            receipt_id="fake_id",
            document_id="doc",
            revision_id="rev",
            source_sha256=SAMPLE_SHA,
            page_id="1",
            total_wall_runs_count=0,
            total_wall_length_m=0.0,
            total_openings_count=0,
            total_opening_void_area_sqm=0.0,
            total_rooms_count=0,
            total_internal_floor_area_sqm=0.0,
            total_ceilings_count=0,
            total_ceiling_area_sqm=0.0,
            total_vertical_voids_count=0,
            total_vertical_void_deduction_sqm=0.0,
            net_floor_area_sqm=0.0,
            _seal=None,
        )
