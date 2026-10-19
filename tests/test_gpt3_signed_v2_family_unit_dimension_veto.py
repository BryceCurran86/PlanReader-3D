"""Cannot score count quantities as floor square metres or vice versa."""
from __future__ import annotations

import pytest

from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity as veto,
)


def apply(*, family, semantic, unit, trade):
    item = {"item_id": "item-one", "denominator_eligible": True,
            "trade_category": trade}
    source = {
        "object_identity_refs": ["source-physical-1"], "family": family,
        "semantic_key": semantic, "unit": unit,
    }
    mapped = {
        "benchmark_item_id": "item-one",
        "production_object_identity_refs": ["source-physical-1"],
        "production_family": family,
    }
    return veto(verified_items=[item], sealed_quantities=[source],
                identity_bindings=[mapped])


@pytest.mark.parametrize(("family", "semantic", "unit", "trade"), [
    ("floor_area", "floor.area", "m²", "flooring"),
    ("floor_finish_area", "tiling.floor", "sqm", "tiling"),
    ("ceiling_area", "ceiling.area", "m2", "ceilings"),
    ("opening_area", "door_area:qualified-1", "m²", "doors"),
    ("opening_area", "window_area:qualified-1", "m2", "windows"),
    ("opening_count", "door_count:qualified-1", "ea", "doors"),
    ("opening_count", "window_count:qualified-1", "count", "windows"),
])
def test_source_owned_dimensional_unit_can_map_to_compatible_trade(
    family, semantic, unit, trade,
):
    apply(family=family, semantic=semantic, unit=unit, trade=trade)


@pytest.mark.parametrize(("family", "semantic", "unit", "trade"), [
    ("floor_area", "floor.area", "ea", "flooring"),
    ("floor_finish_area", "tile.area", "count", "tiling"),
    ("ceiling_area", "ceiling.area", "m", "ceilings"),
    ("opening_area", "door_area:source-id", "ea", "doors"),
    ("opening_count", "door_count:source-id", "m2", "doors"),
    ("opening_area", "window_area:source-id", "m3", "windows"),
])
def test_incompatible_count_area_volume_units_fail_before_benchmark_score(
    family, semantic, unit, trade,
):
    with pytest.raises(ValueError, match="unit disagrees"):
        apply(family=family, semantic=semantic, unit=unit, trade=trade)


@pytest.mark.parametrize("unit", [None, True, 1, [], " m2", "m2 ", "m³"])
def test_noncanonical_signed_source_unit_cannot_be_silent_trade_reclassification(unit):
    if unit is None:
        # Missing unit is separately rejected by the verified typed V1
        # importer, rather than this source-neutral semantic-only helper.
        apply(family="opening_area", semantic="door_area:source-id",
              unit=None, trade="doors")
    else:
        with pytest.raises(ValueError, match="unit disagrees"):
            apply(family="opening_area", semantic="door_area:source-id",
                  unit=unit, trade="doors")
