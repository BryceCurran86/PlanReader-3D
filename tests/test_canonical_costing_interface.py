from __future__ import annotations

from dataclasses import asdict

import pytest

from pb_builder_edition_architecture import (
    CanonicalCompanyRate,
    canonical_quantity_id,
    price_canonical_quantities,
)
from pb_cross_trade_geometry_reuse import (
    DerivedTradeQuantity,
    bind_derived_quantity_rate_key,
)


def _quantity(*, unit="m²", quantity=10.0):
    return DerivedTradeQuantity(
        trade_scope="painting",
        section="Internal",
        element="Wall painting",
        location="wall-1 · face-int",
        substrate="Acrylic paint system",
        quantity=quantity,
        unit=unit,
        host_object_id="wall-1",
        host_object_type="WALL",
        derivation_formula="Canonical net wall area 10.000000 m²",
        host_evidence_ids=("wall-quantity-1",),
        spec_evidence_ids=("paint-spec-1",),
    )


def _rate(**changes):
    values = dict(
        rate_key="paint.internal.standard",
        unit="m²",
        currency="AUD",
        material_cost_per_unit=12.0,
        labour_cost_per_unit=8.0,
        subcontract_cost_per_unit=0.0,
        plant_cost_per_unit=1.0,
        material_waste_pct=5.0,
        overhead_pct=10.0,
        gross_margin_pct=20.0,
        evidence_ids=("company-rate-config-v1",),
    )
    values.update(changes)
    return CanonicalCompanyRate(**values)


def _bound_quantity(**changes):
    quantity = _quantity(**changes)
    return bind_derived_quantity_rate_key(
        quantity,
        rate_key="paint.internal.standard",
        evidence_ids=("company-rate-binding-v1",),
    )


def test_component_costs_and_true_gross_margin_are_explicit():
    result = price_canonical_quantities(
        (_bound_quantity(),),
        (_rate(),),
    )

    assert result.complete is True
    assert result.unrated_quantity_ids == ()
    assert result.currency == "AUD"
    assert len(result.lines) == 1
    line = result.lines[0]

    # 10 m²:
    # material 120 + 5% material waste 6
    # labour 80 + plant 10 => direct 216
    # overhead 10% = 21.60 => cost before margin 237.60
    # true gross margin 20% => sell = 237.60 / 0.80 = 297.00
    assert line.material_base_cost == 120.0
    assert line.material_waste_cost == 6.0
    assert line.labour_cost == 80.0
    assert line.subcontract_cost == 0.0
    assert line.plant_cost == 10.0
    assert line.direct_cost == 216.0
    assert line.overhead_cost == 21.6
    assert line.cost_before_margin == 237.6
    assert line.margin_amount == 59.4
    assert line.sell_price == 297.0
    assert result.sell_price_total == 297.0


def test_rate_change_reprices_without_changing_canonical_quantity():
    quantity = _bound_quantity()
    before = asdict(quantity)
    quantity_id = canonical_quantity_id(quantity)

    first = price_canonical_quantities((quantity,), (_rate(),))
    second = price_canonical_quantities(
        (quantity,),
        (
            _rate(
                material_cost_per_unit=18.0,
                labour_cost_per_unit=10.0,
                evidence_ids=("company-rate-config-v2",),
            ),
        ),
    )

    assert canonical_quantity_id(quantity) == quantity_id
    assert asdict(quantity) == before
    assert first.lines[0].canonical_quantity_id == quantity_id
    assert second.lines[0].canonical_quantity_id == quantity_id
    assert second.sell_price_total > first.sell_price_total


def test_missing_rate_is_unpriced_not_zero_cost():
    quantity = _bound_quantity()

    result = price_canonical_quantities((quantity,), ())

    assert result.complete is False
    assert result.lines == ()
    assert result.unrated_quantity_ids == (canonical_quantity_id(quantity),)
    assert result.sell_price_total == 0.0
    assert result.currency is None


def test_unbound_quantity_is_unpriced_even_when_matching_rate_exists():
    quantity = _quantity()

    result = price_canonical_quantities((quantity,), (_rate(),))

    assert result.complete is False
    assert result.lines == ()
    assert result.unrated_quantity_ids == (canonical_quantity_id(quantity),)


def test_rate_binding_requires_provenance():
    quantity = _quantity()

    with pytest.raises(ValueError):
        bind_derived_quantity_rate_key(
            quantity,
            rate_key="paint.internal.standard",
            evidence_ids=(),
        )


def test_m3_is_supported_by_canonical_costing_independent_of_legacy_takeoff_units():
    quantity = DerivedTradeQuantity(
        trade_scope="concrete",
        section="Structure",
        element="Slab concrete",
        location="slab-1",
        substrate="25 MPa concrete",
        quantity=18.0,
        unit="m³",
        host_object_id="slab-1",
        host_object_type="SLAB",
        derivation_formula="120.0 m² × 0.15 m",
        host_evidence_ids=("slab-area-1", "slab-thickness-1"),
        spec_evidence_ids=("concrete-spec-1",),
    )
    quantity = bind_derived_quantity_rate_key(
        quantity,
        rate_key="concrete.25mpa",
        evidence_ids=("company-rate-binding-v1",),
    )
    rate = CanonicalCompanyRate(
        rate_key="concrete.25mpa",
        unit="m³",
        currency="AUD",
        material_cost_per_unit=240.0,
        labour_cost_per_unit=35.0,
        plant_cost_per_unit=10.0,
        gross_margin_pct=10.0,
        evidence_ids=("company-concrete-rate-v1",),
    )

    result = price_canonical_quantities((quantity,), (rate,))

    assert result.complete is True
    assert result.lines[0].unit == "m³"
    assert result.lines[0].quantity == 18.0
    assert result.lines[0].sell_price > 0.0


def test_rate_unit_mismatch_fails_closed():
    quantity = _bound_quantity()

    with pytest.raises(ValueError):
        price_canonical_quantities(
            (quantity,),
            (_rate(unit="lm"),),
        )


def test_duplicate_rate_key_is_rejected():
    with pytest.raises(ValueError):
        price_canonical_quantities(
            (_bound_quantity(),),
            (
                _rate(evidence_ids=("rate-v1",)),
                _rate(evidence_ids=("rate-v2",)),
            ),
        )


def test_mixed_currencies_cannot_enter_one_result():
    first = _bound_quantity()
    second_raw = DerivedTradeQuantity(
        trade_scope="tiling",
        section="Internal",
        element="Floor tiling",
        location="floor-1",
        substrate="Porcelain tile",
        quantity=20.0,
        unit="m²",
        host_object_id="floor-1",
        host_object_type="FLOOR",
        derivation_formula="Canonical floor metric area 20 m²",
        host_evidence_ids=("floor-area-1",),
        spec_evidence_ids=("tile-spec-1",),
    )
    second = bind_derived_quantity_rate_key(
        second_raw,
        rate_key="tile.internal.standard",
        evidence_ids=("company-rate-binding-v1",),
    )
    aud = _rate()
    usd = CanonicalCompanyRate(
        rate_key="tile.internal.standard",
        unit="m²",
        currency="USD",
        material_cost_per_unit=20.0,
        labour_cost_per_unit=15.0,
        evidence_ids=("usd-rate-v1",),
    )

    with pytest.raises(ValueError):
        price_canonical_quantities((first, second), (aud, usd))


def test_rate_validation_rejects_invalid_margin_and_missing_provenance():
    with pytest.raises(ValueError):
        _rate(gross_margin_pct=100.0)
    with pytest.raises(ValueError):
        _rate(evidence_ids=())
