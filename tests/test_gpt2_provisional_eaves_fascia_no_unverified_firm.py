"""Unissued generic soffit/fascia defaults cannot masquerade as measured takeoff."""
from __future__ import annotations

import math

import pytest

from pb_carpentry_trade_authority import (
    CarpentryElementSpec, calculate_eaves_and_cladding_items,
    generate_workspace_carpentry_takeoff,
)


@pytest.mark.parametrize("width", [0.6, 0.9, 0.0])
def test_eaves_are_provisional_even_with_perimeter_and_named_source_page(width):
    spec = CarpentryElementSpec(
        element_type="eaves", element_id="UNVERIFIED_EAVE",
        description="Unresolved canopy/eave underside",
        perimeter_lm=40, overhang_width_m=width,
        source_page="Architectural ceiling and roof plan",
        source_reference="Draft drawing reference, not an issued metric receipt",
    )
    items = calculate_eaves_and_cladding_items(spec)
    assert len(items) == 2
    assert items[0].quantity == (40 * (width or 0.6))
    assert items[1].quantity == 40.0
    assert all(item.quantity_status == "Provisional" for item in items)
    assert all(item.inclusion_status == "PROVISIONAL" for item in items)
    assert all(item.confidence == "Provisional" for item in items)
    assert all("NOT source-authenticated" in item.notes for item in items)
    rows = generate_workspace_carpentry_takeoff([spec], 1, "2026-10-19")
    assert len(rows) == 2
    assert all(row["quantity_status"] == "Provisional" for row in rows)
    assert all(row["inclusion_status"] == "PROVISIONAL" for row in rows)
    assert all(row["confidence"] == "Provisional" for row in rows)


@pytest.mark.parametrize("width", [float("nan"), float("inf"), -1.0])
def test_invalid_overhang_cannot_issue_customer_area(width):
    spec = CarpentryElementSpec(
        element_type="eaves", element_id="INVALID_EAVE",
        description="Untrusted width", perimeter_lm=40,
        overhang_width_m=width,
    )
    assert calculate_eaves_and_cladding_items(spec) == []
    assert generate_workspace_carpentry_takeoff([spec], 1, "now") == []


@pytest.mark.parametrize("perimeter", [float("nan"), float("inf"), -40])
def test_invalid_perimeter_cannot_issue_customer_fascia_or_soffit(perimeter):
    spec = CarpentryElementSpec(
        element_type="eaves", element_id="INVALID_PERIMETER",
        description="Untrusted envelope", perimeter_lm=perimeter,
    )
    assert calculate_eaves_and_cladding_items(spec) == []


def test_unrelated_documented_cladding_path_unchanged():
    spec = CarpentryElementSpec(
        element_type="cladding", element_id="CLADDING",
        description="Original cladding caller behaviour",
        area_m2=20.0, openings=[{"area": 2.0}],
    )
    items = calculate_eaves_and_cladding_items(spec)
    assert len(items) == 1
    assert items[0].quantity == 18.0
    assert items[0].quantity_status == "Measured"
