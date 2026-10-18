"""GPT2 source-owner regression: public floor finish result cannot reissue one mark twice.

The producer already quarantines source-owner conflicts before constructing a
result. A reconstructed result and the enrichment adapter must fail closed too.
Synthetic, no owner PDFs, no benchmark expected values or quantity promotion.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_cross_view_floor_finish_authority import (
    CrossViewFloorFinishProducer,
    CrossViewFloorFinishResult,
    enrich_live_canonical_floor_finishes,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_floor_finish_authority_v1 import (
    _patch_material_viewports,
    _payload,
    _source_room_area_and_floor,
)


def _producer_result(monkeypatch):
    _patch_material_viewports(monkeypatch)
    source, room_areas, floors = _source_room_area_and_floor(_payload())
    original = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=room_areas, floors=floors
    ).publish()
    assert len(original.records) == 1
    return original.records[0], floors


def _different_room(original):
    floor_id = "different-canonical-floor"
    different_quantity = replace(
        original.quantity,
        quantity_id="different-firm-floor-finish-quantity",
        input_entity_ids=(floor_id,),
        semantic_key="floor_finish_area:different-canonical-floor:FT1:tile",
    )
    return replace(
        original,
        canonical_floor_id=floor_id,
        physical_floor_surface_id="different-physical-floor",
        physical_room_id="different-physical-room",
        source_room_face_record_id="different-source-room-face",
        occurrence_record_id="different-material-occurrence",
        occurrence_evidence_id="different-original-source-mark",
        quantity=different_quantity,
    )


def _public_result(*records):
    return CrossViewFloorFinishResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("reconstructed",),
        records=tuple(records),
        unresolved_canonical_floor_ids=(),
    )


def test_two_source_independent_floors_remain_visible_without_rekey_conflict(monkeypatch):
    original, _ = _producer_result(monkeypatch)
    other = _different_room(original)
    reconstructed = _public_result(other, original)
    assert set(reconstructed.records_by_floor_id) == {
        original.canonical_floor_id, other.canonical_floor_id
    }
    assert len(reconstructed.quantities) == 2


@pytest.mark.parametrize("reused_identity", [
    "occurrence_record_id",
    "occurrence_evidence_id",
    "physical_floor_surface_id",
    "physical_room_id",
    "source_room_face_record_id",
    "quantity_id",
])
def test_reconstructed_result_quarantines_both_owners_of_one_source_or_quantity_id(
    monkeypatch, reused_identity,
):
    original, _ = _producer_result(monkeypatch)
    other = _different_room(original)
    if reused_identity == "quantity_id":
        other = replace(
            other, quantity=replace(
                other.quantity, quantity_id=original.quantity.quantity_id
            )
        )
    else:
        other = replace(other, **{
            reused_identity: getattr(original, reused_identity)
        })
    for order in ((original, other), (other, original)):
        result = _public_result(*order)
        assert result.records_by_floor_id == {}
        assert result.quantities == ()


def test_reconstructed_result_cannot_change_canonical_quantity_input(monkeypatch):
    original, _ = _producer_result(monkeypatch)
    other = _different_room(original)
    inconsistent = replace(
        other,
        quantity=replace(
            other.quantity,
            input_entity_ids=(original.canonical_floor_id,)
        )
    )
    result = _public_result(original, inconsistent)
    assert set(result.records_by_floor_id) == {original.canonical_floor_id}
    assert result.quantities == (original.quantity,)


def test_enrichment_never_assigns_reused_source_mark_even_for_a_valid_floor(monkeypatch):
    original, floors = _producer_result(monkeypatch)
    rival = _different_room(original)
    # The printed material mark is reused for an additional physical room;
    # consumer must not enrich even the otherwise valid original room.
    rival = replace(
        rival, occurrence_evidence_id=original.occurrence_evidence_id
    )
    rebuilt = _public_result(original, rival)
    enriched = enrich_live_canonical_floor_finishes(floors, rebuilt)
    assert enriched.status is EvidenceResolutionStatus.CONFLICT
    assert enriched.floors == floors.floors


def test_invalidly_rekeyed_rival_cannot_launder_the_shared_original_source_mark(monkeypatch):
    original, _ = _producer_result(monkeypatch)
    corrupt = replace(
        original,
        canonical_floor_id="",
        physical_floor_surface_id="other-but-invalid-floor",
        physical_room_id="other-room",
        source_room_face_record_id="other-room-face",
    )
    for order in ((original, corrupt), (corrupt, original)):
        result = _public_result(*order)
        assert result.quantities == ()
        assert result.records_by_floor_id == {}


def test_duplicate_same_floor_or_unsealed_record_cannot_enter_public_quantities(monkeypatch):
    original, _ = _producer_result(monkeypatch)
    assert _public_result(original, original).quantities == ()
    assert _public_result(original, None).quantities == (original.quantity,)
