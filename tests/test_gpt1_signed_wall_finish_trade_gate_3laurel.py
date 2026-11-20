"""Source-owned wall_finish_area is compatible only with tiling-area target scope.

This is a narrow repair of the original four-project signed trade guard, NOT
benchmark truth modification or automatic wall area publication.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)


def _input(trade: str = "tiling", unit: str = "m2", family: str = "wall_finish_area"):
    identity = "3laurel:surface:wall_tile:ensuite_rear_flat_after_niche"
    items = [{"item_id": "source-independent-tiling-object", "denominator_eligible": True,
              "trade_category": trade, "expected_object_refs": [identity]}]
    rows = [{"object_identity_refs": [identity], "family": family, "unit": unit,
             "value": 3.21, "abstained": False}]
    bindings = [{"benchmark_item_id": "source-independent-tiling-object",
                 "production_family": "wall_finish_area", "production_object_identity_refs": [identity]}]
    return items, rows, bindings


def test_sealed_wall_tile_area_is_exactly_tiling_area_semantics():
    items, rows, bindings = _input()
    require_signed_v2_family_trade_integrity(
        verified_items=items, sealed_quantities=rows, identity_bindings=bindings,
    )


@pytest.mark.parametrize("trade", ["painting", "cladding", "ceilings", "flooring", "roofing", "doors", "windows"])
def test_signed_wall_tiles_cannot_be_relabelled_as_another_trade(trade):
    items, rows, bindings = _input(trade=trade)
    with pytest.raises(ValueError, match="bound production family cannot be reclassified"):
        require_signed_v2_family_trade_integrity(
            verified_items=items, sealed_quantities=rows, identity_bindings=bindings,
        )


@pytest.mark.parametrize("unit", ["ea", "m", "mm", "kg", "%", "", "m2 "])
def test_signed_wall_tile_area_requires_area_units(unit):
    items, rows, bindings = _input(unit=unit)
    with pytest.raises(ValueError, match="bound signed source unit disagrees"):
        require_signed_v2_family_trade_integrity(
            verified_items=items, sealed_quantities=rows, identity_bindings=bindings,
        )


def test_mismatched_source_family_remains_rejected():
    items, rows, bindings = _input(family="floor_finish_area")
    with pytest.raises(ValueError, match="requires its explicit original production family"):
        require_signed_v2_family_trade_integrity(
            verified_items=items, sealed_quantities=rows, identity_bindings=bindings,
        )


def test_real_sha_pinned_3laurel_wall_tile_source_8_review_rows_are_tiling_only():
    from tests.original_source_3laurel import require_original_3laurel
    from pb_three_laurel_wall_tile_customer import issue_original_three_laurel_wall_tile_customer_quantities
    from tools.report_gpt3_four_project_evidence import _load_unchanged_frozen_modules, FROZEN_ROOT

    path = require_original_3laurel()
    result = issue_original_three_laurel_wall_tile_customer_quantities(path, workspace_id=1)
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.sealed_run is not None and len(result.sealed_run.quantities) == 8
    _, manifests, _, _, _ = _load_unchanged_frozen_modules()
    manifest = next(m for m in manifests(FROZEN_ROOT) if m.project_id == "au_qld_3laurel")
    bindings = []
    for quantity in result.sealed_run.quantities:
        matches = [item for item in manifest.verified_items
                   if item.trade_category == "tiling"
                   and set(item.expected_object_refs) == set(quantity.object_identity_refs)]
        assert len(matches) == 1
        bindings.append(SimpleNamespace(
            benchmark_item_id=matches[0].item_id,
            production_object_identity_refs=tuple(quantity.object_identity_refs),
            production_family="wall_finish_area",
        ))
    require_signed_v2_family_trade_integrity(
        verified_items=manifest.verified_items,
        sealed_quantities=result.sealed_run.quantities,
        identity_bindings=bindings,
    )