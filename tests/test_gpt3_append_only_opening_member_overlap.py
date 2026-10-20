"""GPT3 append-only release veto for *legacy* signed opening physical overlap."""
from __future__ import annotations

from dataclasses import replace

import pytest

from test_customer_output_verification import quantity
from test_gpt3_source_append_only_batch_gate import (
    _sealed, _customers,
)
from tools.gpt3_source_append_only_batch_gate import assess_append_only_signed_batch


def _audit(*added):
    original = quantity("original", "physical-original-room")
    return assess_append_only_signed_batch(
        _sealed(original),
        _sealed(original, *added),
        baseline_customers=_customers(original),
        candidate_customers=_customers(original, *added),
    )


@pytest.mark.parametrize("family,unit,prefix", [
    ("opening_area", "m2", "door_area"),
    ("opening_count", "ea", "door_count"),
])
def test_partially_overlapping_legacy_source_opening_groups_cannot_enter_batch(
    family, unit, prefix,
):
    first = replace(
        quantity("group-first", "physical-A"),
        family=family, semantic_key=f"{prefix}:original-source-group-A",
        input_entity_ids=("physical-A", "physical-B"), unit=unit,
        value=2.0,
    )
    second = replace(
        quantity("group-second", "physical-B"),
        family=family, semantic_key=f"{prefix}:original-source-group-B",
        input_entity_ids=("physical-B", "physical-C"), unit=unit,
        value=2.0,
    )
    out = _audit(first, second)
    assert out["admission_status"] == "BLOCKED"
    assert out["first_failing_gate"] == (
        "DUPLICATE_OPENING_AREA_PHYSICAL_IDENTITY"
        if family == "opening_area"
        else "DUPLICATE_OPENING_COUNT_PHYSICAL_IDENTITY"
    )
    assert out["source_authenticated"] is False
    assert out["official_v2_accuracy"] is None


@pytest.mark.parametrize("area_kind,count_kind", [
    ("door", "window"), ("window", "door"),
])
def test_legacy_signed_area_and_count_cannot_disagree_about_one_physical_opening(
    area_kind, count_kind,
):
    area = replace(
        quantity("new-area", "physical-1"),
        family="opening_area", semantic_key=f"{area_kind}_area:physical-1",
        unit="m2", value=1.8,
    )
    count = replace(
        quantity("new-count", "physical-1"),
        family="opening_count", semantic_key=f"{count_kind}_count:physical-1",
        unit="ea", value=1.0,
    )
    out = _audit(area, count)
    assert out["admission_status"] == "BLOCKED"
    assert out["first_failing_gate"] == "CONFLICTING_ORIGINAL_OPENING_DOOR_WINDOW_KIND"


def test_legitimate_same_kind_area_and_independent_count_keep_separate_families():
    opening_id = "source-opening-A"
    area = replace(
        quantity("new-area", opening_id),
        family="opening_area", semantic_key=f"door_area:{opening_id}",
        unit="m2", value=1.8,
    )
    count = replace(
        quantity("new-count", opening_id),
        family="opening_count", semantic_key=f"door_count:{opening_id}",
        unit="ea", value=1.0,
    )
    out = _audit(area, count)
    assert out["admission_status"] == "READY_FOR_INDEPENDENT_IDENTITY_REVIEW"
    assert out["customer_approval_granted"] is False
    assert out["independent_benchmark_identity_verified"] is False
    assert out["official_v2_accuracy"] is None


def test_disjoint_original_openings_with_distinct_quantities_not_suppressed():
    first = replace(
        quantity("new-door", "physical-door"),
        family="opening_area", semantic_key="door_area:physical-door",
        unit="m2", value=1.8,
    )
    second = replace(
        quantity("new-window", "physical-window"),
        family="opening_area", semantic_key="window_area:physical-window",
        unit="m2", value=2.16,
    )
    result = _audit(first, second)
    assert result["admission_status"] == "READY_FOR_INDEPENDENT_IDENTITY_REVIEW"
    assert result["added_quantity_ids"] == ["new-door", "new-window"]


def test_unsourced_shadow_abstention_never_claims_a_count_or_masked_area():
    real = replace(
        quantity("new-area", "physical-A"),
        family="opening_area", semantic_key="door_area:physical-A",
        unit="m2", value=1.8,
    )
    abstained = replace(
        quantity("new-count", "physical-A"),
        family="opening_count", semantic_key="door_count:physical-A",
        unit="ea", value=None, abstained=True,
        blocking_reasons=("complete_instance_universe_unproven",),
    )
    outcome = _audit(real, abstained)
    assert outcome["first_failing_gate"] == "NEW_QUANTITY_NOT_FIRM_SOURCE_CLOSED"
    assert outcome["admission_status"] == "BLOCKED"
