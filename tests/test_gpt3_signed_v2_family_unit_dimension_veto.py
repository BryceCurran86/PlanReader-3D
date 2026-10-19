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
    ("opening_count", "window_count:qualified-1", "nr", "windows"),
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
    ("opening_count", "door_count:source-id", "count", "doors"),
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


@pytest.mark.parametrize("value", [0, -1, 0.5, 1.01, True, False,
                                    float("nan"), float("inf"), "1"])
def test_mapped_source_opening_count_never_becomes_fractional_or_default_one(value):
    item = {"item_id": "item", "denominator_eligible": True,
            "trade_category": "windows"}
    source = {"object_identity_refs": ["original-window"],
              "family": "opening_count", "semantic_key": "window_count:source",
              "unit": "nr", "value": value, "abstained": False}
    binding = {"benchmark_item_id": "item", "production_family": "opening_count",
               "production_object_identity_refs": ["original-window"]}
    with pytest.raises(ValueError, match="positive whole number"):
        veto(verified_items=[item], sealed_quantities=[source],
             identity_bindings=[binding])


def test_mapped_group_of_three_source_issued_openings_may_have_count_three():
    item = {"item_id": "item", "denominator_eligible": True,
            "trade_category": "doors"}
    source = {"object_identity_refs": ["original-door-group"],
              "family": "opening_count", "semantic_key": "door_count:source",
              "unit": "nr", "value": 3, "abstained": False}
    binding = {"benchmark_item_id": "item", "production_family": "opening_count",
               "production_object_identity_refs": ["original-door-group"]}
    veto(verified_items=[item], sealed_quantities=[source],
         identity_bindings=[binding])


def test_one_source_owned_physical_door_can_separately_map_area_and_count():
    """Previously rejected because area/count shared one canonical physical ID."""
    original_refs = ["lot16:door:opening-101"]
    items = [
        {"item_id": "door-area", "denominator_eligible": True, "trade_category": "doors"},
        {"item_id": "door-count", "denominator_eligible": True, "trade_category": "doors"},
    ]
    quantities = [
        {"object_identity_refs": original_refs, "family": "opening_area",
         "semantic_key": "door_area:lot16-opening-101", "unit": "m2",
         "value": 1.8, "abstained": False},
        {"object_identity_refs": original_refs, "family": "opening_count",
         "semantic_key": "door_count:lot16-opening-101", "unit": "nr",
         "value": 1, "abstained": False},
    ]
    bindings = [
        {"benchmark_item_id": "door-area", "production_object_identity_refs": original_refs,
         "production_family": "opening_area"},
        {"benchmark_item_id": "door-count", "production_object_identity_refs": original_refs,
         "production_family": "opening_count"},
    ]
    veto(verified_items=items, sealed_quantities=quantities,
         identity_bindings=bindings)


def test_different_family_same_physical_refs_cannot_transmute_window_to_door():
    refs = ["shared-original-open"]
    source = [
        {"object_identity_refs": refs, "family": "opening_area",
         "semantic_key": "window_area:owner-native", "unit": "m2"},
        {"object_identity_refs": refs, "family": "opening_count",
         "semantic_key": "door_count:owner-native", "unit": "nr", "value": 1},
    ]
    with pytest.raises(ValueError, match="kind disagrees"):
        veto(
            verified_items=[{"item_id": "door-area", "denominator_eligible": True,
                             "trade_category": "doors"}],
            sealed_quantities=source,
            identity_bindings=[{
                "benchmark_item_id": "door-area",
                "production_family": "opening_area",
                "production_object_identity_refs": refs,
            }],
        )


def test_mapped_production_without_source_owned_family_cannot_claim_opening_area():
    refs = ["original-shared-opening"]
    with pytest.raises(ValueError, match="explicit original production family"):
        veto(
            verified_items=[{"item_id": "area", "denominator_eligible": True,
                             "trade_category": "doors"}],
            sealed_quantities=[{
                "object_identity_refs": refs, "family": "opening_area",
                "semantic_key": "door_area:owner-id", "unit": "m2",
            }],
            identity_bindings=[{
                "benchmark_item_id": "area",
                "production_family": None,
                "production_object_identity_refs": refs,
            }],
        )
