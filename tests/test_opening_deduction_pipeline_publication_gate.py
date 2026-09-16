"""Regression coverage for GenericOpeningDeductionPipeline publication authority.

The binder intentionally establishes no host binding today.  Directly
constructing an OpeningInstance with ``bound_wall_id`` may still be useful for
pure arithmetic mutation tests, but it must never mint authoritative net-wall
quantity evidence.  The public calculation therefore keeps diagnostic
arithmetic while publishing ABSTAINED evidence until producer-owned host
binding v3 is wired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from pb_opening_deduction_pipeline import (
    GenericOpeningDeductionPipeline,
    OpeningInstance,
    WallInstance,
)


@dataclass
class _Prediction:
    """Minimal duck-typed stand-in for ExtractedPrediction (attribute path)."""

    tag: str
    trade_type: str
    quantity: float
    metadata: Dict[str, Any] = field(default_factory=dict)


def _wall(gross_area_m2: float = 100.0) -> WallInstance:
    return WallInstance(wall_id="perimeter_walling", gross_area_m2=gross_area_m2)


def test_incomplete_deduction_blocks_publication_across_all_dependent_predictions() -> None:
    wall = _wall(gross_area_m2=100.0)
    resolved_window = OpeningInstance(
        opening_id="W1",
        width_m=1.2,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="perimeter_walling",
    )
    unresolved_window = OpeningInstance(
        opening_id="W2", width_m=None, height_m=None, quantity=1.0
    )

    pipeline = GenericOpeningDeductionPipeline()
    results = {
        "perimeter_walling": pipeline.calculate_wall_deductions(
            wall, [resolved_window, unresolved_window]
        )
    }
    result = results["perimeter_walling"]
    assert result.unbound_openings
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.value is None

    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
        _Prediction(tag="internal_paint", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    by_tag = {prediction.tag: prediction for prediction in out}

    for tag in ("perimeter_walling", "internal_plaster", "internal_paint"):
        assert by_tag[tag].quantity is None
        assert by_tag[tag].metadata.get("publication_blocked") is True
        assert by_tag[tag].metadata.get("net_area_m2") is None
        assert by_tag[tag].metadata.get("provisional_net_area_m2") == 96.4


def test_unbound_opening_via_normal_entry_point_blocks_publication() -> None:
    wall = _wall(gross_area_m2=50.0)
    door = OpeningInstance(opening_id="D1", width_m=0.9, height_m=2.1, quantity=1.0)
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [door])
    assert door.bound_wall_id is None
    assert results["perimeter_walling"].unbound_openings
    predictions = [_Prediction(tag="perimeter_walling", trade_type="walls", quantity=50.0)]
    out = pipeline.propagate_to_predictions(predictions, results)
    assert out[0].quantity is None
    assert out[0].metadata.get("publication_blocked") is True


def test_caller_bound_complete_arithmetic_still_cannot_publish_authority() -> None:
    """A caller-populated host id is arithmetic input, never authority."""
    wall = _wall(gross_area_m2=100.0)
    window = OpeningInstance(
        opening_id="W1",
        width_m=1.0,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="perimeter_walling",
    )
    pipeline = GenericOpeningDeductionPipeline()
    result = pipeline.calculate_wall_deductions(wall, [window])

    # Diagnostic arithmetic remains deterministic: 100 - (1 * 1.5 * 2) = 97.
    assert result.net_area_m2 == 97.0
    assert result.total_deducted_area_m2 == 3.0
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.value is None
    assert "producer_owned_host_binding_authority_unavailable" in (
        result.net_area_evidence.blocking_reasons
    )

    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(
        predictions, {"perimeter_walling": result}
    )
    for prediction in out:
        assert prediction.quantity is None
        assert prediction.metadata["publication_blocked"] is True
        assert prediction.metadata["net_area_m2"] is None
        assert prediction.metadata["provisional_net_area_m2"] == 97.0


def test_pure_arithmetic_helper_has_no_quantity_authority_contract() -> None:
    """The lower-level helper preserves arithmetic without evidence minting."""
    wall = _wall(gross_area_m2=100.0)
    opening = OpeningInstance(
        opening_id="synthetic",
        width_m=1.0,
        height_m=3.0,
        quantity=1.0,
        bound_wall_id="perimeter_walling",
    )
    result = GenericOpeningDeductionPipeline().calculate_provisional_wall_deductions(
        wall, [opening]
    )
    assert result.total_deducted_area_m2 == 3.0
    assert result.net_area_m2 == 97.0
    assert not hasattr(result, "net_area_evidence")


def test_empty_local_opening_list_is_not_evidenced_zero_deduction() -> None:
    """Unknown universe != true zero; completeness is still missing today."""
    result = GenericOpeningDeductionPipeline().calculate_wall_deductions(
        _wall(gross_area_m2=100.0), []
    )
    assert result.total_deducted_area_m2 == 0.0
    assert result.net_area_m2 == 100.0
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.value is None


def test_independent_gross_wall_finish_still_gated_by_shared_openings() -> None:
    wall = _wall(gross_area_m2=100.0)
    unresolved_window = OpeningInstance(
        opening_id="W1", width_m=None, height_m=None, quantity=1.0
    )
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [unresolved_window])
    predictions = [
        _Prediction(
            tag="internal_plaster",
            trade_type="wall_finish",
            quantity=90.0,
            metadata={"independent_gross_area_m2": 90.0},
        ),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    assert out[0].quantity is None
    assert out[0].metadata.get("publication_blocked") is True
    assert out[0].metadata.get("provisional_net_area_m2") == 90.0
