"""Typed door/window code must have source-owned identity after its prefix."""
import pytest
from tools.gpt3_signed_v2_family_trade_integrity import require_signed_v2_family_trade_integrity as veto

ITEM = {"item_id": "door-item", "denominator_eligible": True, "trade_category": "doors"}
BIND = {"benchmark_item_id": "door-item", "production_object_identity_refs": ["door-1"], "production_family": "opening_area"}


def apply(key):
    veto(verified_items=[ITEM],
         sealed_quantities=[{"object_identity_refs": ["door-1"], "family": "opening_area", "semantic_key": key}],
         identity_bindings=[BIND])


@pytest.mark.parametrize("invalid", ["door_area:", "door_area:   ", "door_area: valid", "door_area:valid ", " door_area:valid", "window_area:valid"])
def test_unowned_or_conflicting_opening_suffix_does_not_create_door_authority(invalid):
    with pytest.raises(ValueError, match="source-owned"):
        apply(invalid)


@pytest.mark.parametrize("valid", ["door_area:door-1", "door_area:D13", "door_area:source-qualified-id"])
def test_complete_source_owned_door_kind_still_passes_negative_guard(valid):
    apply(valid)
