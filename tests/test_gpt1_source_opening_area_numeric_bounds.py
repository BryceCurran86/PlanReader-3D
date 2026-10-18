"""A source opening label must have two typed finite, in-range axes."""
import pytest
from pb_opening_label_dimension_authority import (
    ParsedOpeningLabel, _area_from_dimension_values, parse_opening_label_dimensions,
)


def test_original_two_axis_source_area_retains_order_invariant_result():
    assert _area_from_dimension_values((1200,1810)) == pytest.approx(2.172)
    assert _area_from_dimension_values((1810,1200)) == pytest.approx(2.172)
    assert _area_from_dimension_values([2100,4800]) == pytest.approx(10.08)
    assert parse_opening_label_dimensions("1200 - 1810 ASW").area_m2 == pytest.approx(2.172)


@pytest.mark.parametrize("axes", [
    (), (1200,), (1200,1810,300), (1200,True),
    ("1200",1810), (1200,None), (1200,float("nan")),
    (float("inf"),1800), (1200,float("-inf")),
    (0,2100), (-1200,2100), (399,2100), (6001,2100),
])
def test_invalid_or_missing_second_axis_never_becomes_area(axes):
    assert _area_from_dimension_values(axes) is None


def test_forged_parsed_opening_does_not_bypass_physical_metric_bounds():
    parsed = ParsedOpeningLabel(
        raw_text="bad",dimension_tokens=("1000","2100"),
        dimension_values_mm=(float("nan"),2100),
        suffix_text="ASW",semantic_kind=None,
        compact_hundreds_present=False,compact_hundreds_used=False,
    )
    assert parsed.area_m2 is None


def test_one_number_opening_does_not_gain_default_count_or_height():
    label=parse_opening_label_dimensions("870 CS")
    assert label is not None and label.area_m2 is None
