"""Q01 final floor finish customer authority cannot normalize scale conflicts."""
from dataclasses import replace
import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_floor_finish_customer_projection import _measurement_authority
from pb_quantity_takeoff_adapter import MissingCommercialAuthorityError
from tests.test_live_floor_finish_area_source_closed_export import _quantity


def _scaled():
    original = _quantity()
    return replace(original, authority=MeasurementAuthorityType.PDF_SCALED.value,
                   metadata={**dict(original.metadata),
                       "resolved_scale_id": "physical-scale-1",
                       "scale_status": "resolved", "scale_conflicts": ()})


def test_authenticated_metric_finish_still_accepts_original_scale():
    authority = _measurement_authority(_scaled())
    assert authority.method == "scaled_geometry"
    assert authority.resolved_scale_id == "physical-scale-1"
    assert authority.scale_conflicts == ()


@pytest.mark.parametrize("overrides", [
    {"resolved_scale_id": True}, {"resolved_scale_id": 12},
    {"resolved_scale_id": " scale-1 "}, {"resolved_scale_id": ""},
    {"scale_status": "provisional"}, {"scale_status": "conflicted"},
    {"scale_status": True}, {"scale_conflicts": ["source-revision-conflict"]},
    {"scale_conflicts": "source-revision-conflict"},
    {"scale_conflicts": None}, {"scale_conflicts": 1},
])
def test_replayed_floor_finish_cannot_cast_source_scale_to_firm(overrides):
    clean = _scaled()
    replay = replace(clean, metadata={**dict(clean.metadata), **overrides})
    with pytest.raises(MissingCommercialAuthorityError, match="original resolved"):
        _measurement_authority(replay)


def test_documented_original_floor_finish_keeps_two_source_axes():
    authority = _measurement_authority(_quantity())
    assert authority.method == "figured_dimension"
    assert authority.figured_dimension_ids == ("dim-h-source", "dim-v-source")
