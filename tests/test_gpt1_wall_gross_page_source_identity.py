"""Q03 physical gross wall m² requires exact typed page and viewport source."""
from dataclasses import replace

import pytest

from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from tests.test_wall_gross_area_quantity import _ctx, _length, _height


def _gross(length, height):
    return build_gross_wall_area_quantity(
        wall_id="WALL-1", wall_length=length, wall_height=height, context=_ctx(),
    )


def test_actual_measured_4m_x_3m_wall_retains_exact_gross_12m2():
    gross=_gross(_length(),_height())
    assert not gross.abstained
    assert gross.value==12.0


@pytest.mark.parametrize("bad_page", [True, 1.0, "1", None, 0, -1, 2])
@pytest.mark.parametrize("part", ["length","height"])
def test_wall_gross_refuses_cast_or_wrong_source_page(bad_page,part):
    length,height=_length(),_height()
    if part=="length":
        length=replace(length,metadata={**length.metadata,"page_no":bad_page})
    else:
        height=replace(height,metadata={**height.metadata,"page_no":bad_page})
    result=_gross(length,height)
    assert result.abstained
    assert result.value is None
    assert any("page" in reason for reason in result.blocking_reasons)


@pytest.mark.parametrize("bad_viewport", [" VP-1", True, 1, "", None])
def test_wall_gross_rejects_alias_source_viewport(bad_viewport):
    height=_height()
    height=replace(height,metadata={**height.metadata,"viewport_id":bad_viewport})
    gross=_gross(_length(),height)
    assert gross.abstained
    assert gross.value is None
    assert "wall_height_viewport_source_invalid" in gross.blocking_reasons
