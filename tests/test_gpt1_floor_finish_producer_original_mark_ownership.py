"""Original source material mark ownership must survive producer ID rekeys."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_cross_view_floor_finish_authority import (
    CrossViewFloorFinishProducer,
    _quarantine_reused_floor_finish_occurrences,
)
from tests.test_cross_view_floor_finish_authority_v1 import (
    _patch_material_viewports,
    _payload,
    _source_room_area_and_floor,
)


def _authentic_record(monkeypatch):
    _patch_material_viewports(monkeypatch)
    source, room_areas, floors = _source_room_area_and_floor(_payload())
    result = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=room_areas, floors=floors
    ).publish()
    assert len(result.records) == 1
    return result.records[0]


def test_source_issuer_rekey_with_same_original_mark_cannot_count_two_rooms(monkeypatch):
    authentic = _authentic_record(monkeypatch)
    other = replace(
        authentic,
        canonical_floor_id="competing-floor",
        physical_floor_surface_id="competing-physical-floor",
        physical_room_id="competing-room",
        occurrence_record_id="source-issued-alias",
        # occurrence_evidence_id remains the EXACT same source mark.
    )
    for items in ((authentic, other), (other, authentic)):
        kept, unresolved = _quarantine_reused_floor_finish_occurrences(items)
        assert kept == ()
        assert unresolved == tuple(sorted((
            authentic.canonical_floor_id, other.canonical_floor_id
        )))


def test_independent_original_mark_with_separate_source_occurrence_survives(monkeypatch):
    authentic = _authentic_record(monkeypatch)
    independent = replace(
        authentic,
        canonical_floor_id="independent-floor",
        physical_floor_surface_id="independent-physical-floor",
        physical_room_id="independent-room",
        occurrence_record_id="independent-occurrence",
        occurrence_evidence_id="independent-original-source-mark",
    )
    kept, unresolved = _quarantine_reused_floor_finish_occurrences(
        (independent, authentic)
    )
    assert kept == (independent, authentic)
    assert unresolved == ()


@pytest.mark.parametrize("field", [
    "canonical_floor_id", "physical_floor_surface_id",
    "occurrence_record_id", "occurrence_evidence_id",
])
@pytest.mark.parametrize("bad", ["", " padded", "padded ", True, 23])
def test_issuer_identity_malformed_before_quantity_production(monkeypatch, field, bad):
    authentic = _authentic_record(monkeypatch)
    invalid = replace(authentic, **{field: bad})
    kept, unresolved = _quarantine_reused_floor_finish_occurrences((invalid,))
    assert kept == ()
    expected = () if field == "canonical_floor_id" else (authentic.canonical_floor_id,)
    assert unresolved == expected


def test_repeated_source_producer_check_does_not_mutate_source_evidence(monkeypatch):
    authentic = _authentic_record(monkeypatch)
    before = repr(authentic)
    original = _quarantine_reused_floor_finish_occurrences((authentic,))
    assert original == ((authentic,), ())
    assert _quarantine_reused_floor_finish_occurrences((authentic,)) == original
    assert repr(authentic) == before
