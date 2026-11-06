"""GPT3 frozen V2: legacy source-floor double-claims never score."""
import pytest

from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity as require,
)


def _floor(floor_id, *, key, family="floor_area", abstained=False):
    return {
        "family": family,
        "semantic_key": key,
        "object_identity_refs": [floor_id],
        "unit": "m2",
        "value": None if abstained else 9.05352,
        "abstained": abstained,
    }


def _target(floor_id, *, family="floor_area", trade="flooring"):
    return (
        [{"item_id": f"target-{family}", "denominator_eligible": True,
          "trade_category": trade}],
        [{"benchmark_item_id": f"target-{family}",
          "production_object_identity_refs": [floor_id],
          "production_family": family}],
    )


def test_legacy_v1_two_semantic_keys_one_physical_floor_do_not_score():
    floor = "producer-physical-office-floor"
    items, links = _target(floor)
    with pytest.raises(ValueError, match="duplicate source-signed geometric floor"):
        require(
            verified_items=items,
            sealed_quantities=[
                _floor(floor, key="floor_area:office-source"),
                _floor(floor, key="floor_area:alternate-physical-label"),
            ],
            identity_bindings=links,
        )


def test_legacy_v1_overlapping_group_claims_cannot_score_same_floor():
    floor = "physical-floor-B"
    items, links = _target(floor)
    first = _floor("physical-floor-A", key="floor_area:group-AB")
    first["object_identity_refs"] = ["physical-floor-A", floor]
    second = _floor(floor, key="floor_area:group-BC")
    second["object_identity_refs"] = [floor, "physical-floor-C"]
    with pytest.raises(ValueError, match="duplicate source-signed geometric floor"):
        require(
            verified_items=items, sealed_quantities=[first, second],
            identity_bindings=links,
        )


def test_independently_signed_distinct_floors_remain_score_eligible():
    floor = "producer-physical-office-floor"
    items, links = _target(floor)
    require(
        verified_items=items,
        sealed_quantities=[
            _floor(floor, key="floor_area:office"),
            _floor("producer-physical-food-prep-floor", key="floor_area:food-prep"),
        ],
        identity_bindings=links,
    )


def test_same_physical_parent_can_have_distinct_geometric_and_finish_families():
    floor = "producer-physical-office-floor"
    items, links = _target(floor, family="floor_finish_area", trade="tiling")
    require(
        verified_items=items,
        sealed_quantities=[
            _floor(floor, key="floor_area:office"),
            # The real finish issuer signs a material-specific semantic
            # key with the identical canonical physical floor identity.
            _floor(floor, key=f"floor_finish_area:{floor}:FT3:tile",
                   family="floor_finish_area"),
        ],
        identity_bindings=links,
    )


def test_abstained_unclosed_floor_cannot_duplicate_source_firm_identity():
    floor = "physical-source-airlock"
    items, links = _target(floor)
    require(
        verified_items=items,
        sealed_quantities=[
            _floor(floor, key="floor_area:source-firm"),
            _floor(floor, key="floor_area:unclosed-shadow", abstained=True),
        ],
        identity_bindings=links,
    )


def test_unmapped_legacy_duplicate_does_not_fabricate_identity_mapping():
    items, _ = _target("physical-source-no-target")
    require(
        verified_items=items,
        sealed_quantities=[
            _floor("unmapped-physical-floor", key="floor_area:first"),
            _floor("unmapped-physical-floor", key="floor_area:second"),
        ],
        identity_bindings=[],
    )
