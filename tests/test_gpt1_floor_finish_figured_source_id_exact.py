"""Q01 original figured floor finish text-source dimensions never normalize whitespace."""
from dataclasses import replace

import pytest

from pb_live_floor_finish_customer_projection import _measurement_authority
from pb_quantity_takeoff_adapter import MissingCommercialAuthorityError
from tests.test_live_floor_finish_area_source_closed_export import _quantity


def test_original_two_figured_finish_dimensions_remain_positive():
    actual=_measurement_authority(_quantity())
    assert actual.method=="figured_dimension"
    assert actual.figured_dimension_ids==("dim-h-source","dim-v-source")


@pytest.mark.parametrize("ids", [
    ("dim-h-source ","dim-v-source"),
    (" dim-h-source","dim-v-source"),
    ("dim-h-source","dim-v-source "),
    ("dim-h-source","dim-h-source"),
    ("dim-h-source","dim-v-source","dim-v-source"),
    ("dim-h-source",True),
])
def test_original_figured_finish_receipts_must_be_exact_source_ids(ids):
    original=_quantity()
    forged=replace(original,metadata={
        **dict(original.metadata),
        "figured_dimension_ids":ids,
    })
    with pytest.raises(MissingCommercialAuthorityError,match="distinct source dimensions"):
        _measurement_authority(forged)
