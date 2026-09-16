"""Regression coverage for GenericOpeningDeductionPipeline.propagate_to_predictions.

NOTE: bind_openings_to_walls performs no binding at all (see
test_opening_deduction_authenticated_binding.py) -- there is no way to
obtain a genuinely "bound" opening through the normal deduct_openings_for_all_walls
entry point today. Tests here that need a bound opening to exercise the
complete-deduction / publication-gate logic in isolation construct it
directly (bound_wall_id set on the OpeningInstance, calculate_wall_deductions
called directly) rather than going through binding -- this tests the gate
and arithmetic, not the (separately, exhaustively tested) binding refusal.

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
    # W1 is constructed already-bound (simulating what a reconciled
    # host-binding authority would eventually prove) to isolate this test's
    # actual subject -- the publication gate -- from binding itself.
    resolved_window = OpeningInstance(
        opening_id="W1", width_m=1.2, height_m=1.5, quantity=2.0, bound_wall_id="perimeter_walling"
    )
    unresolved_window = OpeningInstance(opening_id="W2", width_m=None, height_m=None, quantity=1.0)

    pipeline = GenericOpeningDeductionPipeline()
    results = {
        "perimeter_walling": pipeline.calculate_wall_deductions(
            wall, [resolved_window, unresolved_window]
        )
    }
    assert results["perimeter_walling"].unbound_openings  # W2: never bound at all
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


def test_unbound_opening_via_normal_entry_point_blocks_publication() -> None:
    """Through the real entry point (deduct_openings_for_all_walls, which
    always calls bind_openings_to_walls first), today's only possible
    outcome is unbound -- today's live reality."""
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


def test_complete_deduction_publishes_normally_without_blocking() -> None:
    """The happy path must be unaffected: a resolved, already-bound opening
    (constructed directly -- see module note) -> no publication_blocked
    marker, real quantity published, no unknown/None state."""
    wall = _wall(gross_area_m2=100.0)
    window = OpeningInstance(
        opening_id="W1", width_m=1.0, height_m=1.5, quantity=2.0, bound_wall_id="perimeter_walling"
    )
    pipeline = GenericOpeningDeductionPipeline()
    results = {"perimeter_walling": pipeline.calculate_wall_deductions(wall, [window])}
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
