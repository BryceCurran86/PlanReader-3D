"""Q03 malformed lower-dimensional wall receipts remain auditable ABSTAIN."""
from dataclasses import replace

import pytest

from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from tests.test_wall_gross_area_quantity import _ctx, _length, _height


@pytest.mark.parametrize("bad", [
    None, "ev-wall", 10, True, [["nested"]], [True, "ev-length"], (" ev-length",),
])
@pytest.mark.parametrize("damaged", ["length", "height"])
def test_corrupt_wall_source_receipts_never_crash_or_sign_gross_area(bad, damaged):
    length, height = _length(), _height()
    if damaged == "length":
        length = replace(length, evidence_ids=bad)
    else:
        height = replace(height, evidence_ids=bad)
    blocked = build_gross_wall_area_quantity(
        wall_id="WALL-1", wall_length=length, wall_height=height, context=_ctx()
    )
    assert blocked.abstained is True
    assert blocked.value is None
    assert f"wall_{damaged}_source_receipts_invalid" in blocked.blocking_reasons
    assert all(type(value) is str and value == value.strip()
               for value in blocked.evidence_ids)
    assert blocked.status == "blocked"


def test_verified_wall_length_and_height_still_publish_12m2_gross():
    valid = build_gross_wall_area_quantity(
        wall_id="WALL-1", wall_length=_length(), wall_height=_height(), context=_ctx()
    )
    assert not valid.abstained
    assert valid.value == 12.0
    assert set(valid.evidence_ids) == {"ev-wall_length", "ev-wall_height"}
