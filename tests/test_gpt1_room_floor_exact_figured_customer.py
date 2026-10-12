"""Q01/Q05 final room/floor figured customer must retain exact original source IDs."""
from dataclasses import replace

import pytest

from pb_live_floor_area_customer_projection import _measurement_authority as floor_auth
from pb_live_room_area_customer_projection import _figured_measurement_authority as room_auth
from tests.test_live_floor_area_quantity_publication_integrity import _source_area


def _candidate(ids):
    original=_source_area()
    return replace(original,metadata={
        **dict(original.metadata),"figured_dimension_ids":ids,
    })


@pytest.mark.parametrize("authority",[floor_auth,room_auth])
def test_original_figured_room_and_floor_axes_retained_unmodified(authority):
    measurement=authority(_candidate(("source-dim-h","source-dim-v")))
    assert measurement.method=="figured_dimension"
    assert measurement.figured_dimension_ids==("source-dim-h","source-dim-v")


@pytest.mark.parametrize("ids",[
    ("source-dim-h ","source-dim-v"),
    (" source-dim-h","source-dim-v"),
    ("source-dim-h"," source-dim-v "),
    ("source-dim-h","source-dim-h"),
    ("source-dim-h",True),
    ("source-dim-h","source-dim-v","source-dim-v"),
])
@pytest.mark.parametrize("authority",[floor_auth,room_auth])
def test_original_figured_room_and_floor_cannot_normalize_source_axes(authority,ids):
    assert authority(_candidate(ids)) is None
