"""GPT1: numeric-integrity and provenance-negative tests for the existing M5 authority seam.

These tests use synthetic quantities only. They never inspect benchmark truth,
issue source-based promotions, or mutate customer/signed output.
"""
from __future__ import annotations

import math

import pytest

from pb_figured_dimension_authority import (
    DimensionParseError,
    parse_figured_dimension_mm,
    resolve_measurement_authority,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import QuantityEvidence
from pb_migration_measurement_authority_binder import (
    MeasurementAuthorityBindingError,
    bind_commercial_measurement_authority,
)


def _quantity(*, evidence_ids=("dimension_source_1",)):
    return QuantityEvidence(
        quantity_id="test_figure_1",
        family="figured_dimension",
        semantic_key="independent_span",
        value=6.5,
        unit="m",
        evidence_ids=evidence_ids,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status="firm",
        confidence=1.0,
    )


@pytest.mark.parametrize(
    "value",
    [True, False, "6500", "6.5m", {}, (), [], object(), -1.0, 0.0,
     math.nan, math.inf, -math.inf, 10 ** 1000],
)
def test_untrusted_direct_figured_value_never_firms(value):
    result = resolve_measurement_authority(figured_mm=value)
    assert result.authority_status == AuthorityStatus.BLOCKED.value
    assert result.value_m is None
    assert result.to_dict()["authority_status"] == AuthorityStatus.BLOCKED.value


@pytest.mark.parametrize(
    "value",
    [True, False, "6500", {}, (), [], math.nan, math.inf, -2.0, 0.0, 10 ** 1000],
)
def test_untrusted_scaled_comparison_cannot_confirm_a_valid_figure(value):
    result = resolve_measurement_authority(
        figured_text="6500mm", scaled_mm=value
    )
    assert result.authority_status == AuthorityStatus.BLOCKED.value
    assert result.value_m is None


@pytest.mark.parametrize(
    "value",
    [True, False, "6500", {}, (), [], math.nan, math.inf, -2.0, 0.0, 10 ** 1000],
)
def test_untrusted_scaled_fallback_never_returns_a_quantity(value):
    result = resolve_measurement_authority(scaled_mm=value, scale_reliable=True)
    assert result.authority_status == AuthorityStatus.BLOCKED.value
    assert result.value_m is None


@pytest.mark.parametrize(
    "bad_ratio",
    [True, False, "0.05", None, {}, math.nan, math.inf, -math.inf, -0.01, 10 ** 1000],
)
def test_invalid_conflict_tolerance_cannot_hide_documented_scale_disagreement(bad_ratio):
    result = resolve_measurement_authority(
        figured_mm=6500, scaled_mm=8000,
        max_delta_ratio=bad_ratio,
    )
    assert result.authority_status == AuthorityStatus.BLOCKED.value
    assert result.value_m is None


def test_zero_tolerance_allows_exact_match_but_forces_conflict_review():
    exact = resolve_measurement_authority(
        figured_text="6500", scaled_mm=6500, max_delta_ratio=0.0
    )
    conflict = resolve_measurement_authority(
        figured_text="6500", scaled_mm=6480, max_delta_ratio=0.0
    )
    assert exact.authority_status == AuthorityStatus.FIRM.value
    assert conflict.authority_status == AuthorityStatus.REVIEW_REQUIRED.value


def test_no_firm_zero_area_axis_from_submillimetre_rounding():
    result = resolve_measurement_authority(figured_mm=0.001)
    assert result.value_m is None
    assert result.authority_status == AuthorityStatus.BLOCKED.value


def test_metres_unit_conversion_must_remain_finite():
    with pytest.raises(DimensionParseError, match="finite"):
        parse_figured_dimension_mm("1" + "0" * 307 + "m")


def test_valid_figured_controls_remain_byte_deterministic_and_inputs_unchanged():
    controls = {"figured_mm": 3570.0, "scaled_mm": 3560.0}
    before = dict(controls)
    first = resolve_measurement_authority(**controls)
    second = resolve_measurement_authority(**controls)
    assert controls == before
    assert first.to_dict() == second.to_dict()
    assert first.authority_status == AuthorityStatus.FIRM.value
    assert first.value_m == 3.57
    assert resolve_measurement_authority(figured_mm=2200).value_m == 2.2


@pytest.mark.parametrize(
    "supplied",
    [
        {"figured_mm": True},
        {"figured_mm": "6500"},
        {"figured_mm": math.nan},
        {"figured_text": "unreadable"},
        {"figured_text": ""},
        {"figured_text": "6500", "scaled_mm": 8000.0},
        {},
    ],
)
def test_m5_never_constructs_a_figured_proof_from_blocked_or_absent_measurement(supplied):
    with pytest.raises(MeasurementAuthorityBindingError, match="FIRM"):
        bind_commercial_measurement_authority(_quantity(), **supplied)


def test_m5_requires_original_evidence_identity_not_synthetic_bound_id():
    with pytest.raises(MeasurementAuthorityBindingError, match="evidence"):
        bind_commercial_measurement_authority(
            _quantity(evidence_ids=()), figured_mm=6500.0,
        )


def test_m5_compatible_original_figured_record_retains_its_evidence_id():
    bound = bind_commercial_measurement_authority(
        _quantity(), figured_text="6500mm",
    )
    assert bound.method == "figured_dimension"
    assert bound.figured_dimension_ids == ("dimension_source_1",)
    assert bound.metadata["figured_mm"] == 6500.0
