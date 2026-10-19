"""Independent source-owned opening dimensions in metres, without guessing axes."""
from dataclasses import replace

import pytest

from pb_live_opening_metric_dimensions_quantity_publication import (
    publish_live_opening_dimension_quantities,
)
from tests.test_live_opening_area_quantity_publication import _opening, _composition


def _figured_with_explicit_axes():
    original = _opening(area_m2=2.172)
    return replace(
        original,
        width_m=1.2,
        height_m=1.81,
        width_record_id="original-width-1",
        height_record_id="original-height-1",
        evidence_ids=(*original.evidence_ids,
                      "original-width-1", "original-height-1"),
    )


def _source_frame_schedule():
    original = _opening(
        area_m2=2.16,
        area_basis="authenticated_frame_schedule",
        figured_area_record_id=None,
    )
    return replace(
        original,
        schedule_binding_record_id="original-outer-frame-schedule-1",
        schedule_declared_width_mm=1200,
        schedule_declared_height_mm=1800,
        schedule_row_dimension_basis="frame",
        schedule_row_basis_source="original frame width",
        evidence_ids=(*original.evidence_ids,
                      "original-outer-frame-schedule-1"),
    )


@pytest.mark.parametrize("original,expected", [
    (_figured_with_explicit_axes(), {"opening_width": 1.2, "opening_height": 1.81}),
    (_source_frame_schedule(), {"opening_width": 1.2, "opening_height": 1.8}),
])
def test_original_source_qualified_opening_dimensions_become_real_metres(original, expected):
    claim = _composition(original)
    quantities = claim.physical_opening_dimension_quantities
    assert {q.family: q.value for q in quantities} == expected
    assert all(q.unit == "lm" and q.status == "corroborated" for q in quantities)
    assert all(q.input_entity_ids == (original.physical_opening_id,) for q in quantities)
    assert all(q.metadata["commercial_projection_allowed"] is False for q in quantities)
    assert all(q.metadata["source_area_quantity_id"] for q in quantities)
    assert quantities == publish_live_opening_dimension_quantities(claim)


def test_authentic_figured_area_without_axis_orientation_stays_area_only():
    assert publish_live_opening_dimension_quantities(_composition(_opening())) == ()


@pytest.mark.parametrize("bad", [
    {"width_record_id": None},
    {"height_record_id": None},
    {"width_record_id": "original-height-1"},
    {"width_m": True},
    {"width_m": "1.2"},
    {"height_m": float("nan")},
    {"width_m": 1.3},
    {"area_m2": 2.40},
])
def test_unproved_or_conflicting_figured_axes_are_never_inferred(bad):
    original = replace(_figured_with_explicit_axes(), **bad)
    assert publish_live_opening_dimension_quantities(_composition(original)) == ()


@pytest.mark.parametrize("bad", [
    {"schedule_row_dimension_basis": "leaf"},
    {"schedule_binding_record_id": None},
    {"schedule_declared_width_mm": "1200"},
    {"schedule_declared_width_mm": True},
    {"schedule_declared_width_mm": float("inf")},
    {"schedule_declared_height_mm": 0},
    {"schedule_declared_height_mm": 2100},
])
def test_opening_leaf_size_or_invalid_frame_dimension_never_mints_length(bad):
    claim = _composition(replace(_source_frame_schedule(), **bad))
    assert publish_live_opening_dimension_quantities(claim) == ()


def test_missing_axes_on_one_opening_do_not_hide_other_independent_source_axes():
    no_axes = _opening(canonical_id="opening-with-figured-area-only")
    with_axes = replace(
        _source_frame_schedule(),
        canonical_opening_id="opening-with-source-axes",
        physical_opening_id="opening-with-source-axes",
        evidence_ids=tuple(
            "opening-with-source-axes" if x == "opening-1" else x
            for x in _source_frame_schedule().evidence_ids
        ),
    )
    published = publish_live_opening_dimension_quantities(
        _composition(no_axes, with_axes),
    )
    assert len(published) == 2
    assert all(q.input_entity_ids == ("opening-with-source-axes",) for q in published)
