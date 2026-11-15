"""Existing dimension authority must reuse authenticated page views safely."""
from __future__ import annotations

from dataclasses import replace

import pytest

import pb_source_visibility_authority as visibility_module
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority
from test_cross_view_room_area_authority_v1 import _source_and_room
from test_same_view_room_area_authority_v1 import _source_and_rooms


def _case(kind):
    if kind == "same":
        source, rooms = _source_and_rooms()
        publish = lambda: SameViewRoomAreaProducer.from_source(
            source=source, rooms=rooms,
        ).publish()
    else:
        source, rooms = _source_and_room()
        publish = lambda: CrossViewRoomAreaProducer.from_source(
            source=source, rooms=rooms,
        ).publish()
    return source, rooms, publish


def _legacy_rows(self, published, *, bind_page_id=None):
    rows = []
    for observation_id in published.visible_observation_ids:
        result = self.resolve_visible(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if result.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        observation = result.observation
        if observation is not None and (
            bind_page_id is None or observation.page_id == bind_page_id
        ):
            rows.append((observation_id, observation))
    return tuple(rows)


@pytest.mark.parametrize("kind", ["same", "cross"])
def test_complete_figured_area_records_match_original_scalar_proof(kind, monkeypatch):
    _source, _rooms, publish = _case(kind)
    optimized = publish()
    assert optimized.records
    monkeypatch.setattr(
        SourceVisibilityAuthority, "authenticated_visible_observations", _legacy_rows,
    )
    assert publish() == optimized


@pytest.mark.parametrize("kind", ["same", "cross"])
def test_dimension_queries_do_not_repeat_scalar_visible_resolution(kind, monkeypatch):
    _source, _rooms, publish = _case(kind)
    original = SourceVisibilityAuthority.resolve_visible
    calls = []
    def counted(self, selector):
        calls.append(selector)
        return original(self, selector)
    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", counted)
    first = publish()
    assert first.records
    assert publish() == first
    assert calls == []


def test_repeated_room_queries_reuse_existing_bound_aliases(monkeypatch):
    _source, _rooms, publish = _case("same")
    baseline = publish()
    assert baseline.records
    original = visibility_module._native_visible_alias
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(visibility_module, "_native_visible_alias", counted)
    assert publish() == baseline
    assert publish() == baseline
    assert calls == []


@pytest.mark.parametrize("damage", ["parent", "fingerprint", "origin", "bytes"])
def test_warm_dimension_page_proof_rejects_source_damage(damage):
    source, rooms, publish = _case("same")
    assert publish().records
    revision = rooms.rooms[0].revision_id
    published = source.published_snapshot_for_revision(revision)
    sid = published.snapshot.snapshot_id
    visible_id = published.visible_observation_ids[0]
    store = source._producer._store
    parent_id = source._visibility_receipts[(sid, visible_id)]
    if damage == "parent":
        key = (sid, parent_id)
        store.observations[key] = replace(
            store.observations[key], geometry=(1.0, 2.0, 99.0, 2.0),
        )
    elif damage == "fingerprint":
        store.record_fingerprints[(sid, parent_id)] = "corrupt-parent-fingerprint"
    elif damage == "origin":
        source._visible_origin_kinds[(sid, visible_id)] = "unissued-origin"
    else:
        store.source_bytes_by_revision[revision] += b"source-change"
    result = publish()
    assert result.records == ()
    assert result.unresolved_physical_room_ids


def test_mutating_returned_page_clone_cannot_poison_dimension_geometry():
    source, rooms, publish = _case("same")
    baseline = publish()
    assert baseline.records
    published = source.published_snapshot_for_revision(rooms.rooms[0].revision_id)
    rows = source.authority().authenticated_visible_observations(
        published, bind_page_id="1",
    )
    assert rows
    object.__setattr__(rows[0][1], "geometry", (0.0, 0.0, 1.0, 0.0))
    assert publish() == baseline
