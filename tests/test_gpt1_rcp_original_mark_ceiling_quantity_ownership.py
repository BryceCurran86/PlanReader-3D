"""One original RCP mark can support only one physical ceiling quantity.

Use source-neutral producer-owned test fixtures; no original building PDF
or benchmark truth is used to grant synthetic FIRM quantities.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_cross_view_ceiling_quantity_authority import (
    CrossViewCeilingQuantityResult,
    publish_cross_view_ceiling_quantities,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_quantity_authority import (
    _bridge, _finish, _room, _rooms,
)


def _two_room_args(*, same_mark: bool):
    room1 = _room()
    room2 = replace(
        room1,
        canonical_room_id="canonical-room-2",
        physical_room_id="physical-room-2",
        source_room_face_record_id="face-2",
        room_label="OTHER ROOM",
        room_label_binding_record_id="label-binding-2",
        room_label_evidence_ids=("room-label-evidence-2",),
        decision_scope_id="scope-2",
        evidence_ids=("room-evidence-2",),
        polygon_pdf_pts=((120., 0.), (180., 0.), (180., 70.), (120., 70.)),
        area_page_pts2=4200.,
    )
    first_bridge = _bridge()
    second_entity = replace(
        first_bridge.entities[0],
        candidate_entity_id="source-room-2",
        evidence_ids=("face-2", "room-geometry-evidence-2"),
        metadata={
            **first_bridge.entities[0].metadata,
            "source_room_index_id": "room-index-2",
        },
    )
    second_area = replace(
        first_bridge.quantities[0],
        quantity_id="room-area-qty-2",
        semantic_key="room_area:source-room-2",
        input_entity_ids=("source-room-2",),
        value=7.0,
        evidence_ids=("face-2", "room-geometry-evidence-2"),
        metadata={
            **first_bridge.quantities[0].metadata,
            "room_label": "OTHER ROOM",
            "figured_dimension_ids": ["second-room-dim-h", "second-room-dim-v"],
        },
    )
    second_bridge = replace(
        first_bridge,
        entities=(second_entity,),
        quantities=(second_area,),
    )
    first = _finish().records[0]
    second = replace(
        first,
        record_id="ceiling-finish-record-2",
        physical_room_id="physical-room-2",
        canonical_room_id="canonical-room-2",
        source_room_face_record_id="face-2",
        room_label="OTHER ROOM",
        occurrence_record_id="another-source-issuer-occurrence",
        occurrence_evidence_id=(
            first.occurrence_evidence_id if same_mark else "independent-source-mark"
        ),
        occurrence_observation_ids=("other-rcp-finish-obs",),
        occurrence_receipt_ids=("other-rcp-finish-receipt",),
        room_label_observation_ids=("other-rcp-label-obs",),
        room_label_receipt_ids=("other-rcp-label-receipt",),
    )
    rooms = replace(_rooms(), rooms=(room1, room2))
    finishes = replace(_finish(), records=(first, second))
    return rooms, (first_bridge, second_bridge), finishes


@pytest.mark.parametrize("reverse", [False, True])
def test_one_original_mark_rekeyed_to_two_physical_ceilings_blocks_both(reverse):
    rooms, bridges, finishes = _two_room_args(same_mark=True)
    if reverse:
        rooms = replace(rooms, rooms=tuple(reversed(rooms.rooms)))
        finishes = replace(finishes, records=tuple(reversed(finishes.records)))
        bridges = tuple(reversed(bridges))
    result = publish_cross_view_ceiling_quantities(
        rooms=rooms, room_area_bridges=bridges, finishes=finishes
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.records == ()
    assert result.quantities == ()
    assert result.canonical_ceilings == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1", "physical-room-2")


@pytest.mark.parametrize("reverse", [False, True])
def test_two_independent_original_marks_publish_two_distinct_ceiling_areas(reverse):
    rooms, bridges, finishes = _two_room_args(same_mark=False)
    if reverse:
        rooms = replace(rooms, rooms=tuple(reversed(rooms.rooms)))
        bridges = tuple(reversed(bridges))
        finishes = replace(finishes, records=tuple(reversed(finishes.records)))
    result = publish_cross_view_ceiling_quantities(
        rooms=rooms, room_area_bridges=bridges, finishes=finishes
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.quantities) == len(result.canonical_ceilings) == 2
    assert {q.value for q in result.quantities} == {9.05352, 7.0}
    assert {r.physical_room_id for r in result.records} == {
        "physical-room-1", "physical-room-2"
    }


@pytest.mark.parametrize("bad", [None, True, 17, "", " mark", "mark "])
def test_noncanonical_original_rcp_source_observation_cannot_own_ceiling(bad):
    finish = _finish()
    compromised = replace(
        finish,
        records=(replace(finish.records[0], occurrence_evidence_id=bad),),
    )
    result = publish_cross_view_ceiling_quantities(
        rooms=_rooms(), room_area_bridges=(_bridge(),), finishes=compromised
    )
    assert result.records == ()
    assert result.quantities == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_duplicate_ceiling_ids_are_absent_from_all_convenience_projections():
    rooms, bridges, finishes = _two_room_args(same_mark=False)
    resolved = publish_cross_view_ceiling_quantities(
        rooms=rooms, room_area_bridges=bridges, finishes=finishes
    )
    original = resolved.records[0]
    duplicate = replace(
        original,
        quantity=replace(original.quantity, quantity_id="competing-quantity"),
    )
    compromised = replace(resolved, records=(original, duplicate))
    assert not compromised.records_by_ceiling_id
    assert compromised.quantities == ()
    assert compromised.canonical_ceilings == ()
    assert len(resolved.quantities) == 2


def test_original_single_ceiling_source_quantity_stays_byte_identical():
    kwargs = {
        "rooms": _rooms(),
        "room_area_bridges": (_bridge(),),
        "finishes": _finish(),
    }
    a = publish_cross_view_ceiling_quantities(**kwargs)
    b = publish_cross_view_ceiling_quantities(**kwargs)
    assert a.status is EvidenceResolutionStatus.CORROBORATED
    assert a.quantities == b.quantities
    assert a.quantities[0].value == 9.05352
    assert a.canonical_ceilings == b.canonical_ceilings
