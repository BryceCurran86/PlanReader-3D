"""Synthetic evidence completeness tests for cladding net quantity publication."""
from __future__ import annotations

import pytest
from pb_carpentry_trade_authority import CarpentryElementSpec, calculate_eaves_and_cladding_items


def _spec(openings):
    return CarpentryElementSpec(
        element_type="cladding", element_id="synthetic-elevation",
        description="synthetic external cladding area",
        area_m2=50.0, openings=openings,
    )


def test_authentic_positive_cladding_opening_deductions_are_subtracted_once():
    rows = calculate_eaves_and_cladding_items(_spec([{"area": 8.0}]))
    assert len(rows) == 1
    assert rows[0].quantity == pytest.approx(42.0)


def test_unopened_elevation_preserves_whole_evidenced_cladding_area():
    rows = calculate_eaves_and_cladding_items(_spec([]))
    assert len(rows) == 1
    assert rows[0].quantity == pytest.approx(50.0)


@pytest.mark.parametrize("openings", [
    [{"width": 1.0, "height": 2.0}], [{"area": None}],
    [{"area": "8"}], [{"area": True}], [{"area": 0.0}],
    [{"area": -4.0}], [{"area": float("nan")}],
    [{"area": float("inf")}], [{"area": 10**400}],
    [{"area": 60.0}], [{"area": 50.0}], [{"area": 30.0}, {"area": 25.0}],
    [None], [8.0],
])
def test_unresolved_or_physically_impossible_opening_deduction_never_mints_measured_cladding(openings):
    assert calculate_eaves_and_cladding_items(_spec(openings)) == []


def test_one_invalid_opening_cannot_be_filtered_away_before_net_area():
    rows = calculate_eaves_and_cladding_items(_spec([
        {"area": 8.0}, {"width": 1.0, "height": 1.5},
    ]))
    assert rows == []
