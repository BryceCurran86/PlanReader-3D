"""Vinyl rooms were silently omitted from legacy trade takeoff."""
import pytest
from pb_flooring_trade_authority import (
    FlooringSpaceSpec,calculate_vinyl_flooring_items,
    generate_workspace_flooring_takeoff,
)


def _spec(finish="vinyl",area=13.27):
    return FlooringSpaceSpec(
        space_id="synthetic-room",room_name="Food preparation",floor_finish=finish,
        area_m2=area,perimeter_lm=15.0,
    )


@pytest.mark.parametrize("finish",["vinyl","vinyl_sheet","vinyl_plank","resilient"])
def test_vinyl_room_no_longer_silently_disappears_from_workspace_takeoff(finish):
    src=_spec(finish)
    rows=calculate_vinyl_flooring_items(src)
    assert len(rows)==1
    assert rows[0].quantity==13.27
    assert rows[0].unit=="m²"
    assert rows[0].quantity_status=="Provisional"
    assert rows[0].inclusion_status=="PROVISIONAL"
    mapped=generate_workspace_flooring_takeoff([src],8,"2026-10-19T00:00:00")
    assert len(mapped)==1
    assert mapped[0]["quantity"]==13.27


@pytest.mark.parametrize("bad",[True,False,"13",float("nan"),float("inf"),10**400,0,-1])
def test_invalid_or_coerced_vinyl_area_does_not_mint_quantity(bad):
    assert calculate_vinyl_flooring_items(_spec(area=bad))==[]


def test_tiling_is_not_falsely_classified_as_vinyl():
    assert calculate_vinyl_flooring_items(_spec("tiles"))==[]


def test_unknown_sheet_direction_doorway_threshold_and_coving_are_not_assumed():
    result=calculate_vinyl_flooring_items(_spec("vinyl_sheet"))
    assert len(result)==1
    assert result[0].row_role=="floor_area"
    assert "coves" in result[0].notes
    assert "under partitions" in result[0].notes
