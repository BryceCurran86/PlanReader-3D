"""GPT3 V2: separate legitimate opening AREA/COUNT, forbid semantic kind drift."""
from __future__ import annotations

import pytest

from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity as veto,
)


def _quantities(area_kind="window", count_kind="door", *,
                same_physical=True, abstained_count=False):
    return [
        {"object_identity_refs": ["physical-opening-A"],
         "family": "opening_area",
         "semantic_key": f"{area_kind}_area:physical-opening-A",
         "unit": "m2", "value": 1.80, "abstained": False},
        {"object_identity_refs": [
            "physical-opening-A" if same_physical else "physical-opening-B"
        ],
         "family": "opening_count",
         "semantic_key": f"{count_kind}_count:source-owned-group-A",
         "unit": "nr", "value": None if abstained_count else 1,
         "abstained": abstained_count},
    ]


def _bindings(*, same_physical=True, area_kind="window", count_kind="door"):
    return (
        [
            {"item_id": "opening-area", "denominator_eligible": True,
             "trade_category": f"{area_kind}s"},
            {"item_id": "opening-count", "denominator_eligible": True,
             "trade_category": f"{count_kind}s"},
        ],
        [
            {"benchmark_item_id": "opening-area",
             "production_object_identity_refs": ["physical-opening-A"],
             "production_family": "opening_area"},
            {"benchmark_item_id": "opening-count",
             "production_object_identity_refs": [
                "physical-opening-A" if same_physical else "physical-opening-B"
             ],
             "production_family": "opening_count"},
        ],
    )


@pytest.mark.parametrize("area_kind,count_kind", [
    ("door", "window"), ("window", "door"),
])
def test_individual_compatible_trade_mappings_cannot_hide_contradictory_source_kind(
    area_kind, count_kind,
):
    items, bindings = _bindings(
        area_kind=area_kind, count_kind=count_kind
    )
    with pytest.raises(ValueError, match="area/count disagree"):
        veto(
            verified_items=items,
            sealed_quantities=_quantities(
                area_kind=area_kind, count_kind=count_kind
            ),
            identity_bindings=bindings,
        )


@pytest.mark.parametrize("kind", ["door", "window"])
def test_same_source_kind_area_and_independently_issued_count_may_both_match(kind):
    items, bindings = _bindings(area_kind=kind, count_kind=kind)
    veto(
        verified_items=items,
        sealed_quantities=_quantities(area_kind=kind, count_kind=kind),
        identity_bindings=bindings,
    )


def test_disjoint_physical_openings_do_not_cross_match_semantic_kind():
    items, bindings = _bindings(same_physical=False)
    veto(
        verified_items=items,
        sealed_quantities=_quantities(same_physical=False),
        identity_bindings=bindings,
    )


def test_unmapped_unrelated_source_claim_cannot_block_independent_other_opening():
    items, bindings = _bindings(same_physical=False)
    quantities = _quantities(same_physical=False)
    quantities.append({
        "object_identity_refs": ["third-opening"],
        "family": "opening_count",
        "semantic_key": "window_count:third-opening",
        "unit": "nr", "value": 1, "abstained": False,
    })
    quantities.append({
        "object_identity_refs": ["third-opening"],
        "family": "opening_area",
        "semantic_key": "door_area:third-opening",
        "unit": "m2", "value": 2.16, "abstained": False,
    })
    # An unrelated contradictory source object must be investigated upstream,
    # but it does not invent a map or erase two unrelated independently bound
    # verified physical source objects in this negative V2 guard.
    veto(
        verified_items=items,
        sealed_quantities=quantities,
        identity_bindings=bindings,
    )


def test_unresolved_count_abstention_never_becomes_positive_kind_claim():
    items, bindings = _bindings()
    veto(
        verified_items=items,
        sealed_quantities=_quantities(abstained_count=True),
        identity_bindings=[bindings[0]],
    )


def test_mapped_same_physical_multirow_conflict_fails_even_if_count_not_mapped():
    items, bindings = _bindings()
    with pytest.raises(ValueError, match="area/count disagree"):
        veto(
            verified_items=items,
            sealed_quantities=_quantities(),
            identity_bindings=[bindings[0]],
        )


def test_no_source_mapping_never_infers_a_frozen_object_identity():
    items, _ = _bindings()
    veto(
        verified_items=items,
        sealed_quantities=_quantities(),
        identity_bindings=[],
    )



@pytest.mark.parametrize("family,semantic_prefix,unit", [
    ("opening_area", "window_area", "m2"),
    ("opening_count", "window_count", "nr"),
])
def test_legacy_seal_cannot_map_duplicate_same_family_physical_opening(
    family, semantic_prefix, unit,
):
    items, bindings = _bindings(
        area_kind="window", count_kind="window"
    )
    source = _quantities(area_kind="window", count_kind="window")
    extra = {
        "object_identity_refs": ["physical-opening-A"],
        "family": family,
        "semantic_key": f"{semantic_prefix}:second-record",
        "unit": unit,
        "value": 1 if family == "opening_count" else 1.8,
        "abstained": False,
    }
    with pytest.raises(ValueError, match="multiple source opening quantities"):
        veto(
            verified_items=items,
            sealed_quantities=[*source, extra],
            identity_bindings=bindings,
        )


def test_legacy_duplicate_source_claim_for_unmapped_object_cannot_rekey_valid_openings():
    items, bindings = _bindings(
        same_physical=False, area_kind="window", count_kind="door"
    )
    source = _quantities(same_physical=False)
    source += [
        {"object_identity_refs": ["unmapped-opening"],
         "family": "opening_area", "semantic_key": "door_area:unmapped-A",
         "unit": "m2", "value": 1.8, "abstained": False},
        {"object_identity_refs": ["unmapped-opening"],
         "family": "opening_area", "semantic_key": "door_area:unmapped-B",
         "unit": "m2", "value": 1.8, "abstained": False},
    ]
    veto(
        verified_items=items,
        sealed_quantities=source,
        identity_bindings=bindings,
    )


@pytest.mark.parametrize("claimed_refs", [
    ["unrelated-opening"],
    ["physical-opening-A", "foreign-opening"],
])
def test_source_signed_opening_area_cannot_claim_foreign_or_grouped_physical_members(
    claimed_refs,
):
    # Actual source issuer signs typed opening AREA semantic suffix equal
    # to its one canonical opening, and input_entity_ids=(that opening,).
    # A verified V1 signature on a contradictory source receipt must not
    # turn a different physical opening into an eligible trade match.
    signed = {
        "family": "opening_area",
        "semantic_key": "window_area:physical-opening-A",
        "object_identity_refs": claimed_refs,
        "unit": "m2",
        "value": 1.80,
        "abstained": False,
    }
    with pytest.raises(ValueError, match="physical|source.*identity|opening.*identity"):
        veto(
            verified_items=[{
                "item_id": "synthetic-window",
                "denominator_eligible": True,
                "trade_category": "windows",
            }],
            sealed_quantities=[signed],
            identity_bindings=[{
                "benchmark_item_id": "synthetic-window",
                "production_family": "opening_area",
                "production_object_identity_refs": claimed_refs,
            }],
        )


def test_authentic_single_source_opening_area_semantic_and_ref_agree():
    # This is only an independent negative mapping guard, not a producer,
    # source-origin receipt, original drawing measurement or scored match.
    veto(
        verified_items=[{
            "item_id": "synthetic-window",
            "denominator_eligible": True,
            "trade_category": "windows",
        }],
        sealed_quantities=[{
            "family": "opening_area",
            "semantic_key": "window_area:physical-opening-A",
            "object_identity_refs": ["physical-opening-A"],
            "unit": "m2",
            "value": 1.80,
            "abstained": False,
        }],
        identity_bindings=[{
            "benchmark_item_id": "synthetic-window",
            "production_family": "opening_area",
            "production_object_identity_refs": ["physical-opening-A"],
        }],
    )
