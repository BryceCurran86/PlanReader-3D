"""Adversarial source-neutral V2 trade veto identity tests."""
import pytest
from tools.gpt3_signed_v2_family_trade_integrity import require_signed_v2_family_trade_integrity as veto


def item(identity, eligible=True):
    return {"item_id": identity, "denominator_eligible": eligible, "trade_category": "doors"}


def test_distinct_source_neutral_eligible_ids_remain_valid():
    veto(verified_items=[item("a"), item("b")], sealed_quantities=[], identity_bindings=[])


@pytest.mark.parametrize("invalid", ["", None, True, 7, [], {}])
def test_missing_or_untyped_eligible_frozen_item_id_is_never_silently_dropped(invalid):
    with pytest.raises(ValueError, match="canonical identity"):
        veto(verified_items=[item(invalid)], sealed_quantities=[], identity_bindings=[])


def test_conflicting_duplicate_eligible_ids_do_not_overwrite_trade_category():
    a = item("same")
    b = {**a, "trade_category": "windows"}
    with pytest.raises(ValueError, match="duplicate eligible"):
        veto(verified_items=[a, b], sealed_quantities=[], identity_bindings=[])


def test_ineligible_duplicate_does_not_change_real_frozen_item():
    veto(verified_items=[item("a"), item("a", False)],
         sealed_quantities=[], identity_bindings=[])
