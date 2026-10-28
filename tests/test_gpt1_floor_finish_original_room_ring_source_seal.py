"""Original canonical room geometry must own any sealed floor finish.

Negative-only source authority: live floor projection copies its original room
ring. Tests traverse the actual source trace, sealed quantity and customer
projection, never deriving a finish, dimension, room or frozen score.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
    seal_live_floor_finish_area_run,
)
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with_canonical_room,
)
from tests.test_live_floor_finish_area_source_closed_export import _claim


def _claim_with_room():
    return _claim_with_canonical_room()


def _traces(claim):
    return build_live_floor_finish_area_source_traces(
        claim, workspace_id=1, project_id="source-room-finish",
    )


def _seal(claim):
    return seal_live_floor_finish_area_run(
        claim, workspace_id=1, project_id="source-room-finish",
    )


def _customer(claim):
    return project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="source-room-finish",
    )


@pytest.mark.parametrize("tamper", (
    "floor_ring", "room_ring", "room_face", "room_snapshot",
    "room_document", "room_revision", "room_page", "room_viewport",
    "duplicate_room", "missing_room",
))
def test_foreign_original_room_cannot_authorize_sealed_floor_finish(tamper):
    original = _claim_with_room()
    floor = original.canonical_floors[0]
    room = original.canonical_rooms[0]
    assert len(_traces(original)) == len(_seal(original).quantities) == 1
    assert len(_customer(original)) == 1

    if tamper == "floor_ring":
        changed = replace(floor, polygon_pdf_pts=(
            (10., 10.), (25., 10.), (25., 20.), (10., 20.),
        ))
        claim = replace(original, canonical_floors=(changed,))
    elif tamper == "room_ring":
        changed = replace(room, polygon_pdf_pts=(
            (10., 10.), (20., 10.), (20., 25.), (10., 25.),
        ))
        claim = replace(original, canonical_rooms=(changed,))
    elif tamper == "duplicate_room":
        rival = replace(room, physical_room_id="rival-physical-room")
        claim = replace(original, canonical_rooms=(room, rival))
    elif tamper == "missing_room":
        changed = replace(room, canonical_room_id="other-original-room")
        claim = replace(original, canonical_rooms=(changed,))
    else:
        field, value = {
            "room_face": ("source_room_face_record_id", "other-original-face"),
            "room_snapshot": ("snapshot_id", "other-original-snapshot"),
            "room_document": ("document_id", "other-original-document"),
            "room_revision": ("revision_id", "other-original-revision"),
            "room_page": ("page_id", "other-page"),
            "room_viewport": ("viewport_id", "other-viewport"),
        }[tamper]
        claim = replace(original, canonical_rooms=(replace(room, **{field: value}),))

    for consumer in (_traces, _seal, _customer):
        with pytest.raises(SourceClosedRunConflictError, match="original canonical room"):
            consumer(claim)
    assert original.canonical_floors == (floor,)
    assert original.canonical_rooms == (room,)


@pytest.mark.parametrize("transform", ("rotate", "reverse", "closed"))
def test_equivalent_original_room_ring_keeps_customer_and_seal(transform):
    original = _claim_with_room()
    room = original.canonical_rooms[0]
    ring = room.polygon_pdf_pts
    equivalent = {
        "rotate": ring[2:] + ring[:2],
        "reverse": tuple(reversed(ring)),
        "closed": ring + (ring[0],),
    }[transform]
    claim = replace(original, canonical_rooms=(
        replace(room, polygon_pdf_pts=equivalent),
    ))
    assert _traces(claim) == _traces(original)
    assert _seal(claim).to_json() == _seal(original).to_json()
    assert _customer(claim) == _customer(original)
    assert _seal(claim).fingerprint == _seal(original).fingerprint
    assert claim.canonical_rooms[0].polygon_pdf_pts == equivalent


def test_roomless_legacy_finish_and_source_remain_unchanged():
    claim = _claim()
    assert claim.canonical_rooms == ()
    assert len(_traces(claim)) == 1
    assert len(_seal(claim).quantities) == 1
    assert len(_customer(claim)) == 1
