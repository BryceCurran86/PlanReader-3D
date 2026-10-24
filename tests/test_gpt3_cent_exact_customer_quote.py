"""Client-facing monetary component totals must exactly reconcile to every line."""
from __future__ import annotations

from decimal import Decimal

import pytest

from tools.gpt3_verified_customer_quote import (
    _cent_exact_cost_components, build_verified_customer_quote,
)
from test_gpt3_verified_customer_quote import fixture


def _card(material, labour, plant, subcontract):
    return {
        "material": Decimal(str(material)),
        "labour": Decimal(str(labour)),
        "plant": Decimal(str(plant)),
        "subcontract": Decimal(str(subcontract)),
    }


def test_four_half_cent_components_total_two_cents_not_four():
    amounts, total = _cent_exact_cost_components(
        Decimal("1"), _card("0.005", "0.005", "0.005", "0.005"),
    )
    assert total == Decimal("0.02")
    assert sum(map(Decimal, amounts.values())) == total
    assert amounts == {
        "material": "0.01", "labour": "0.01",
        "plant": "0.00", "subcontract": "0.00",
    }


@pytest.mark.parametrize(("units", "rates"), [
    ("0.01", ("3.333", "5.555", "2.222", "8.888")),
    ("1.000001", ("10.015", "0.005", "0.005", "0.005")),
    ("2.37", ("100.05", "31.05", "7.05", "0.05")),
    ("0", ("9", "8", "7", "6")),
    ("10000.01", ("0.001", "0.002", "0.003", "0.004")),
])
def test_cent_allocator_preserves_billable_quantity_and_sum(units, rates):
    billable = Decimal(units)
    card = _card(*rates)
    original = billable
    amounts, cost = _cent_exact_cost_components(billable, card)
    raw = sum((billable * card[key] for key in card), Decimal("0"))
    assert cost == raw.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
    assert sum(map(Decimal, amounts.values())) == cost
    assert all(Decimal(value) >= 0 for value in amounts.values())
    assert billable == original


def test_signed_original_eight_customer_quantities_keep_exact_cost_totals():
    sealed, customers, rates = fixture()
    quote = build_verified_customer_quote(sealed, customers, rates)
    assert quote["signed_quantity_count"] == 8
    assert quote["publication_status"] == "CLIENT_PRICED_QUOTE"
    assert quote["official_four_project_accuracy"] is None
    for item in quote["items"]:
        assert sum(
            (Decimal(amount) for amount in item["cost_components"].values()),
            Decimal("0"),
        ) == Decimal(item["cost_amount"])
        assert item["quantity_fingerprint"]
        assert item["source_sha256"]


def test_quote_component_overflow_fails_closed():
    with pytest.raises(ValueError, match="safe financial bound"):
        _cent_exact_cost_components(
            Decimal("1000000000000"), _card("999", "999", "999", "999"),
        )


def test_quote_component_negative_physical_quantity_cannot_be_priced():
    with pytest.raises(ValueError, match="finite and nonnegative"):
        _cent_exact_cost_components(
            Decimal("-1"), _card("10", "0", "0", "0"),
        )


def test_original_client_rate_card_is_not_rewritten_by_cent_allocation():
    card = _card("0.005", "0.005", "0.005", "0.005")
    original = dict(card)
    _cent_exact_cost_components(Decimal("1"), card)
    assert card == original
