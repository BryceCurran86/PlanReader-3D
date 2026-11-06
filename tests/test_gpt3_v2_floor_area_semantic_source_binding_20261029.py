"""GPT3: source-neutral V2 floor-area semantic/physical identity mapping veto."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from tools.gpt3_signed_v2_family_trade_integrity import require_signed_v2_family_trade_integrity


def _inputs(*, semantic_key="floor_area:original-floor", source_refs=("original-floor",),
            bound_refs=None, abstained=False, trade="flooring"):
    item = SimpleNamespace(item_id="synthetic-target", denominator_eligible=True,
                           trade_category=trade)
    quantity = SimpleNamespace(family="floor_area", semantic_key=semantic_key,
                               object_identity_refs=source_refs, abstained=abstained,
                               unit="m2", value=8.125)
    bound = SimpleNamespace(
        benchmark_item_id="synthetic-target", production_family="floor_area",
        production_object_identity_refs=source_refs if bound_refs is None else bound_refs,
    )
    return (item,), (quantity,), (bound,)


def _check(inputs):
    items, quantities, bindings = inputs
    return require_signed_v2_family_trade_integrity(
        verified_items=items, sealed_quantities=quantities, identity_bindings=bindings,
    )


def test_exact_original_source_floor_semantic_and_physical_member_replay():
    original = _inputs()
    before = deepcopy(original)
    assert _check(original) is None
    assert _check(original) is None
    assert original == before


@pytest.mark.parametrize(("semantic_key", "source_refs"), [
    ("floor_area:foreign-floor", ("original-floor",)),
    ("floor_area:", ("original-floor",)),
    ("floor_area:original-floor ", ("original-floor",)),
    ("floor_area:original-floor", ("original-floor", "other-floor")),
    ("floor_area:foreign-floor", ("original-floor", "other-floor")),
])
def test_wrong_or_grouped_original_floor_semantics_abstain(
    semantic_key, source_refs,
):
    original = _inputs(semantic_key=semantic_key, source_refs=source_refs)
    before = deepcopy(original)
    with pytest.raises(ValueError, match="floor area semantic source physical identity mismatch"):
        _check(original)
    assert original == before


def test_untyped_legacy_floor_semantic_is_not_rewritten_or_newly_authorized():
    assert _check(_inputs(semantic_key="source-owned")) is None


def test_abstained_floor_does_not_gain_metric_semantic_authority():
    assert _check(_inputs(semantic_key="floor_area:foreign-floor", abstained=True)) is None


def test_unmapped_floor_cannot_be_rebound_by_this_negative_guard():
    assert _check(_inputs(semantic_key="floor_area:foreign-floor",
                          bound_refs=("other-identity",))) is None


def test_trade_mismatch_still_refused_by_original_family_trade_boundary():
    with pytest.raises(ValueError, match="reclassified"):
        _check(_inputs(trade="tiling"))
