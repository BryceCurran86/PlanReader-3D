"""Regression coverage for GenericOpeningDeductionPipeline.propagate_to_predictions.

Bug: an unresolved or unbound opening contributes zero to
total_deducted_area_m2 (by design -- see calculate_wall_deductions), but
propagate_to_predictions previously published net_area_m2 as final regardless,
silently understating deductions (overstating net area) across every walling
and wall-finish prediction sharing that wall. Found via cross-project
benchmark analysis: the KSTVET public-tender benchmark reproduced this
exactly -- internal_plaster and internal_paint reported the identical
(undeducted) 84.336 SM, and perimeter_walling/external_key_pointing reported
the identical 87.7 SM, because two windows' missing dimensions were silently
excluded from the deduction rather than blocking publication.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
    """One opening with missing dimensions must block walling AND every
    wall-finish prediction sharing that wall -- not just the wall itself,
    and not silently propagate an undeducted number as final."""
    wall = _wall(gross_area_m2=100.0)
    resolved_window = OpeningInstance(
        opening_id="W1", width_m=1.2, height_m=1.5, quantity=2.0, bound_wall_id="perimeter_walling"
    )
    unresolved_window = OpeningInstance(
        opening_id="W2", width_m=None, height_m=None, quantity=1.0, bound_wall_id="perimeter_walling"
    )

    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [resolved_window, unresolved_window])
    assert results["perimeter_walling"].unresolved_openings  # sanity: fixture exercises the gap

    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
        _Prediction(tag="internal_paint", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    by_tag = {p.tag: p for p in out}

    for tag in ("perimeter_walling", "internal_plaster", "internal_paint"):
        assert by_tag[tag].metadata.get("publication_blocked") is True, (
            f"{tag} must be blocked from publication when a bound opening's "
            "dimensions are unresolved"
        )
        assert by_tag[tag].metadata.get("unresolved_openings"), (
            f"{tag} metadata must retain the unresolved-opening record for diagnostics"
        )


def test_unbound_opening_also_blocks_publication() -> None:
    # bind_openings_to_walls' single-wall shortcut auto-binds everything to
    # the one wall present, so a genuinely unbound opening requires 2+ walls
    # and no bounding-box overlap for the fallback (provisional-unbound) path
    # to actually fire.
    wall = _wall(gross_area_m2=50.0)
    other_wall = WallInstance(wall_id="internal_walling", gross_area_m2=30.0)
    unbound_door = OpeningInstance(
        opening_id="D1", width_m=0.9, height_m=2.1, quantity=1.0, bound_wall_id=None
    )
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall, other_wall], [unbound_door])
    assert unbound_door.bound_wall_id is None  # sanity: fixture exercises the gap
    predictions = [_Prediction(tag="perimeter_walling", trade_type="walls", quantity=50.0)]
    out = pipeline.propagate_to_predictions(predictions, results)
    assert out[0].metadata.get("publication_blocked") is True


def test_complete_deduction_publishes_normally_without_blocking() -> None:
    """The happy path must be unaffected: no unresolved/unbound openings ->
    no publication_blocked marker, and the correct net area is published."""
    wall = _wall(gross_area_m2=100.0)
    window = OpeningInstance(
        opening_id="W1", width_m=1.0, height_m=1.5, quantity=2.0, bound_wall_id="perimeter_walling"
    )
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [window])
    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    by_tag = {p.tag: p for p in out}

    expected_net = 100.0 - (1.0 * 1.5 * 2.0)
    for tag in ("perimeter_walling", "internal_plaster"):
        assert "publication_blocked" not in by_tag[tag].metadata
        assert by_tag[tag].quantity == expected_net
        assert by_tag[tag].metadata["net_area_m2"] == expected_net


def test_independent_gross_wall_finish_still_gated_by_shared_openings() -> None:
    """A wall-finish prediction with its own independently-derived gross area
    must still be blocked when the SHARED openings are incomplete -- the gate
    is about the openings, not about which gross value is being netted."""
    wall = _wall(gross_area_m2=100.0)
    unresolved_window = OpeningInstance(
        opening_id="W1", width_m=None, height_m=None, quantity=1.0, bound_wall_id="perimeter_walling"
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
    assert out[0].metadata.get("publication_blocked") is True
