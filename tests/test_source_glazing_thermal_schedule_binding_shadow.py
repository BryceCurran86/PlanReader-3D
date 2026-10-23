"""Unit tests for Producer-Owned Glazing U-Value and Thermal Performance Schedule Binding Shadow Authority.

Tests positive, negative, and conflicting schedule scenarios.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_glazing_thermal_schedule_binding_shadow import (
    FrameSubstrate,
    GlazingAssembly,
    GlazingThermalBindingEvidence,
    GlazingThermalScheduleBindingShadowAuthority,
    ThermalScheduleEntry,
)


def test_positive_glazing_thermal_binding():
    authority = GlazingThermalScheduleBindingShadowAuthority()
    entry = ThermalScheduleEntry(
        mark="W01",
        width_mm=1800.0,
        height_mm=1200.0,
        u_value_w_m2k=2.8,
        shgc=0.45,
        glazing_assembly=GlazingAssembly.DOUBLE_LOW_E,
        frame_substrate=FrameSubstrate.ALUMINIUM_THERMALLY_BROKEN,
        schedule_page_id="29",
        source_table_row_id="row_w01",
    )
    authority.register_schedule_entry(entry)

    evidence = authority.bind_opening(
        opening_id="OPENING_W01_P7",
        mark="W01",
        physical_width_m=1.80,
        physical_height_m=1.20,
    )

    assert evidence.status == EvidenceResolutionStatus.CANDIDATE
    assert pytest.approx(evidence.u_value_w_m2k, rel=1e-2) == 2.80
    assert pytest.approx(evidence.shgc, rel=1e-2) == 0.45
    assert evidence.glazing_assembly == GlazingAssembly.DOUBLE_LOW_E
    assert evidence.frame_substrate == FrameSubstrate.ALUMINIUM_THERMALLY_BROKEN
    # Area = 1.8 * 1.2 = 2.16 m²
    assert pytest.approx(evidence.opening_area_sqm, rel=1e-3) == 2.16
    # Conductance = 2.8 * 2.16 = 6.048 W/K
    assert pytest.approx(evidence.thermal_conductance_w_k, rel=1e-3) == 6.048
    assert evidence.commercial_projection_allowed is False
    assert evidence.takeoff_eligible is False


def test_negative_unregistered_mark_abstains():
    authority = GlazingThermalScheduleBindingShadowAuthority()
    evidence = authority.bind_opening(
        opening_id="OPENING_W99",
        mark="W99",
        physical_width_m=1.0,
        physical_height_m=1.0,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "No thermal schedule entry found" in evidence.notes


def test_negative_conflicting_schedule_ratings_abstains():
    authority = GlazingThermalScheduleBindingShadowAuthority()
    # Conflicting U-values for same mark W02
    e1 = ThermalScheduleEntry("W02", 1200.0, 1200.0, 2.5, 0.40, GlazingAssembly.DOUBLE_LOW_E, FrameSubstrate.UPVC, "29", "r1")
    e2 = ThermalScheduleEntry("W02", 1200.0, 1200.0, 4.8, 0.65, GlazingAssembly.SINGLE_CLEAR, FrameSubstrate.ALUMINIUM_STANDARD, "29", "r2")
    authority.register_schedule_entry(e1)
    authority.register_schedule_entry(e2)

    evidence = authority.bind_opening(
        opening_id="OPENING_W02",
        mark="W02",
        physical_width_m=1.20,
        physical_height_m=1.20,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "Conflicting thermal ratings" in evidence.notes


def test_negative_non_physical_u_value_abstains():
    authority = GlazingThermalScheduleBindingShadowAuthority()
    # U-value 9.5 W/m²K is non-physical
    entry = ThermalScheduleEntry("W03", 1000.0, 1000.0, 9.5, 0.50, GlazingAssembly.SINGLE_CLEAR, FrameSubstrate.TIMBER, "29", "r3")
    authority.register_schedule_entry(entry)

    evidence = authority.bind_opening(
        opening_id="OPENING_W03",
        mark="W03",
        physical_width_m=1.0,
        physical_height_m=1.0,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "Non-physical U-value" in evidence.notes


def test_negative_dimension_mismatch_abstains():
    authority = GlazingThermalScheduleBindingShadowAuthority()
    # Schedule says 2.4m x 2.1m, but physical opening is 1.2m x 1.2m
    entry = ThermalScheduleEntry("W04", 2400.0, 2100.0, 2.2, 0.35, GlazingAssembly.DOUBLE_LOW_E, FrameSubstrate.ALUMINIUM_THERMALLY_BROKEN, "29", "r4")
    authority.register_schedule_entry(entry)

    evidence = authority.bind_opening(
        opening_id="OPENING_W04",
        mark="W04",
        physical_width_m=1.20,
        physical_height_m=1.20,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "Dimension mismatch" in evidence.notes
