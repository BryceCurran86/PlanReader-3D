"""Synthetic authority-boundary tests for orthogonal area reconciliation."""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_orthogonal_envelope_evidence import (
    extract_oriented_dimension_observations,
    reconcile_orthogonal_envelope_against_declared_area,
    resolve_orthogonal_envelope_evidence,
)


def _dimension_text(value_m: float) -> str:
    return f"{int(round(value_m * 1000.0)):,}"


def _make_page(horizontal: list[float], vertical: list[float]):
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    for idx, value in enumerate(horizontal):
        page.insert_text((240, 80 + idx * 24), _dimension_text(value), fontsize=10)
    for idx, value in enumerate(vertical):
        page.insert_text((90 + idx * 24, 360), _dimension_text(value), fontsize=10, rotate=90)
    return doc, page


def test_declared_area_can_no_longer_choose_competing_dimension_pairs():
    doc, page = _make_page([12.0, 10.0], [9.6, 8.0])
    try:
        assert resolve_orthogonal_envelope_evidence(
            page, explicit_floor_area_m2=96.0
        ) is None
    finally:
        doc.close()


def test_declared_area_can_no_longer_choose_even_a_unique_dimension_pair():
    doc, page = _make_page([10.0], [8.0])
    try:
        assert resolve_orthogonal_envelope_evidence(
            page, explicit_floor_area_m2=80.0
        ) is None
    finally:
        doc.close()


def test_reconciliation_accepts_only_already_established_dimensions():
    result = reconcile_orthogonal_envelope_against_declared_area(
        length_m=10.0,
        width_m=8.0,
        declared_floor_area_m2=80.0,
    )
    assert result is not None
    assert result.length_m == 10.0
    assert result.width_m == 8.0
    assert result.reconstructed_area_m2 == 80.0
    assert result.status == "agrees_with_declared_area"
    assert result.binding == "unbound"
    assert result.authority == "reconciliation_only"


def test_reconciliation_reports_discrepancy_without_overwriting_geometry():
    result = reconcile_orthogonal_envelope_against_declared_area(
        length_m=10.0,
        width_m=8.0,
        declared_floor_area_m2=95.0,
    )
    assert result is not None
    assert (result.length_m, result.width_m) == (10.0, 8.0)
    assert result.reconstructed_area_m2 == 80.0
    assert result.declared_area_m2 == 95.0
    assert result.delta_m2 == -15.0
    assert result.status == "declared_area_discrepancy"


def test_reconciliation_can_include_independently_established_secondary_width():
    result = reconcile_orthogonal_envelope_against_declared_area(
        length_m=12.0,
        width_m=7.0,
        secondary_width_m=1.5,
        declared_floor_area_m2=102.0,
    )
    assert result is not None
    assert result.reconstructed_area_m2 == 102.0
    assert result.status == "agrees_with_declared_area"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"length_m": 0.0, "width_m": 8.0, "declared_floor_area_m2": 80.0},
        {"length_m": 10.0, "width_m": 0.0, "declared_floor_area_m2": 80.0},
        {"length_m": 10.0, "width_m": 8.0, "declared_floor_area_m2": 0.0},
        {"length_m": 10.0, "width_m": 8.0, "declared_floor_area_m2": float("nan")},
    ],
)
def test_invalid_reconciliation_inputs_fail_closed(kwargs):
    assert reconcile_orthogonal_envelope_against_declared_area(**kwargs) is None


def test_text_direction_observation_remains_source_evidence():
    doc, page = _make_page([12.0], [7.0])
    try:
        observations = extract_oriented_dimension_observations(page)
        by_value = {obs.value_m: obs for obs in observations}
        assert by_value[12.0].orientation == "horizontal"
        assert by_value[7.0].orientation == "vertical"
    finally:
        doc.close()


def test_module_contains_no_benchmark_identity_or_expected_answer_access():
    import pb_orthogonal_envelope_evidence as module

    source = inspect.getsource(module).lower()
    forbidden = [
        "tenders_ke_",
        "ghazi",
        "kstvet",
        "murera",
        "umma",
        "expected_boq_summary",
        "benchmark_rules",
    ]
    for term in forbidden:
        assert term not in source


def test_deprecated_api_cannot_promote_declared_area_to_geometry():
    import pb_orthogonal_envelope_evidence as module

    source = inspect.getsource(module.resolve_orthogonal_envelope_evidence)
    assert "return None" in source
    assert "reconcile_orthogonal_envelope_against_declared_area" in source
