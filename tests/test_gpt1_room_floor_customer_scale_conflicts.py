"""Q01 / Q05 customer projection keeps original scale status and conflicts."""
from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_floor_area_customer_projection import _measurement_authority as floor_auth
from pb_live_room_area_customer_projection import _scaled_measurement_authority as room_auth
from tests.test_live_floor_area_quantity_publication_integrity import _source_area


def _scaled():
    source=_source_area()
    return replace(
        source, authority=MeasurementAuthorityType.PDF_SCALED.value,
        metadata={
            **dict(source.metadata), "resolved_scale_id":"physical-scale-1",
            "scale_status":"resolved", "scale_conflicts": (),
        },
    )


@pytest.mark.parametrize("authority", [room_auth, floor_auth])
def test_original_resolved_physical_scale_still_supports_customer_measurement(authority):
    result=authority(_scaled())
    assert result.method=="scaled_geometry"
    assert result.resolved_scale_id=="physical-scale-1"
    assert result.scale_status=="resolved"
    assert result.scale_conflicts==()


@pytest.mark.parametrize("updates", [
    {"resolved_scale_id":True},
    {"resolved_scale_id":11},
    {"resolved_scale_id":"physical-scale-1 "},
    {"resolved_scale_id":""},
    {"scale_status":"provisional"},
    {"scale_status":"conflicted"},
    {"scale_status":"unresolved"},
    {"scale_status":True},
    {"scale_conflicts":("other physical source",)},
    {"scale_conflicts":"other physical source"},
    {"scale_conflicts":None},
    {"scale_conflicts":3},
])
@pytest.mark.parametrize("authority", [room_auth, floor_auth])
def test_original_room_and_floor_customer_cannot_normalize_source_scale_conflicts(
    updates, authority,
):
    source=_scaled()
    tampered=replace(source,metadata={**dict(source.metadata),**updates})
    assert authority(tampered) is None
