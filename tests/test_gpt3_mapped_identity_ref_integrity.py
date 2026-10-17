"""Mapped production refs must not collapse to an accidental empty-key join."""
import pytest
from tools.gpt3_signed_v2_family_trade_integrity import require_signed_v2_family_trade_integrity as veto

ITEM = {"item_id": "t", "denominator_eligible": True, "trade_category": "doors"}


def bind(refs):
    return {"benchmark_item_id": "t", "production_object_identity_refs": refs, "production_family": "opening_area"}


@pytest.mark.parametrize("bad", [None, [], (), ["x", "x"], ["x", ""], [" x"], ["x "], ["x", 1], ["x", None], "x", True, {}])
def test_invalid_mapped_refs_fail_before_spurious_empty_ref_match(bad):
    with pytest.raises(ValueError, match="not canonical"):
        veto(verified_items=[ITEM], sealed_quantities=[], identity_bindings=[bind(bad)])


def test_order_of_distinct_valid_refs_still_has_exact_join():
    q = {"object_identity_refs": ["b", "a"], "family": "opening_area", "semantic_key": "door_area:valid"}
    veto(verified_items=[ITEM], sealed_quantities=[q], identity_bindings=[bind(["a", "b"])])


def test_unmapped_abstained_empty_ref_quantity_still_allowed():
    q = {"object_identity_refs": [], "family": "opening_area", "semantic_key": ""}
    veto(verified_items=[ITEM], sealed_quantities=[q], identity_bindings=[])
