"""Sealed production must agree with produced V2 projection exactly."""
from __future__ import annotations

from types import SimpleNamespace

from scripts.report_full_plan_v2_readiness import produced_sealed_parity_blockers


def _sealed(*, abstained: bool = False):
    return SimpleNamespace(
        quantity_id="source-q-1",
        object_identity_refs=("canonical-opening-1",),
        unit="m2",
        value=None if abstained else 1.26,
        abstained=abstained,
        lineage_ok=True,
    )


def _produced(*, abstained: bool = False):
    return {
        "quantity_id": "source-q-1",
        "object_refs": ["canonical-opening-1"],
        "trade_category": "windows",
        "unit": "m2",
        "value": None if abstained else 1.26,
        "abstained": abstained,
        "lineage_ok": True,
    }


def test_exact_source_quantity_projection_accepted() -> None:
    assert produced_sealed_parity_blockers([_produced()], (_sealed(),)) == []


def test_missing_firm_quantity_detected() -> None:
    assert "firm_sealed_quantity_not_projected:source-q-1" in (
        produced_sealed_parity_blockers([], (_sealed(),))
    )


def test_abstained_quantity_may_be_omitted_without_fabricating_zero() -> None:
    assert produced_sealed_parity_blockers([], (_sealed(abstained=True),)) == []
    output = _produced(abstained=True)
    output["value"] = 0.0
    assert "abstained_projection_has_value:source-q-1" in (
        produced_sealed_parity_blockers([output], (_sealed(abstained=True),))
    )


def test_spoofed_object_id_or_unsupported_extra_fails_closed() -> None:
    output = _produced()
    output["object_refs"] = ["benchmark:fake:matching-object"]
    assert "projection_object_identity_mismatch:source-q-1" in (
        produced_sealed_parity_blockers([output], (_sealed(),))
    )
    output = _produced()
    output["quantity_id"] = "extra-q"
    blockers = produced_sealed_parity_blockers([output], (_sealed(),))
    assert "unsealed_produced_quantity:extra-q" in blockers


def test_conflicts_cannot_hide_under_duplicate_or_changed_units() -> None:
    output = _produced()
    output["unit"] = "nr"
    output["value"] = 0.0
    output["lineage_ok"] = False
    blockers = produced_sealed_parity_blockers([output, output], (_sealed(),))
    assert "duplicate_produced_quantity_id:source-q-1" in blockers
    assert "projection_unit_mismatch:source-q-1" in blockers
    assert "projection_value_mismatch:source-q-1" in blockers
    assert "projection_lineage_mismatch:source-q-1" in blockers


def test_missing_trade_or_bad_numeric_value_rejected() -> None:
    output = _produced()
    output["trade_category"] = ""
    output["value"] = float("nan")
    blockers = produced_sealed_parity_blockers([output], (_sealed(),))
    assert "projection_trade_category_missing:source-q-1" in blockers
    assert "projection_value_mismatch:source-q-1" in blockers


def test_independent_firm_and_abstained_claims_stay_independent() -> None:
    second = SimpleNamespace(
        quantity_id="source-q-2",
        object_identity_refs=("canonical-opening-2",),
        unit="m2",
        value=None,
        abstained=True,
        lineage_ok=True,
    )
    assert produced_sealed_parity_blockers([_produced()], (_sealed(), second)) == []
