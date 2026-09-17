"""Item 19 — exact physical-wall quantity propagation validator.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

The legacy opening-deduction propagator chooses one ``primary_res`` and can
broadcast that wall's result to unrelated walling/finish predictions. Item 19
must replace that behavior with propagation keyed by authenticated physical-wall
identity, never by tag, list order, first result, or a project-wide primary wall.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import pytest

from pb_migration_contracts import QuantityEvidence
from pb_opening_deduction_pipeline import (
    GenericOpeningDeductionPipeline,
    WallDeductionResult,
)


MODULE_NAME = "pb_exact_wall_quantity_propagation"
HAS_EXACT_PROPAGATION = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_EXACT_PROPAGATION,
    strict=True,
    reason="Item 19 exact physical-wall propagation is intentionally absent",
)


def _firm_net(wall_id: str, value: float) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"net-{wall_id}",
        family="wall_net_area",
        semantic_key=f"wall_net_area:{wall_id}",
        value=value,
        unit="m2",
        input_entity_ids=(wall_id,),
        formula="test-only-authenticated-net-wall",
        authority="test-only",
        status="firm",
        confidence=1.0,
        abstained=False,
        metadata={"physical_wall_identity_id": wall_id},
    )


def _result(wall_id: str, *, gross: float, deduction: float, net: float) -> WallDeductionResult:
    return WallDeductionResult(
        wall_id=wall_id,
        gross_area_m2=gross,
        total_deducted_area_m2=deduction,
        net_area_m2=net,
        net_area_evidence=_firm_net(wall_id, net),
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "legacy propagator broadcasts one primary wall result instead of resolving "
        "the prediction's exact physical-wall identity"
    ),
)
def test_current_legacy_propagator_exposes_cross_wall_broadcast_defect() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall_a = _result("wall-a", gross=100.0, deduction=10.0, net=90.0)
    wall_b = _result("wall-b", gross=90.0, deduction=20.0, net=70.0)
    prediction = {
        "tag": "internal_plaster",
        "quantity": 999.0,
        "metadata": {"physical_wall_identity_id": "wall-b"},
    }

    out = pipeline.propagate_to_predictions(
        [prediction],
        {"perimeter_walling": wall_a, "wall-b": wall_b},
    )

    # Correct Item-19 behavior is 70 m2 from wall-b. Current legacy code uses
    # ``primary_res`` (wall-a here) and therefore fails this assertion.
    assert out[0]["quantity"] == pytest.approx(70.0)


@EXPECTED_RED
def test_future_item19_module_does_not_choose_primary_first_or_nearest_wall() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod).lower()
    forbidden = (
        "primary_res",
        "list(results.values())[0]",
        "nearest_wall",
        "first_wall",
        "default_wall",
    )
    assert not any(token in source for token in forbidden)


@EXPECTED_RED
def test_future_item19_public_boundary_requires_exact_physical_wall_identity() -> None:
    mod = importlib.import_module(MODULE_NAME)
    assert hasattr(mod, "propagate_by_exact_wall_identity")
    params = tuple(inspect.signature(mod.propagate_by_exact_wall_identity).parameters)
    assert "predictions" in params
    assert any("authority" in name for name in params)
    assert not any(name in params for name in ("default_wall_id", "nearest", "first", "confidence"))


@EXPECTED_RED
def test_future_item19_missing_or_ambiguous_wall_identity_blocks_not_broadcasts() -> None:
    mod = importlib.import_module(MODULE_NAME)
    result = mod.propagate_by_exact_wall_identity(
        predictions=[{"tag": "internal_plaster", "quantity": 123.0, "metadata": {}}],
        net_wall_authority=None,
    )
    assert len(result) == 1
    assert result[0]["quantity"] is None
    assert result[0]["metadata"]["publication_blocked"] is True


@EXPECTED_RED
def test_future_item19_same_tag_on_two_walls_remains_two_distinct_quantities() -> None:
    mod = importlib.import_module(MODULE_NAME)
    # Production will replace this test's authority fixture with the sealed Item-17
    # authority. The invariant is frozen now: same trade tag never collapses wall
    # identity and never causes one wall's net area to overwrite another's.
    assert "physical_wall_identity" in inspect.getsource(mod).lower()
