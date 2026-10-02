"""Contract hardening for canonical costing (review findings on PR #1190).

Every test here pins one rule from the canonical-costing contract:

* a company rate never changes quantity identity, and identity covers every
  declared identity field (so different quantities never share an id);
* the same canonical quantity can never be priced twice;
* a missing/empty rate is UNPRICED with an explicit reason, never zero-cost;
* no guessed currency; units normalise like quantity units but never cross;
* cost lines foot to the cent and keep their provenance.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import asdict, replace
from decimal import Decimal

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

RATE_KEY = "paint.internal.standard"


def _quantity(**changes) -> DerivedTradeQuantity:
    values = dict(
        trade_scope="painting",
        section="Internal",
        element="Wall painting",
        location="wall-1 · face-int",
        substrate="Acrylic paint system",
        quantity=10.0,
        unit="m²",
        host_object_id="wall-1",
        host_object_type="WALL",
        derivation_formula="Canonical net wall area 10.000000 m²",
        host_evidence_ids=("wall-quantity-1", "wall-height-1"),
        spec_evidence_ids=("paint-spec-1", "paint-spec-2"),
    )
    values.update(changes)
    return DerivedTradeQuantity(**values)


def _bound(rate_key: str = RATE_KEY, evidence=("company-rate-binding-v1",), **changes):
    return bind_derived_quantity_rate_key(
        _quantity(**changes), rate_key=rate_key, evidence_ids=evidence
    )


def _rate(**changes) -> CanonicalCompanyRate:
    values = dict(
        rate_key=RATE_KEY,
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


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

_IDENTITY_MUTATIONS = {
    "trade_scope": "tiling",
    "section": "External",
    "element": "Ceiling painting",
    "location": "wall-1 · face-ext",
    "substrate": "Enamel",
    "quantity": 11.0,
    "unit": "lm",
    "host_object_id": "wall-2",
    "host_object_type": "SLAB",
    "derivation_formula": "Canonical net wall area 11.000000 m²",
    "host_evidence_ids": ("wall-quantity-1", "wall-height-2"),
    "spec_evidence_ids": ("paint-spec-1", "paint-spec-3"),
}


@pytest.mark.parametrize("field,value", sorted(_IDENTITY_MUTATIONS.items()))
def test_identity_covers_every_declared_identity_field(field, value):
    base = _quantity()
    changed = _quantity(**{field: value})

    assert canonical_quantity_id(base) != canonical_quantity_id(changed), field


def test_identity_excludes_every_rate_input():
    base = _quantity()
    base_id = canonical_quantity_id(base)

    for key, evidence in itertools.product(
        ("paint.internal.standard", "paint.OTHER", "x"),
        (("binding-a",), ("binding-b", "binding-c")),
    ):
        bound = bind_derived_quantity_rate_key(
            base, rate_key=key, evidence_ids=evidence
        )
        assert canonical_quantity_id(bound) == base_id

    # Pricing under very different company rates never touches the id.
    bound = _bound()
    for rate in (
        _rate(),
        _rate(material_cost_per_unit=99.5, labour_cost_per_unit=31.25),
        _rate(currency="USD", gross_margin_pct=33.3, overhead_pct=17.5),
        _rate(material_waste_pct=12.5, evidence_ids=("other-config",)),
    ):
        line = price_canonical_quantities((bound,), (rate,)).lines[0]
        assert line.canonical_quantity_id == base_id


def test_same_quantity_gets_same_id_regardless_of_evidence_order_or_whitespace():
    reference = canonical_quantity_id(_quantity())

    reordered = _quantity(
        host_evidence_ids=("wall-height-1", "wall-quantity-1"),
        spec_evidence_ids=("paint-spec-2", "paint-spec-1"),
    )
    padded = _quantity(
        host_object_id=" wall-1 ",
        element="Wall painting ",
        host_evidence_ids=(" wall-quantity-1", "wall-height-1 "),
    )
    negative_zero = canonical_quantity_id(_quantity(quantity=-0.0))
    positive_zero = canonical_quantity_id(_quantity(quantity=0.0))

    assert canonical_quantity_id(reordered) == reference
    assert canonical_quantity_id(padded) == reference
    assert negative_zero == positive_zero


def test_quantities_differing_only_in_section_are_both_priced():
    internal = _bound(section="Internal")
    external = _bound(section="External")

    result = price_canonical_quantities((internal, external), (_rate(),))

    assert result.complete is True
    assert len(result.lines) == 2
    assert result.lines[0].canonical_quantity_id != result.lines[1].canonical_quantity_id


# --------------------------------------------------------------------------
# No duplicate quantities
# --------------------------------------------------------------------------


def test_same_quantity_object_twice_is_rejected_not_double_priced():
    quantity = _bound()

    with pytest.raises(ValueError, match="duplicate"):
        price_canonical_quantities((quantity, quantity), (_rate(),))


def test_equal_quantity_objects_are_rejected_even_when_unrated():
    first = _quantity()
    second = _quantity()

    with pytest.raises(ValueError, match="duplicate"):
        price_canonical_quantities((first, second), ())


def test_result_is_input_order_invariant():
    quantities = [
        _bound(host_object_id=f"wall-{index}", quantity=float(index + 1))
        for index in range(8)
    ]
    forward = price_canonical_quantities(quantities, (_rate(),))
    rng = random.Random(7)
    for _ in range(20):
        shuffled = quantities[:]
        rng.shuffle(shuffled)
        assert price_canonical_quantities(shuffled, (_rate(),)) == forward


# --------------------------------------------------------------------------
# Missing / empty rates are UNPRICED with explicit reasons
# --------------------------------------------------------------------------


def test_rate_with_no_cost_components_is_rejected():
    with pytest.raises(ValueError, match="cost component"):
        _rate(
            material_cost_per_unit=0.0,
            labour_cost_per_unit=0.0,
            subcontract_cost_per_unit=0.0,
            plant_cost_per_unit=0.0,
        )


def test_single_component_rate_is_a_valid_supply_only_rate():
    rate = _rate(
        material_cost_per_unit=5.0,
        labour_cost_per_unit=0.0,
        plant_cost_per_unit=0.0,
        material_waste_pct=0.0,
        overhead_pct=0.0,
        gross_margin_pct=0.0,
    )

    line = price_canonical_quantities((_bound(),), (rate,)).lines[0]

    assert line.direct_cost == 50.0
    assert line.sell_price == 50.0


def test_unpriced_reasons_are_explicit_and_distinct():
    no_key = _quantity(host_object_id="wall-a")
    no_binding = replace(
        _quantity(host_object_id="wall-b"), rate_key=RATE_KEY, rate_binding_evidence_ids=()
    )
    unknown_key = _bound(rate_key="not.in.rate.set", host_object_id="wall-c")
    priced = _bound(host_object_id="wall-d")

    result = price_canonical_quantities(
        (no_key, no_binding, unknown_key, priced), (_rate(),)
    )

    reasons = {item.host_object_id: item.reason for item in result.unpriced}
    assert reasons == {
        "wall-a": "no_rate_key",
        "wall-b": "no_rate_binding_evidence",
        "wall-c": "rate_key_not_in_rate_set",
    }
    assert result.complete is False
    assert len(result.lines) == 1
    assert result.unrated_quantity_ids == tuple(item.canonical_quantity_id for item in result.unpriced)
    by_host = {item.host_object_id: item for item in result.unpriced}
    assert by_host["wall-c"].rate_key == "not.in.rate.set"
    assert by_host["wall-a"].rate_key is None
    assert by_host["wall-a"].element == "Wall painting"
    assert by_host["wall-a"].unit == "m²"


def test_empty_input_is_not_a_complete_costing():
    result = price_canonical_quantities((), (_rate(),))

    assert result.complete is False
    assert result.lines == ()
    assert result.unpriced == ()
    assert result.sell_price_total == 0.0


# --------------------------------------------------------------------------
# Currency and units
# --------------------------------------------------------------------------


def test_currency_is_required_not_guessed():
    with pytest.raises(TypeError):
        CanonicalCompanyRate(  # type: ignore[call-arg]
            rate_key=RATE_KEY,
            unit="m²",
            material_cost_per_unit=1.0,
            evidence_ids=("cfg",),
        )


@pytest.mark.parametrize("bad", ["", "  ", "A$", "AU", "AUDD", "12$"])
def test_currency_must_be_a_three_letter_code(bad):
    with pytest.raises(ValueError, match="currency"):
        _rate(currency=bad)


def test_currency_is_normalised_but_a_conflict_still_fails_closed():
    assert _rate(currency=" aud ").currency == "AUD"

    other = _bound(rate_key="tile.std", host_object_id="floor-1")
    with pytest.raises(ValueError, match="currenc"):
        price_canonical_quantities(
            (_bound(), other),
            (_rate(), _rate(rate_key="tile.std", currency="usd")),
        )


@pytest.mark.parametrize(
    "rate_unit,quantity_unit",
    [("m2", "m²"), ("sqm", "m²"), ("m^2", "m²"), ("m3", "m³"), ("NO", "No."),
     ("ea", "No."), ("linear_m", "lm")],
)
def test_rate_unit_aliases_normalise_like_quantity_units(rate_unit, quantity_unit):
    quantity = _bound(unit=quantity_unit)

    result = price_canonical_quantities((quantity,), (_rate(unit=rate_unit),))

    assert result.complete is True
    assert result.lines[0].unit == quantity_unit


@pytest.mark.parametrize(
    "rate_unit,quantity_unit",
    [("m²", "m³"), ("m³", "m²"), ("lm", "m²"), ("No.", "m²"), ("m²", "No."), ("m²", "lm")],
)
def test_different_units_never_cross_price(rate_unit, quantity_unit):
    with pytest.raises(ValueError, match="unit"):
        price_canonical_quantities(
            (_bound(unit=quantity_unit),), (_rate(unit=rate_unit),)
        )


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

_NUMERIC_FIELDS = (
    "material_cost_per_unit",
    "labour_cost_per_unit",
    "subcontract_cost_per_unit",
    "plant_cost_per_unit",
    "material_waste_pct",
    "overhead_pct",
    "gross_margin_pct",
)


@pytest.mark.parametrize("field", _NUMERIC_FIELDS)
@pytest.mark.parametrize(
    "bad", [True, False, "15", None, float("nan"), float("inf"), -1.0]
)
def test_rate_numbers_must_be_real_finite_non_negative(field, bad):
    with pytest.raises((TypeError, ValueError)):
        _rate(**{field: bad})


@pytest.mark.parametrize("field", ["evidence_ids"])
def test_plain_string_evidence_is_rejected_not_split_into_characters(field):
    with pytest.raises(TypeError):
        _rate(**{field: "company-rate-config-v1"})


def test_binding_rejects_plain_string_evidence():
    with pytest.raises(TypeError):
        bind_derived_quantity_rate_key(
            _quantity(), rate_key=RATE_KEY, evidence_ids="company-rate-binding-v1"
        )


def test_binding_returns_a_new_object_and_never_mutates_the_source():
    source = _quantity()
    snapshot = asdict(source)

    bound = bind_derived_quantity_rate_key(
        source, rate_key=RATE_KEY, evidence_ids=("binding-1",)
    )

    assert bound is not source
    assert asdict(source) == snapshot
    assert source.rate_key is None and source.rate_binding_evidence_ids == ()


# --------------------------------------------------------------------------
# Money maths
# --------------------------------------------------------------------------


def test_every_line_and_total_foots_to_the_cent():
    rng = random.Random(20261002)
    quantities = []
    rates = []
    for index in range(120):
        key = f"rate.{index}"
        quantities.append(
            _bound(
                rate_key=key,
                host_object_id=f"wall-{index}",
                quantity=round(rng.uniform(0.01, 987.654321), 6),
            )
        )
        rates.append(
            _rate(
                rate_key=key,
                material_cost_per_unit=round(rng.uniform(0.01, 250.0), 4),
                labour_cost_per_unit=round(rng.uniform(0.0, 120.0), 4),
                subcontract_cost_per_unit=round(rng.uniform(0.0, 40.0), 4),
                plant_cost_per_unit=round(rng.uniform(0.0, 15.0), 4),
                material_waste_pct=round(rng.uniform(0.0, 20.0), 3),
                overhead_pct=round(rng.uniform(0.0, 30.0), 3),
                gross_margin_pct=round(rng.uniform(0.0, 60.0), 3),
            )
        )

    result = price_canonical_quantities(quantities, rates)

    def cents(value: float) -> Decimal:
        return Decimal(repr(value))

    for line in result.lines:
        direct = (
            cents(line.material_base_cost)
            + cents(line.material_waste_cost)
            + cents(line.labour_cost)
            + cents(line.subcontract_cost)
            + cents(line.plant_cost)
        )
        assert cents(line.direct_cost) == direct
        assert cents(line.cost_before_margin) == direct + cents(line.overhead_cost)
        assert cents(line.sell_price) == cents(line.cost_before_margin) + cents(line.margin_amount)
    assert cents(result.sell_price_total) == sum(cents(l.sell_price) for l in result.lines)
    assert cents(result.direct_cost_total) == sum(cents(l.direct_cost) for l in result.lines)
    assert cents(result.overhead_total) == sum(cents(l.overhead_cost) for l in result.lines)
    assert cents(result.margin_total) == sum(cents(l.margin_amount) for l in result.lines)


def test_gross_margin_is_margin_on_sell_price_not_markup():
    line = price_canonical_quantities(
        (_bound(),), (_rate(gross_margin_pct=25.0, overhead_pct=0.0, material_waste_pct=0.0),)
    ).lines[0]

    # cost 10 * (12 + 8 + 1) = 210 -> sell = 210 / 0.75 = 280, margin 70 = 25% OF SELL
    assert line.cost_before_margin == 210.0
    assert line.sell_price == 280.0
    assert line.margin_amount == 70.0
    assert line.margin_basis == "gross_margin_on_sell_price"
    assert line.margin_amount / line.sell_price == pytest.approx(0.25)


# --------------------------------------------------------------------------
# Provenance carried onto the cost line
# --------------------------------------------------------------------------


def test_cost_line_keeps_quantity_context_and_a_rate_snapshot():
    quantity = _bound(
        status="Provisional", confidence="Source-derived", host_object_id="wall-9"
    )
    rate = _rate()

    line = price_canonical_quantities((quantity,), (rate,)).lines[0]

    assert (line.section, line.location, line.substrate) == (
        quantity.section, quantity.location, quantity.substrate,
    )
    assert line.quantity_status == "Provisional"
    assert line.quantity_confidence == "Source-derived"
    assert line.rate_unit == "m²"
    assert line.rate_material_cost_per_unit == 12.0
    assert line.rate_labour_cost_per_unit == 8.0
    assert line.rate_subcontract_cost_per_unit == 0.0
    assert line.rate_plant_cost_per_unit == 1.0
    assert line.rate_material_waste_pct == 5.0
    assert line.rate_overhead_pct == 10.0
    assert line.quantity_evidence_ids == quantity.host_evidence_ids
    assert line.spec_evidence_ids == quantity.spec_evidence_ids
    assert line.rate_binding_evidence_ids == quantity.rate_binding_evidence_ids
    assert line.rate_evidence_ids == rate.evidence_ids


def test_pricing_never_mutates_quantities_or_rates():
    quantity = _bound()
    rate = _rate()
    quantity_before = asdict(quantity)
    rate_before = asdict(rate)

    price_canonical_quantities((quantity,), (rate,))

    assert asdict(quantity) == quantity_before
    assert asdict(rate) == rate_before
