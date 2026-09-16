"""tests/benchmarks/test_mutation_opening_deductions.py — Mutation Tests for F.9 Opening Deductions.

Arithmetic mutations remain deterministic.  Authority is intentionally
separate: caller-populated wall ids can drive provisional arithmetic but can
never publish net-wall quantity authority until producer-owned host binding is
integrated.
"""
from __future__ import annotations

from pathlib import Path
import fitz
import pytest

from pb_opening_deduction_pipeline import (
    GenericOpeningDeductionPipeline,
    OpeningDeductionStatus,
    OpeningInstance,
    WallDeductionResult,
    WallInstance,
)
from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    GenericPlanReaderExtractor,
)


def test_mutation_1_add_window_decreases_net_wall_area_exactly() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="wall_01", length_m=10.0, height_m=3.0, gross_area_m2=30.0)
    window = OpeningInstance(
        opening_id="W1",
        trade_type="windows",
        width_m=1.2,
        height_m=1.5,
        quantity=1.0,
        bound_wall_id="wall_01",
    )
    res = pipeline.calculate_wall_deductions(wall, [window])
    assert res.gross_area_m2 == 30.0
    assert res.total_deducted_area_m2 == 1.8
    assert res.net_area_m2 == 28.2
    assert len(res.applied_openings) == 1
    assert res.applied_openings[0]["opening_id"] == "W1"
    assert res.applied_openings[0]["status"] == OpeningDeductionStatus.APPLIED.value
    assert res.net_area_evidence is not None
    assert res.net_area_evidence.abstained is True
    assert res.net_area_evidence.value is None


def test_mutation_2_remove_window_deduction_disappears() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="wall_01", length_m=10.0, height_m=3.0, gross_area_m2=30.0)
    res = pipeline.calculate_wall_deductions(wall, [])
    assert res.gross_area_m2 == 30.0
    assert res.total_deducted_area_m2 == 0.0
    assert res.net_area_m2 == 30.0
    assert len(res.applied_openings) == 0
    assert res.net_area_evidence is not None
    assert res.net_area_evidence.abstained is True


def test_mutation_3_double_quantity_doubles_deduction() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="wall_01", length_m=10.0, height_m=3.0, gross_area_m2=30.0)
    window_2x = OpeningInstance(
        opening_id="W1",
        trade_type="windows",
        width_m=1.2,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="wall_01",
    )
    res = pipeline.calculate_wall_deductions(wall, [window_2x])
    assert res.gross_area_m2 == 30.0
    assert res.total_deducted_area_m2 == 3.6
    assert res.net_area_m2 == 26.4
    assert len(res.applied_openings) == 1
    assert res.applied_openings[0]["quantity"] == 2.0


def test_mutation_4_move_opening_to_another_wall_isolates_change() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall_a = WallInstance(wall_id="wall_north", gross_area_m2=30.0)
    wall_b = WallInstance(wall_id="wall_south", gross_area_m2=50.0)
    window_south = OpeningInstance(
        opening_id="W1",
        trade_type="windows",
        width_m=1.2,
        height_m=1.5,
        quantity=1.0,
        bound_wall_id="wall_south",
    )
    res_a = pipeline.calculate_wall_deductions(wall_a, [window_south])
    res_b = pipeline.calculate_wall_deductions(wall_b, [window_south])
    assert res_a.gross_area_m2 == 30.0
    assert res_a.total_deducted_area_m2 == 0.0
    assert res_a.net_area_m2 == 30.0
    assert len(res_a.applied_openings) == 0
    assert res_b.gross_area_m2 == 50.0
    assert res_b.total_deducted_area_m2 == 1.8
    assert res_b.net_area_m2 == 48.2
    assert len(res_b.applied_openings) == 1
    assert res_b.applied_openings[0]["bound_wall_id"] == "wall_south"


def test_mutation_5_missing_height_no_deduction_explicit_unresolved_state() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="wall_01", gross_area_m2=30.0)
    window_unresolved = OpeningInstance(
        opening_id="W_UNKNOWN",
        trade_type="windows",
        width_m=1.2,
        height_m=None,
        quantity=1.0,
        bound_wall_id="wall_01",
    )
    res = pipeline.calculate_wall_deductions(wall, [window_unresolved])
    assert res.gross_area_m2 == 30.0
    assert res.total_deducted_area_m2 == 0.0
    assert res.net_area_m2 == 30.0
    assert len(res.applied_openings) == 0
    assert len(res.unresolved_openings) == 1
    unres = res.unresolved_openings[0]
    assert unres["opening_id"] == "W_UNKNOWN"
    assert unres["status"] == OpeningDeductionStatus.UNRESOLVED_MISSING_DIMENSIONS.value
    assert "Missing figured width or height" in unres["notes"]


def test_propagation_to_predictions_blocks_caller_bound_arithmetic() -> None:
    """Arithmetic can be computed, but the shared quantity remains unpublished."""
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    window = OpeningInstance(
        opening_id="W1",
        width_m=2.0,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="perimeter_walling",
    )
    results = {"perimeter_walling": pipeline.calculate_wall_deductions(wall, [window])}
    assert results["perimeter_walling"].net_area_m2 == 94.0
    assert results["perimeter_walling"].net_area_evidence is not None
    assert results["perimeter_walling"].net_area_evidence.abstained is True

    preds = [
        ExtractedPrediction(
            tag="perimeter_walling",
            trade_type="walls",
            description="Perimeter walling",
            quantity=100.0,
            unit="SM",
            confidence=0.88,
            source_page=1,
        ),
        ExtractedPrediction(
            tag="internal_plaster",
            trade_type="finishes",
            description="Internal plaster",
            quantity=100.0,
            unit="SM",
            confidence=0.85,
            source_page=1,
        ),
        ExtractedPrediction(
            tag="internal_paint",
            trade_type="finishes",
            description="Internal paint",
            quantity=100.0,
            unit="SM",
            confidence=0.85,
            source_page=1,
        ),
        ExtractedPrediction(
            tag="floor_screed",
            trade_type="finishes",
            description="Floor screed",
            quantity=80.0,
            unit="SM",
            confidence=0.92,
            source_page=1,
        ),
    ]
    updated = pipeline.propagate_to_predictions(preds, results)
    pred_map = {prediction.tag: prediction for prediction in updated}
    for tag in ("perimeter_walling", "internal_plaster", "internal_paint"):
        assert pred_map[tag].quantity is None
        assert pred_map[tag].metadata["net_area_m2"] is None
        assert pred_map[tag].metadata["provisional_net_area_m2"] == 94.0
        assert pred_map[tag].metadata["publication_blocked"] is True
    assert pred_map["floor_screed"].quantity == 80.0


def test_propagation_blocks_independent_gross_area_without_host_authority() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    window = OpeningInstance(
        opening_id="W1",
        width_m=2.0,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="perimeter_walling",
    )
    results = {"perimeter_walling": pipeline.calculate_wall_deductions(wall, [window])}
    preds = [
        ExtractedPrediction(
            tag="perimeter_walling",
            trade_type="walls",
            description="Perimeter walling",
            quantity=100.0,
            unit="SM",
            confidence=0.88,
            source_page=1,
        ),
        ExtractedPrediction(
            tag="internal_plaster",
            trade_type="finishes",
            description="Internal plaster (independent internal-face area)",
            quantity=85.0,
            unit="SM",
            confidence=0.8,
            source_page=1,
            metadata={"independent_gross_area_m2": 85.0},
        ),
        ExtractedPrediction(
            tag="internal_paint",
            trade_type="finishes",
            description="Internal paint (plain proxy copy, no independent area)",
            quantity=100.0,
            unit="SM",
            confidence=0.5,
            source_page=1,
        ),
    ]
    updated = pipeline.propagate_to_predictions(preds, results)
    pred_map = {prediction.tag: prediction for prediction in updated}
    assert pred_map["internal_plaster"].quantity is None
    assert pred_map["internal_plaster"].metadata["net_area_m2"] is None
    assert pred_map["internal_plaster"].metadata["provisional_net_area_m2"] == 79.0
    assert pred_map["internal_paint"].quantity is None
    assert pred_map["internal_paint"].metadata["provisional_net_area_m2"] == 94.0


def test_wall_deduction_result_round_trip_shape() -> None:
    """Retain the public result shape used by older callers."""
    result = WallDeductionResult(
        wall_id="wall",
        gross_area_m2=10.0,
        total_deducted_area_m2=0.0,
        net_area_m2=10.0,
    )
    payload = result.to_dict()
    assert payload["wall_id"] == "wall"
    assert payload["net_area_evidence"] is None


def test_fixture_imports_remain_available() -> None:
    """Keep historical fixture dependencies imported for the larger mutation module."""
    assert Path is not None
    assert fitz is not None
    assert pytest is not None
    assert GenericPlanReaderExtractor is not None
