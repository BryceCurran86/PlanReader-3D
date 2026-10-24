"""Strict V2 commercial trade veto for the actual source-owned ceiling_lining family."""
from __future__ import annotations

import pytest
from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)


def _veto(*, trade: str, family: str = "ceiling_lining",
          unit: str = "m2", refs=("source-ceiling-1",)):
    verified = [{"item_id": "frozen-ceiling-1", "denominator_eligible": True,
                 "trade_category": trade}]
    signed = [{
        "family": family,
        "semantic_key": "ceiling_lining:ceiling-1:GRID:ceiling_grid",
        "unit": unit,
        "object_identity_refs": list(refs),
        "value": 9.05352, "abstained": False,
    }]
    mapping = [{
        "benchmark_item_id": "frozen-ceiling-1",
        "production_family": family,
        "production_object_identity_refs": list(refs),
    }]
    return require_signed_v2_family_trade_integrity(
        verified_items=verified,
        sealed_quantities=signed,
        identity_bindings=mapping,
    )


@pytest.mark.parametrize("unit", ["m2", "m²", "sqm"])
def test_independently_mapped_ceiling_lining_accepts_area_unit_only(unit):
    assert _veto(trade="ceilings", unit=unit) is None


@pytest.mark.parametrize("trade", ["painting", "tiling", "flooring", "doors", "windows"])
def test_ceiling_lining_can_never_be_remapped_to_unrelated_trade(trade):
    with pytest.raises(ValueError, match="reclassified"):
        _veto(trade=trade)


@pytest.mark.parametrize("unit", ["m", "m3", "nr", "ea", "t", " m2 ", "count", True, 9])
def test_ceiling_lining_rejects_wrong_or_untyped_units(unit):
    with pytest.raises(ValueError, match="unit disagrees"):
        _veto(trade="ceilings", unit=unit)


def test_unknown_family_still_unscorable():
    with pytest.raises(ValueError, match="no verified benchmark trade semantics"):
        _veto(trade="ceilings", family="wall_net_area")


def test_unmapped_source_ceiling_lining_receipt_does_not_mint_identity():
    assert require_signed_v2_family_trade_integrity(
        verified_items=[{"item_id": "c", "denominator_eligible": True,
                         "trade_category": "ceilings"}],
        sealed_quantities=[{
            "family": "ceiling_lining", "unit": "m2",
            "semantic_key": "ceiling_lining:room-X",
            "object_identity_refs": ["unmapped-source-ceiling"],
        }],
        identity_bindings=[],
    ) is None
