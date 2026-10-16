"""GPT1: numeric-integrity and provenance-negative tests for the existing M5 authority seam.

These tests use synthetic quantities only. They never inspect benchmark truth,
issue source-based promotions, or mutate customer/signed output.
"""
from __future__ import annotations

import math
from fractions import Fraction
from decimal import Decimal

import pytest

from pb_figured_dimension_authority import (
    DimensionParseError,
    parse_figured_dimension_mm,
    resolve_measurement_authority,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, ScaleCalibration
from pb_migration_contracts import QuantityEvidence
from pb_page_scale_calibration_authority import ScaleSourceType, ScaleCalibrationStatus
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
        input_entity_ids=("span_entity_1",),
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


@pytest.mark.parametrize("numeric", [Fraction(13, 2), Fraction(3570, 1)])
def test_real_numeric_scalar_dimensions_preserve_valid_firm_measurements(numeric):
    result = resolve_measurement_authority(figured_mm=numeric)
    assert result.authority_status == AuthorityStatus.FIRM.value
    assert result.value_m == round(float(numeric) / 1000.0, 4)
    scaled = resolve_measurement_authority(scaled_mm=numeric, scale_reliable=True)
    assert scaled.authority_status == AuthorityStatus.PROVISIONAL.value


def test_numpy_real_scalar_supported_without_bool_false_positive():
    np = pytest.importorskip("numpy")
    for numeric in (np.float64(6500.0), np.float32(6500.0), np.int64(6500)):
        figured = resolve_measurement_authority(figured_mm=numeric)
        scaled = resolve_measurement_authority(scaled_mm=numeric, scale_reliable=True)
        verified = resolve_measurement_authority(
            figured_mm=6500.0, scaled_mm=numeric, max_delta_ratio=np.float64(0.05)
        )
        assert figured.authority_status == AuthorityStatus.FIRM.value
        assert figured.value_m == 6.5
        assert scaled.authority_status == AuthorityStatus.PROVISIONAL.value
        assert verified.authority_status == AuthorityStatus.FIRM.value


def test_tolerance_boundary_retains_original_rounded_delta_verdict_and_notes():
    # Previously accepted value: the published 2dp delta is exactly 5 percent.
    at_edge = resolve_measurement_authority(figured_mm=6500.0, scaled_mm=6174.996)
    over_edge = resolve_measurement_authority(figured_mm=6500.0, scaled_mm=6174.994)
    assert at_edge.authority_status == AuthorityStatus.FIRM.value
    assert at_edge.scaled_delta_mm == 325.0
    assert at_edge.notes == "Figured dimension precedence applied (scaled delta: 325.0mm)"
    assert over_edge.authority_status == AuthorityStatus.REVIEW_REQUIRED.value
    assert over_edge.scaled_delta_mm == 325.01


def test_finite_decimal_scaled_and_figured_inputs_remain_authoritative():
    figure = resolve_measurement_authority(figured_mm=Decimal("6500"))
    scaled = resolve_measurement_authority(scaled_mm=Decimal("6500"), scale_reliable=True)
    same = resolve_measurement_authority(
        figured_mm=Decimal("6500"), scaled_mm=Decimal("6500"),
        max_delta_ratio=Decimal("0.05"),
    )
    assert figure.value_m == 6.5 and figure.authority_status == AuthorityStatus.FIRM.value
    assert scaled.value_m == 6.5 and scaled.authority_status == AuthorityStatus.PROVISIONAL.value
    assert same.value_m == 6.5 and same.authority_status == AuthorityStatus.FIRM.value


@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_nonfinite_decimals_fail_closed_without_parser_exception(bad):
    assert resolve_measurement_authority(figured_mm=bad).authority_status == AuthorityStatus.BLOCKED.value
    assert resolve_measurement_authority(scaled_mm=bad).authority_status == AuthorityStatus.BLOCKED.value
    assert resolve_measurement_authority(figured_mm=6500, max_delta_ratio=bad).authority_status == AuthorityStatus.BLOCKED.value


def _verified_scale_bar():
    return ScaleCalibration(
        page_no=1,
        ratio_str="1:100",
        px_per_m=28.346,
        method="SCALE_BAR",
        is_verified=True,
        confidence=1.0,
        source_type=ScaleSourceType.SCALE_BAR.value,
        status=ScaleCalibrationStatus.VALID.value,
    )


def _scaled_quantity():
    return QuantityEvidence(
        quantity_id="test_source_scaled",
        family="length",
        semantic_key="wall_span",
        value=1.5,
        unit="m",
        input_entity_ids=("wall_1",),
        evidence_ids=("original_wall_source_1",),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        status="firm",
        confidence=1.0,
    )


@pytest.mark.parametrize(
    "bad", [None, True, False, "1500", {}, [], 0, -1, float("nan"),
            float("inf"), -float("inf"), 10 ** 1000, Decimal("NaN"), 0.001],
)
def test_m5_scaled_only_rejects_invalid_or_unusable_metric_even_with_firm_scale(bad):
    with pytest.raises(MeasurementAuthorityBindingError, match="finite positive measured value"):
        bind_commercial_measurement_authority(
            _scaled_quantity(),
            scaled_mm=bad,
            scale_calibration=_verified_scale_bar(),
        )


def test_m5_scaled_only_requires_existing_firm_scale_and_valid_metric():
    bound = bind_commercial_measurement_authority(
        _scaled_quantity(),
        scaled_mm=1500.0,
        scale_calibration=_verified_scale_bar(),
        trusted_scale_id="trusted_source_bar_1",
    )
    assert bound.method == "scaled_geometry"
    assert bound.resolved_scale_id == "trusted_source_bar_1"
    assert bound.scale_status == "resolved"


def test_m5_scaled_quantity_rejects_explicitly_malformed_figured_competitor():
    with pytest.raises(MeasurementAuthorityBindingError, match="FIRM"):
        bind_commercial_measurement_authority(
            _scaled_quantity(),
            scaled_mm=1500.0,
            figured_text="",
            scale_calibration=_verified_scale_bar(),
        )


def test_m5_valid_non_builtin_real_scaled_metric_is_accepted():
    bound = bind_commercial_measurement_authority(
        _scaled_quantity(),
        scaled_mm=Decimal("1500.0"),
        scale_calibration=_verified_scale_bar(),
    )
    assert bound.method == "scaled_geometry"
