"""Exact-cent live costing parity, tax, missing rates and source ownership."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import pytest

from pb_builder_edition_architecture import (
    CanonicalCompanyRate, price_canonical_quantities,
)
from pb_cross_trade_geometry_reuse import (
    DerivedTradeQuantity, bind_derived_quantity_rate_key,
)
from pb_vr_editor_command_preview import preview_editor_command
from pb_vr_live_costing import (
    LiveCostBook, LiveRateBinding, price_live_correction_preview,
)
from test_vr_editor_command_preview import _fixture


def _rate(**overrides):
    props = dict(
        rate_key="paint.wall.gross", unit="m²", currency="AUD",
        material_cost_per_unit=12.0, labour_cost_per_unit=8.0,
        subcontract_cost_per_unit=0.0, plant_cost_per_unit=1.0,
        material_waste_pct=5.0, overhead_pct=10.0,
        gross_margin_pct=20.0, evidence_ids=("company-rate-v1",),
    )
    props.update(overrides)
    return CanonicalCompanyRate(**props)


def _book(ws, **changes):
    props = dict(
        tenant_id="tenant1", workspace_id=ws.scope.workspace_id,
        source_sha256=ws.scope.source_sha256, snapshot_id=ws.scope.snapshot_id,
        revision="client-rates-v1", currency="AUD",
        tax_pct="10", contingency_pct="0",
        bindings=(LiveRateBinding(
            canonical_object_id="canonical-wall-1",
            target="wall_gross_area", rate=_rate(),
            binding_evidence_ids=("company-binding-w1-gross",),
        ),),
        evidence_ids=("tenant-company-ratebook-v1",),
    )
    props.update(changes)
    return LiveCostBook(**props)


def _preview():
    user, ws, ledger, cmd = _fixture()
    before = ledger.get_object("wall-1").to_dict()
    quantities = preview_editor_command(
        cmd, principal=user, workspace=ws, ledger=ledger,
    )
    assert quantities["accepted"] is True
    assert ledger.get_object("wall-1").to_dict() == before
    return user, ws, ledger, cmd, quantities


def test_live_exact_cent_formula_line_and_gst_not_price_approval():
    principal, ws, ledger, cmd, quantities = _preview()
    result = price_live_correction_preview(
        cmd, quantities, principal=principal, workspace=ws, book=_book(ws),
    )
    assert result["accepted"] is True
    assert result["validationState"] == "cost_preview_only"
    assert result["quoteReady"] is False
    assert result["requiresApproval"] is True
    assert result["persisted"] is False
    assert result["commercialPublicationAllowed"] is False
    assert result["currency"] == "AUD"
    assert result["rateBookRevision"] == "client-rates-v1"
    assert result["pricedComplete"] is False  # length/net require separate bindings
    gross = next(x for x in result["lines"] if x["target"] == "wall_gross_area")
    assert gross["previousQuantity"] == "9.6"
    assert gross["proposedQuantity"] == "12.0"
    assert gross["rateEvidenceIds"] == ["company-rate-v1"]
    assert gross["bindingEvidenceIds"] == ["company-binding-w1-gross"]
    assert gross["before"]["direct"] == "207.36"
    assert gross["before"]["overhead"] == "20.74"
    assert gross["before"]["sellExTax"] == "285.13"
    assert gross["before"]["tax"] == "28.51"
    assert gross["before"]["sellIncTax"] == "313.64"
    assert gross["after"]["direct"] == "259.20"
    assert gross["after"]["overhead"] == "25.92"
    assert gross["after"]["sellExTax"] == "356.40"
    assert gross["after"]["tax"] == "35.64"
    assert gross["after"]["sellIncTax"] == "392.04"
    assert gross["deltaIncTax"] == "78.40"
    assert result["totals"]["delta"]["sellIncTax"] == "78.40"
    assert ledger.events == ()


def test_margin_formula_is_identical_to_existing_canonical_costing_when_no_extras():
    principal, ws, _, cmd, quantities = _preview()
    result = price_live_correction_preview(
        cmd, quantities, principal=principal, workspace=ws,
        book=_book(ws, tax_pct="0", contingency_pct="0"),
    )
    row = next(x for x in result["lines"] if x["target"] == "wall_gross_area")
    source = DerivedTradeQuantity(
        trade_scope="painting", section="Internal", element="Wall painting",
        location="wall-1", substrate="Acrylic",
        quantity=12.0, unit="m²", host_object_id="wall-1",
        host_object_type="WALL", derivation_formula="Original wall gross",
        host_evidence_ids=("wall-source",), spec_evidence_ids=("paint-spec",),
    )
    source = bind_derived_quantity_rate_key(
        source, rate_key="paint.wall.gross", evidence_ids=("rate-binding",),
    )
    canonical = price_canonical_quantities((source,), (_rate(),))
    assert Decimal(row["after"]["sellExTax"]) == Decimal(str(canonical.sell_price_total))
    assert Decimal(row["after"]["direct"]) == Decimal(str(canonical.direct_cost_total))
    assert Decimal(row["after"]["margin"]) == Decimal(str(canonical.margin_total))


def test_contingency_and_tax_are_explicit_and_never_implicit():
    user, ws, _, cmd, q = _preview()
    base = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws, book=_book(ws, tax_pct="0"),
    )["lines"][0]["after"]
    with_extras = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws,
        book=_book(ws, tax_pct="10", contingency_pct="5"),
    )["lines"][0]["after"]
    assert base["tax"] == "0.00"
    assert base["contingency"] == "0.00"
    assert Decimal(with_extras["contingency"]) > 0
    assert Decimal(with_extras["tax"]) > 0
    assert Decimal(with_extras["sellIncTax"]) > Decimal(base["sellExTax"])


def test_no_rate_is_unpriced_not_free_and_totals_stay_partial():
    user, ws, _, cmd, q = _preview()
    result = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws,
        book=_book(ws, bindings=()),
    )
    assert result["lines"] == []
    assert result["unpriced"]
    assert all(x["reason"] == "no_source_bound_company_rate" for x in result["unpriced"])
    assert result["totals"]["after"]["sellIncTax"] == "0.00"
    assert result["pricedComplete"] is False
    assert result["partialTotalsOnly"] is True
    assert result["quoteReady"] is False


def test_missing_or_bad_quantity_stays_unpriced_even_with_rate():
    user, ws, _, cmd, q = _preview()
    candidate = dict(q)
    candidate["quantityImpacts"] = [
        {"target": "wall_gross_area", "status": "manual_review_required",
         "oldValue": None, "proposedValue": None, "unit": "m²"},
    ]
    result = price_live_correction_preview(
        cmd, candidate, principal=user, workspace=ws, book=_book(ws),
    )
    assert not result["lines"]
    assert result["unpriced"][0]["reason"] == "manual_review_or_missing_quantity"
    candidate["quantityImpacts"] = [
        {"target": "wall_gross_area", "status": "recalculated",
         "oldValue": float("nan"), "proposedValue": 3.0, "unit": "m²"},
    ]
    result = price_live_correction_preview(
        cmd, candidate, principal=user, workspace=ws, book=_book(ws),
    )
    assert not result["lines"]
    assert result["unpriced"][0]["reason"] == "nonfinite_or_unbounded_quantity"


def test_source_and_tenant_and_revision_must_be_current():
    principal, ws, _, cmd, quantities = _preview()
    for mismatch in (
        replace(_book(ws), tenant_id="someone-else"),
        replace(_book(ws), snapshot_id="old"),
        replace(_book(ws), source_sha256="b" * 64),
    ):
        with pytest.raises(ValueError, match="scope_mismatch"):
            price_live_correction_preview(
                cmd, quantities, principal=principal, workspace=ws, book=mismatch,
            )
    with pytest.raises(ValueError, match="stale"):
        price_live_correction_preview(
            {**cmd, "targetCanonicalId": "forged"}, quantities,
            principal=principal, workspace=ws, book=_book(ws),
        )
    with pytest.raises(ValueError, match="stale"):
        price_live_correction_preview(
            cmd, {**quantities, "persisted": True},
            principal=principal, workspace=ws, book=_book(ws),
        )


def test_ratebook_rejects_duplicate_gross_net_mixed_money_and_unproven_bindings():
    _, ws, _, _, _ = _preview()
    binding = _book(ws).bindings[0]
    with pytest.raises(ValueError, match="duplicate"):
        _book(ws, bindings=(binding, binding))
    with pytest.raises(ValueError, match="gross_net"):
        _book(ws, bindings=(binding, replace(binding, target="wall_net_area")))
    with pytest.raises(ValueError, match="mixed_rate"):
        _book(ws, bindings=(replace(binding, rate=_rate(currency="USD")),))
    with pytest.raises(ValueError, match="provenance"):
        replace(binding, binding_evidence_ids=())
    with pytest.raises(ValueError, match="tax_pct"):
        _book(ws, tax_pct="-1")
    with pytest.raises(ValueError, match="gross_margin"):
        _rate(gross_margin_pct=100)


def test_rate_units_do_not_cross_price_and_same_command_receipts_deterministic():
    user, ws, _, cmd, q = _preview()
    book = _book(ws)
    one = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws, book=book,
    )
    two = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws, book=book,
    )
    assert one == two
    mismatch = _book(ws, bindings=(replace(
        book.bindings[0], rate=_rate(unit="lm"),
    ),))
    denied = price_live_correction_preview(
        cmd, q, principal=user, workspace=ws, book=mismatch,
    )
    assert not denied["lines"]
    assert any(x["reason"] == "rate_unit_mismatch" for x in denied["unpriced"])


def test_duplicate_impact_refused_not_double_priced():
    user, ws, _, cmd, q = _preview()
    dup = dict(q)
    dup["quantityImpacts"] = [q["quantityImpacts"][0]] * 2
    with pytest.raises(ValueError, match="duplicate"):
        price_live_correction_preview(
            cmd, dup, principal=user, workspace=ws, book=_book(ws),
        )
