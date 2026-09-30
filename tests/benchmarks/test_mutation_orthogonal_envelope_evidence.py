"""Synthetic tests for reconciliation-only orthogonal envelope evidence."""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_orthogonal_envelope_evidence import (
    extract_oriented_dimension_observations,
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


def test_declared_area_cannot_choose_between_competing_dimension_pairs() -> None:
    doc, page = _make_page([12.0, 10.0], [9.6, 8.0])
    try:
        # Both independent pairs happen to reconcile to the same 96 m2 claim.
        # The caller must choose the physical pair before this resolver runs.
        first = resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=12.0,
            candidate_width_m=8.0,
            declared_floor_area_m2=96.0,
        )
        second = resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=10.0,
            candidate_width_m=9.6,
            declared_floor_area_m2=96.0,
        )
        assert first is not None and second is not None
        assert first.geometry_authority is False
        assert second.geometry_authority is False
        assert (first.length_m, first.width_m) == pytest.approx((12.0, 8.0))
        assert (second.length_m, second.width_m) == pytest.approx((10.0, 9.6))
    finally:
        doc.close()


def test_reconciliation_requires_independently_supplied_geometry() -> None:
    doc, page = _make_page([10.0], [8.0])
    try:
        with pytest.raises(TypeError):
            resolve_orthogonal_envelope_evidence(  # type: ignore[call-arg]
                page, declared_floor_area_m2=80.0
            )
    finally:
        doc.close()


def test_declared_area_mismatch_does_not_mutate_or_replace_geometry() -> None:
    doc, page = _make_page([10.0], [8.0])
    try:
        assert resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=10.0,
            candidate_width_m=8.0,
            declared_floor_area_m2=95.0,
        ) is None
    finally:
        doc.close()


def test_candidate_dimensions_must_exist_on_opposite_source_axes() -> None:
    doc, page = _make_page([10.0, 8.0], [7.0])
    try:
        assert resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=10.0,
            candidate_width_m=8.0,
            declared_floor_area_m2=80.0,
        ) is None
    finally:
        doc.close()


def test_supplied_secondary_width_is_reconciled_but_never_inferred_from_area() -> None:
    doc, page = _make_page([12.0], [7.0])
    try:
        area = 12.0 * 7.0 + 12.0 * 1.5
        with_secondary = resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=12.0,
            candidate_width_m=7.0,
            declared_floor_area_m2=area,
            secondary_width_m=1.5,
        )
        without_secondary = resolve_orthogonal_envelope_evidence(
            page,
            candidate_length_m=12.0,
            candidate_width_m=7.0,
            declared_floor_area_m2=area,
        )
        assert with_secondary is not None
        assert with_secondary.secondary_width_m == pytest.approx(1.5)
        assert without_secondary is None
    finally:
        doc.close()


def test_text_direction_remains_source_evidence() -> None:
    doc, page = _make_page([12.0], [7.0])
    try:
        observations = extract_oriented_dimension_observations(page)
        by_value = {obs.value_m: obs for obs in observations}
        assert by_value[12.0].orientation == "horizontal"
        assert by_value[7.0].orientation == "vertical"
    finally:
        doc.close()


def test_input_text_translation_does_not_change_reconciliation() -> None:
    doc_a, page_a = _make_page([10.0], [8.0])
    doc_b = fitz.open()
    page_b = doc_b.new_page(width=800, height=600)
    page_b.insert_text((500, 300), _dimension_text(10.0), fontsize=10)
    page_b.insert_text((450, 500), _dimension_text(8.0), fontsize=10, rotate=90)
    try:
        a = resolve_orthogonal_envelope_evidence(
            page_a, candidate_length_m=10.0, candidate_width_m=8.0, declared_floor_area_m2=80.0
        )
        b = resolve_orthogonal_envelope_evidence(
            page_b, candidate_length_m=10.0, candidate_width_m=8.0, declared_floor_area_m2=80.0
        )
        assert a is not None and b is not None
        assert (a.length_m, a.width_m, a.corroborated_area_m2) == (
            b.length_m, b.width_m, b.corroborated_area_m2
        )
    finally:
        doc_a.close()
        doc_b.close()


def test_module_contains_no_benchmark_identity_or_expected_answer_access() -> None:
    import pb_orthogonal_envelope_evidence as module

    source = inspect.getsource(module).lower()
    for term in (
        "tenders_ke_", "ghazi", "kstvet", "murera", "umma",
        "expected_boq_summary", "benchmark_rules",
    ):
        assert term not in source
