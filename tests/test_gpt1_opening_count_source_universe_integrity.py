"""Source-owned opening count universes cannot be made complete by ID dedup."""
from __future__ import annotations

import pytest

from pb_live_opening_count_quantity_publication import (
    _authentic_source_id_universe,
    _valid_explicit_source_count,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tests.test_live_opening_count_quantity_publication import (
    _floor_plan_with_schedule_quantity,
)


@pytest.mark.parametrize("invalid", [
    (), [], None, "", "observation-1", ("source-1", "source-1"),
    ("source-1", ""), ("source-1", " "), ("source-1", True),
    ("source-1", 2), (" source-1",), ("source-1 ",),
])
def test_count_universe_never_silently_sanitizes_original_observation_ids(invalid):
    assert _authentic_source_id_universe(invalid) is False


@pytest.mark.parametrize("authentic", [
    ("source-1",), ["source-1", "source-2"],
    ("source-1", "source-2", "source-3"),
])
def test_distinct_typed_original_observation_members_remain_valid(authentic):
    assert _authentic_source_id_universe(authentic) is True


def test_original_explicit_schedule_count_still_reaches_canonical_quantity(tmp_path):
    path = tmp_path / "explicit-count-original-source.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.canonical_openings) == 1
    assert len(claim.opening_count_quantity_evidence) == 1
    quantity = claim.opening_count_quantity_evidence[0]
    assert quantity.value == 1.0
    assert quantity.input_entity_ids == (claim.canonical_openings[0].canonical_opening_id,)
    assert quantity.metadata["schedule_corroborated"] is True


def test_missing_explicit_schedule_quantity_still_means_abstain(tmp_path):
    path = tmp_path / "opening-without-quantity.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=None))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert claim.opening_count_quantity_evidence == ()



@pytest.mark.parametrize("invalid_count", [
    None, True, False, "1", "", -1, 0, 1.5, float("nan"),
    float("inf"), -float("inf"), 10 ** 1000,
])
def test_schedule_count_cannot_convert_invalid_or_nonfinite_source_quantity(invalid_count):
    assert _valid_explicit_source_count(invalid_count) is False


@pytest.mark.parametrize("real_count", [1, 2, 1.0, 5.0])
def test_exact_source_integer_counts_remain_supported(real_count):
    assert _valid_explicit_source_count(real_count) is True



def test_existing_source_inventory_with_unresolved_existence_remains_without_count(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pb_migration_contracts import EvidenceResolutionStatus
    from pb_physical_opening_authority import PhysicalOpeningAuthority
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    payload = _floor_plan_with_schedule_quantity(quantity=1)
    source = SourceVisibilityProducer(
        producer_method="opening-count-universe-regression",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-count-universe",
        source_bytes=payload,
        source_locator="memory://opening-count-universe.pdf",
    )
    walls = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    # Control: original producer has a complete, explicitly quantified W1.
    control = publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source, wall_opening_composition=walls,
    )
    assert len(control) == 1
    assert control[0].value == 1.0

    def missing_physical_existence(_self, _selector):
        return SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            existence_record=None,
        )

    monkeypatch.setattr(
        PhysicalOpeningAuthority, "prove_existence", missing_physical_existence,
    )
    assert publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source, wall_opening_composition=walls,
    ) == ()



def _authentic_issued_count_quantity():
    from dataclasses import replace
    from pb_live_opening_area_quantity_publication import _opening_quantity
    from tests.test_live_opening_area_quantity_publication import _opening
    area = _opening_quantity(_opening())
    assert area is not None
    from pb_generic_opening_count_authority import (
        GENERIC_OPENING_COUNT_SCHEMA_VERSION,
    )
    return replace(
        area,
        family="opening_count",
        semantic_key="opening_count:W1",
        status="firm",
        unit="ea",
        value=1.0,
        input_entity_ids=("opening-1",),
        formula="sum_of_authenticated_physical_opening_instances",
        formula_version=GENERIC_OPENING_COUNT_SCHEMA_VERSION,
        authority="pdf_scaled",
        blocking_reasons=(),
        abstained=False,
        metadata={"opening_mark": "W1", "schedule_corroborated": True},
    )


def test_exact_positive_firm_count_reaches_final_source_publisher_gate():
    from pb_live_opening_count_quantity_publication import (
        _source_count_quantity_ready_for_publication,
    )
    assert _source_count_quantity_ready_for_publication(
        _authentic_issued_count_quantity(), opening_mark="W1",
    )


@pytest.mark.parametrize("corruption", [
    {"value": True},
    {"value": 1.5},
    {"value": "1"},
    {"value": 10 ** 400},
    {"input_entity_ids": ("opening-1", "opening-2")},
    {"input_entity_ids": ("opening-1", "opening-1")},
    {"input_entity_ids": ("opening-1", True)},
    {"input_entity_ids": (" opening-1",)},
    {"status": "provisional"},
    {"unit": "m2"},
    {"abstained": True},
    {"blocking_reasons": ("incomplete_opening_universe",)},
])
def test_invalid_final_count_never_reissues_as_a_commercial_physical_count(corruption):
    from dataclasses import replace
    from pb_live_opening_count_quantity_publication import (
        _source_count_quantity_ready_for_publication,
    )
    from copy import copy
    quantity = copy(_authentic_issued_count_quantity())
    for key, value in corruption.items():
        object.__setattr__(quantity, key, value)
    assert not _source_count_quantity_ready_for_publication(
        quantity, opening_mark="W1",
    )
