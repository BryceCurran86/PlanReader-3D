"""Original canonical room geometry must own a sealed physical floor ring.

These source-neutral adversarial tests exercise the actual FIRM publisher,
source trace, sealed run and customer projector. They do not infer a new
physical room, measured area, finish, source authority or benchmark match.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with,
    _claim_with_canonical_room,
    _source_area,
)


def _claim():
    source = _source_area()
    source = replace(
        source,
        metadata={
            **source.metadata,
            "figured_dimension_ids": ("original-horizontal", "original-vertical"),
        },
    )
    return _claim_with_canonical_room(source)


def _traces(claim):
    return build_live_floor_area_source_traces(
        claim, workspace_id=7, project_id="original-room-floor",
    )


def _seal(claim):
    return seal_live_floor_area_run(
        claim, workspace_id=7, project_id="original-room-floor",
    )


def _customer(claim):
    return project_live_floor_area_customer_rows(
        claim, workspace_id=7, project_id="original-room-floor",
    )


@pytest.mark.parametrize("tamper", ("floor_ring", "room_ring", "room_face", "room_snapshot",
                                    "room_document", "room_page", "duplicate_room"))
def test_foreign_canonical_room_geometry_cannot_seal_original_floor(tamper):
    original = _claim()
    published = publish_live_floor_area_quantities(original)
    assert len(published) == 1 and published[0].value == 8.64

    floor = original.canonical_floors[0]
    room = original.canonical_rooms[0]
    if tamper == "floor_ring":
        changed = replace(floor, polygon_pdf_pts=(
            (10.0, 10.0), (25.0, 10.0), (25.0, 20.0), (10.0, 20.0),
        ))
        claim = replace(original, canonical_floors=(changed,))
    elif tamper == "room_ring":
        changed = replace(room, polygon_pdf_pts=(
            (10.0, 10.0), (20.0, 10.0), (20.0, 25.0), (10.0, 25.0),
        ))
        claim = replace(original, canonical_rooms=(changed,))
    elif tamper == "duplicate_room":
        rival = replace(room, physical_room_id="competing-physical-room")
        claim = replace(original, canonical_rooms=(room, rival))
    else:
        field, value = {
            "room_face": ("source_room_face_record_id", "other-original-face"),
            "room_snapshot": ("snapshot_id", "other-original-snapshot"),
            "room_document": ("document_id", "other-original-document"),
            "room_page": ("page_id", "2"),
        }[tamper]
        claim = replace(original, canonical_rooms=(replace(room, **{field: value}),))

    # The first failure was downstream of numeric FIRM publication.
    assert publish_live_floor_area_quantities(claim) == published
    for consumer in (_traces, _seal, _customer):
        with pytest.raises(SourceClosedRunConflictError, match="original canonical room"):
            consumer(claim)
    assert _traces(original)  # Genuine source owner remains sealable.
    assert original.canonical_floors == (floor,)
    assert original.canonical_rooms == (room,)


@pytest.mark.parametrize("transform", ("rotate", "reverse", "closed"))
def test_equivalent_original_ring_order_keeps_identical_seal_and_customer(transform):
    original = _claim()
    ring = original.canonical_rooms[0].polygon_pdf_pts
    alternate = {
        "rotate": ring[2:] + ring[:2],
        "reverse": tuple(reversed(ring)),
        "closed": ring + (ring[0],),
    }[transform]
    claim = replace(
        original,
        canonical_rooms=(replace(original.canonical_rooms[0], polygon_pdf_pts=alternate),),
    )
    baseline_run, variant_run = _seal(original), _seal(claim)
    baseline_rows, variant_rows = _customer(original), _customer(claim)
    assert len(baseline_run.quantities) == len(variant_run.quantities) == 1
    assert len(baseline_rows) == len(variant_rows) == 1
    assert variant_run.to_json() == baseline_run.to_json()
    assert variant_rows == baseline_rows
    assert variant_run.fingerprint == _seal(claim).fingerprint
    assert claim.canonical_rooms[0].polygon_pdf_pts == alternate


def test_roomless_legacy_floor_source_remains_unchanged():
    # This path historically publishes a documented floor with no room
    # inventory. The new negative gate does not mint or revoke that authority.
    claim = _claim_with(_source_area())
    assert claim.canonical_rooms == ()
    assert len(publish_live_floor_area_quantities(claim)) == 1
    assert len(_traces(claim)) == 1
    assert len(_seal(claim).quantities) == 1
