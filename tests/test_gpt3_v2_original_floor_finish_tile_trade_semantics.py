"""Frozen V2 may only award tiling to an already signed original TILE finish."""
from __future__ import annotations

import pytest

from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)


def _check(semantic_key, *, trade="tiling", abstained=False, claimed_refs=None):
    # The actual CrossViewFloorFinishProducer signs its canonical floor ID
    # into BOTH the material semantic key and the source object identities.
    floor = "canonical-floor-1"
    source_refs = [floor] if claimed_refs is None else list(claimed_refs)
    quantity = {
        "family": "floor_finish_area",
        "semantic_key": semantic_key,
        "object_identity_refs": source_refs,
        "unit": "m2", "value": None if abstained else 9.05352,
        "abstained": abstained,
    }
    item = {
        "item_id": "frozen-floor-finish-item",
        "denominator_eligible": True,
        "trade_category": trade,
    }
    link = {
        "benchmark_item_id": item["item_id"],
        "production_family": "floor_finish_area",
        "production_object_identity_refs": source_refs,
    }
    return require_signed_v2_family_trade_integrity(
        verified_items=[item],
        sealed_quantities=[quantity],
        identity_bindings=[link],
    )


@pytest.mark.parametrize("key", [
    "floor_finish_area:canonical-floor-1:FT2:tile",
    "floor_finish_area:canonical-floor-1:FT3:tile",
])
def test_source_signed_tile_finish_can_be_considered_for_tiling_trade(key):
    # This is only a negative guard; independent source/physical identity
    # and frozen evaluator must separately verify the actual result.
    assert _check(key) is None



@pytest.mark.parametrize("claimed_refs", [
    ["different-physical-floor"],
    ["canonical-floor-1", "unrelated-physical-floor"],
])
def test_tile_source_key_cannot_map_an_unrelated_or_grouped_physical_floor(
    claimed_refs,
):
    # A source-signed material type alone does not prove the physical
    # identity in an independently mapped frozen tiling item. A valid
    # signature on a contradictory floor ID still must be rejected.
    with pytest.raises(ValueError, match="floor|source.*identity"):
        _check(
            "floor_finish_area:canonical-floor-1:FT3:tile",
            claimed_refs=claimed_refs,
        )


@pytest.mark.parametrize("finish", ["vinyl", "epoxy", "carpet", "tile ", "TILE"])
def test_non_tile_source_finish_cannot_score_as_original_tiling(finish):
    with pytest.raises(ValueError, match="original source-signed tile"):
        _check(f"floor_finish_area:canonical-floor-1:FT3:{finish}")


@pytest.mark.parametrize("key", [
    "floor_finish_area:canonical-floor-1:FT3",
    "floor_finish_area:canonical-floor-1:FT3:",
    "floor_finish_area::FT3:tile",
    "floor_finish_area:canonical-floor-1::tile",
    "floor_finish_area:canonical-floor-1:FT3: tile",
    "floor_finish_area:canonical-floor-1:FT3:tile:vinyl",
    "floor_finish_area:canonical-floor-1:FT3:epoxy:tile",
    "floor_area:canonical-floor-1:FT3:tile",
    "floor_finish_area:canonical-floor-1:FT3:TILE",
    True, None, {}, [],
])
def test_malformed_or_ambiguous_original_material_key_never_grants_tiling(key):
    with pytest.raises(ValueError, match="original source-signed tile"):
        _check(key)


@pytest.mark.parametrize("finish", ["vinyl", "epoxy", "tile"])
def test_other_flooring_trade_may_use_source_supported_finish_types(finish):
    assert _check(
        f"floor_finish_area:canonical-floor-1:FT1:{finish}",
        trade="flooring",
    ) is None


def test_ft3_label_does_not_override_real_signed_vinyl_source_semantic():
    with pytest.raises(ValueError, match="original source-signed tile"):
        _check("floor_finish_area:canonical-floor-1:FT3:vinyl")


def test_abstained_unknown_material_never_becomes_scored_tiling():
    with pytest.raises(ValueError, match="original source-signed tile"):
        _check(
            "floor_finish_area:canonical-floor-1:FT3:epoxy",
            abstained=True,
        )


def test_unmapped_source_unsupported_finish_never_creates_identity_crosswalk():
    require_signed_v2_family_trade_integrity(
        verified_items=[{
            "item_id": "source-target", "denominator_eligible": True,
            "trade_category": "tiling",
        }],
        sealed_quantities=[{
            "family": "floor_finish_area",
            "semantic_key": "floor_finish_area:floor:FT3:vinyl",
            "object_identity_refs": ["source-floor"],
            "unit": "m2", "value": 2.0, "abstained": False,
        }],
        identity_bindings=[],
    )
