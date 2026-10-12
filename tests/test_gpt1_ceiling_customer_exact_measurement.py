"""Exact legacy ceiling customer projection authority cannot repair source inputs."""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    _measurement_authority, project_live_ceiling_area_customer_rows,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from tests.test_live_ceiling_area_quantity_publication import _result


def _quantity(authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value):
    from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
    original = publish_live_ceiling_area_quantities(_result())[0]
    return replace(original, authority=authority)


def test_source_authenticated_ceiling_customer_projection_preserves_real_result():
    rows = project_live_ceiling_area_customer_rows(
        _result(), workspace_id=7, project_id="source-project",
    )
    assert len(rows) == 1
    assert rows[0]["measurement_method"] == "figured_dimension"


@pytest.mark.parametrize("source_ids", [
    ("dim-h", "dim-v", "dim-h"), ("dim-h", "dim-h"), ("dim-h",),
    ("dim-h", " dim-v"), ("dim-h", True), ["dim-h", ["nested"]],
    "dim-h,dim-v", None, {},
])
def test_ceiling_customer_cannot_repair_figured_source_pair(source_ids):
    quantity = _quantity()
    tampered = replace(quantity, metadata={
        **dict(quantity.metadata), "figured_dimension_ids": source_ids,
    })
    assert _measurement_authority(tampered) is None


def test_exact_two_original_ceiling_axes_remain_commercially_authentic():
    quantity = _quantity()
    clean = replace(quantity, metadata={
        **dict(quantity.metadata), "figured_dimension_ids": ["dim-v", "dim-h"],
    })
    result = _measurement_authority(clean)
    assert result.method == "figured_dimension"
    assert result.figured_dimension_ids == ("dim-h", "dim-v")


@pytest.mark.parametrize("bad", [
    {"resolved_scale_id": True},
    {"resolved_scale_id": " scale-1"},
    {"resolved_scale_id": ""},
    {"scale_status": "conflicted"},
    {"scale_status": "provisional"},
    {"scale_status": True},
    {"scale_conflicts": ("page10-conflict",)},
    {"scale_conflicts": "lost-conflict"},
    {"scale_conflicts": None},
])
def test_ceiling_customer_cannot_invent_clean_scale_record(bad):
    quantity = _quantity(authority=MeasurementAuthorityType.PDF_SCALED.value)
    source_meta = dict(quantity.metadata)
    source_meta.update({
        "resolved_scale_id": "physical-scale-1",
        "scale_status": "resolved", "scale_conflicts": (),
    })
    source_meta.update(bad)
    tampered = replace(quantity, metadata=source_meta)
    assert _measurement_authority(tampered) is None


def test_scaled_ceiling_customer_keeps_exact_physical_source_scale():
    quantity = _quantity(authority=MeasurementAuthorityType.PDF_SCALED.value)
    verified = replace(quantity, metadata={
        **dict(quantity.metadata),
        "resolved_scale_id": "physical-scale-1",
        "scale_status": "resolved", "scale_conflicts": (),
    })
    result = _measurement_authority(verified)
    assert result.method == "scaled_geometry"
    assert result.resolved_scale_id == "physical-scale-1"
