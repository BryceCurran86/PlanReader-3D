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

Second correction (same file, later pass): an incomplete deduction is an
UNKNOWN net area, not an evidenced zero one (see WallDeductionResult.
net_area_evidence). quantity must become None, not a silently-retained
guess -- the guess moves to metadata["provisional_net_area_m2"] for
diagnostics only. See test_opening_deduction_authenticated_binding.py for
coverage of bind_openings_to_walls itself (no heuristic binding).
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
    resolved_window = OpeningInstance(opening_id="W1", width_m=1.2, height_m=1.5, quantity=2.0)
    unresolved_window = OpeningInstance(opening_id="W2", width_m=None, height_m=None, quantity=1.0)

    pipeline = GenericOpeningDeductionPipeline()
    # W1's binding is independently authenticated (simulating a reconciled
    # host-binding authority); W2 has no such proof and no dimensions either.
    results = pipeline.deduct_openings_for_all_walls(
        [wall],
        [resolved_window, unresolved_window],
        authenticated_host_bindings={"W1": "perimeter_walling"},
    )
    assert results["perimeter_walling"].unbound_openings  # W2: no authenticated binding at all
    assert results["perimeter_walling"].net_area_evidence.abstained is True
    assert results["perimeter_walling"].net_area_evidence.value is None

    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
        _Prediction(tag="internal_paint", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    by_tag = {p.tag: p for p in out}

    for tag in ("perimeter_walling", "internal_plaster", "internal_paint"):
        assert by_tag[tag].quantity is None, (
            f"{tag} must publish quantity=None, not a silently-retained "
            "undeducted number, when the shared opening universe is incomplete"
        )
        assert by_tag[tag].metadata.get("publication_blocked") is True
        assert by_tag[tag].metadata.get("net_area_m2") is None
        # W1 (1.2 x 1.5 x qty2 = 3.6 m2) is authenticated and resolved, so
        # the provisional estimate reflects its real deduction (100 - 3.6);
        # W2 stays fully excluded since it's unbound -- that gap is exactly
        # why this must stay provisional/blocked rather than final.
        assert by_tag[tag].metadata.get("provisional_net_area_m2") == 96.4, (
            "the best-known (unreliable) estimate is retained for diagnostics "
            "under a clearly provisional-only key, never under quantity/net_area_m2"
        )


def test_unbound_opening_with_no_authenticated_binding_blocks_publication() -> None:
    wall = _wall(gross_area_m2=50.0)
    door = OpeningInstance(opening_id="D1", width_m=0.9, height_m=2.1, quantity=1.0)
    pipeline = GenericOpeningDeductionPipeline()
    # No authenticated_host_bindings supplied at all -- current live reality.
    results = pipeline.deduct_openings_for_all_walls([wall], [door])
    assert door.bound_wall_id is None
    assert results["perimeter_walling"].unbound_openings
    predictions = [_Prediction(tag="perimeter_walling", trade_type="walls", quantity=50.0)]
    out = pipeline.propagate_to_predictions(predictions, results)
    assert out[0].quantity is None
    assert out[0].metadata.get("publication_blocked") is True


def test_complete_deduction_publishes_normally_without_blocking() -> None:
    """The happy path must be unaffected: an authenticated binding plus
    resolved dimensions -> no publication_blocked marker, real quantity
    published, no unknown/None state."""
    wall = _wall(gross_area_m2=100.0)
    window = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=2.0)
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls(
        [wall], [window], authenticated_host_bindings={"W1": "perimeter_walling"}
    )
    assert results["perimeter_walling"].net_area_evidence.abstained is False
    predictions = [
        _Prediction(tag="perimeter_walling", trade_type="walls", quantity=100.0),
        _Prediction(tag="internal_plaster", trade_type="wall_finish", quantity=100.0),
    ]
    out = pipeline.propagate_to_predictions(predictions, results)
    by_tag = {p.tag: p for p in out}

    expected_net = 100.0 - (1.0 * 1.5 * 2.0)
    for tag in ("perimeter_walling", "internal_plaster"):
        assert "publication_blocked" not in by_tag[tag].metadata
        assert "provisional_net_area_m2" not in by_tag[tag].metadata
        assert by_tag[tag].quantity == expected_net
        assert by_tag[tag].metadata["net_area_m2"] == expected_net


def test_independent_gross_wall_finish_still_gated_by_shared_openings() -> None:
    """A wall-finish prediction with its own independently-derived gross area
    must still be blocked when the SHARED openings are incomplete -- the gate
    is about the openings, not about which gross value is being netted."""
    wall = _wall(gross_area_m2=100.0)
    unresolved_window = OpeningInstance(opening_id="W1", width_m=None, height_m=None, quantity=1.0)
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
