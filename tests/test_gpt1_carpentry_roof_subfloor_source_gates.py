"""Gold-free source authority for structural carpentry quantities.

A conventional structural layout assumption can remain a commercial estimate
but it cannot be represented as signed, exact, drawing-measured material.
"""
import math
import pytest
from pb_carpentry_trade_authority import (
    CarpentryElementSpec, calculate_subfloor_framing_items,
    calculate_roof_framing_items,
)


def test_genuine_complete_roof_axes_retain_count_as_provisional_design_estimate():
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=15.0,width_m=8.0,
    )
    rows = calculate_roof_framing_items(spec)
    assert len(rows) == 2
    assert rows[0].quantity == 18.0
    assert rows[1].quantity == 150.0
    assert all(x.inclusion_status == "PROVISIONAL" for x in rows)
    assert all(x.quantity_status == "Provisional" for x in rows)
    assert all(x.confidence == "Provisional" for x in rows)


def test_missing_original_roof_span_never_issues_invented_eight_metre_trusses():
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=15.0,width_m=0.0,
    )
    assert calculate_roof_framing_items(spec) == []


def test_evidenced_roof_area_without_truss_span_is_not_licence_for_truss_count():
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=15.0,area_m2=120.0,
    )
    rows = calculate_roof_framing_items(spec)
    assert len(rows) == 1
    assert rows[0].element.startswith("Timber roof battens")
    assert rows[0].inclusion_status == "PROVISIONAL"
    assert rows[0].quantity == 150.0


@pytest.mark.parametrize("bad", [True,"15",float("inf"),float("nan"),10**400])
def test_untyped_or_unbounded_roof_axes_cannot_mint_trusses(bad):
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=bad,width_m=8.0,
    )
    assert calculate_roof_framing_items(spec) == []


def test_subfloor_area_and_joists_remain_visible_but_not_fake_verified():
    spec = CarpentryElementSpec(
        element_type="subfloor",element_id="synthetic-floor",
        description="floor",area_m2=80.0,
    )
    rows = calculate_subfloor_framing_items(spec)
    assert [x.quantity for x in rows] == [80.0,192.0]
    assert all(x.quantity_status == "Provisional" for x in rows)
    assert all(x.inclusion_status == "PROVISIONAL" for x in rows)


@pytest.mark.parametrize("area", [True,"80",float("nan"),float("inf"),10**400,-30.0])
def test_untyped_or_invalid_source_subfloor_area_never_becomes_material(area):
    spec = CarpentryElementSpec(
        element_type="subfloor",element_id="synthetic-floor",
        description="floor",area_m2=area,
    )
    assert calculate_subfloor_framing_items(spec) == []


def test_conflicting_subfloor_metric_area_and_native_dimensions_abstain():
    spec = CarpentryElementSpec(
        element_type="subfloor",element_id="synthetic-floor",
        description="floor",area_m2=80.0,length_m=10.0,width_m=10.0,
    )
    assert calculate_subfloor_framing_items(spec) == []


def test_matching_subfloor_metric_area_and_native_dimensions_remain_estimate():
    spec = CarpentryElementSpec(
        element_type="subfloor",element_id="synthetic-floor",
        description="floor",area_m2=80.0,length_m=10.0,width_m=8.0,
    )
    rows = calculate_subfloor_framing_items(spec)
    assert [x.quantity for x in rows] == [80.0,192.0]
    assert all(x.quantity_status == "Provisional" for x in rows)


def test_contradictory_roof_footprint_and_native_axes_do_not_mint_trusses_or_battens():
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=15.0,width_m=8.0,area_m2=180.0,
    )
    assert calculate_roof_framing_items(spec) == []


@pytest.mark.parametrize("bad_area", [-1.0, True, "120", float("nan"), float("inf"), 10**400])
def test_broken_original_roof_area_does_not_fall_back_to_plausible_axes(bad_area):
    spec = CarpentryElementSpec(
        element_type="roof_frame",element_id="synthetic-roof",
        description="roof",length_m=15.0,width_m=8.0,area_m2=bad_area,
    )
    assert calculate_roof_framing_items(spec) == []
