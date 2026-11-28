"""A14/A15/A16/A24 tests: room legend normalization, finish symbol/code linkage, cold-room epoxy vs equipment exclusions."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_green_exclusion_epoxy_linkage_shadow import (
    CLASS_CONFLICT,
    CLASS_EPOXY_LABEL_ONLY,
    CLASS_EXCLUSION_LABEL_ONLY,
    FinishLegendDefinitionInput,
    FloorExclusionRoomCandidate,
    FloorFinishLabelObservation,
    link_green_exclusions_and_epoxy_labels,
)
from pb_source_room_legend_linkage_shadow import (
    PhysicalRoomFaceCandidate,
    RoomLegendTableRowInput,
    RoomNumberBubbleCandidate,
    canonical_room_number_key,
    link_room_legend_to_physical_rooms,
    parse_room_legend_rows,
)

_SHA = "c" * 64
_SQ1 = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
_SQ2 = ((120.0, 0.0), (220.0, 0.0), (220.0, 100.0), (120.0, 100.0))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RM\u201301", ("RM", 1)),
        ("R\u201404", ("R", 4)),
        ("L1\u221202", ("L1", 2)),
        ("G\u00a003", ("G", 3)),
        ("\uff32\uff2d\uff10\uff15", ("RM", 5)),
    ],
)
def test_a14_unicode_room_number_normalization(raw: str, expected: tuple[str, int]) -> None:
    assert canonical_room_number_key(raw) == expected


@pytest.mark.parametrize("non_room", ["D\u201301", "W\u201407", "FT1", "CL01", "0"])
def test_a14_opening_and_finish_codes_never_become_room_numbers(non_room: str) -> None:
    assert canonical_room_number_key(non_room) is None


def test_a14_schedule_of_rooms_and_room_list_headers_link_generically() -> None:
    rows = (
        RoomLegendTableRowInput("d1", "r1", _SHA, "1", "vp-leg", ("o1",), ("SCHEDULE OF ROOMS",)),
        RoomLegendTableRowInput("d1", "r1", _SHA, "1", "vp-leg", ("o2",), ("ROOM NO", "ROOM NAME")),
        RoomLegendTableRowInput("d1", "r1", _SHA, "1", "vp-leg", ("o3",), ("RM\u201301", "COLD ROOM")),
        RoomLegendTableRowInput("d1", "r1", _SHA, "1", "vp-leg", ("o4",), ("RM\u201302", "STAFF OFFICE")),
    )
    parsed = parse_room_legend_rows(rows)
    assert len(parsed.entries) == 2
    faces = (
        PhysicalRoomFaceCandidate("rf-1", "d1", "r1", _SHA, "1", "vp-plan", _SQ1, ("ev-1",)),
        PhysicalRoomFaceCandidate("rf-2", "d1", "r1", _SHA, "1", "vp-plan", _SQ2, ("ev-2",)),
    )
    # Only room 1 has a bubble; room 2 has missing label -> must remain unlinked/abstained, never guessed
    bubbles = (
        RoomNumberBubbleCandidate("b1", "d1", "r1", _SHA, "1", "vp-plan", "ob1", "RM 01", (50.0, 50.0)),
    )
    report = link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=faces, number_callouts=bubbles
    )
    by_face = {r.room_face_id: r for r in report.room_links}
    assert by_face["rf-1"].linked_room_name == "COLD ROOM"
    assert by_face["rf-2"].linked_room_name is None
    assert report.commercial_authority_granted is False


def test_a15_a16_a24_hyphenated_finish_codes_epoxy_vs_equipment_zone_exclusion() -> None:
    rooms = (
        FloorExclusionRoomCandidate("f-cold", "pf-cold", "rf-cold", "d1", "r1", _SHA, "1", "vp-1", _SQ1),
        FloorExclusionRoomCandidate("f-equip", "pf-equip", "rf-equip", "d1", "r1", _SHA, "1", "vp-1", _SQ2),
    )
    legend_defs = (
        FinishLegendDefinitionInput("def-ep", "d1", "r1", _SHA, "2", "EP-01", "Seamless epoxy floor screed"),
        FinishLegendDefinitionInput("def-eq", "d1", "r1", _SHA, "2", "EX-02", "Equipment zone excluded from contract"),
    )
    obs = (
        FloorFinishLabelObservation("o-ep", "d1", "r1", _SHA, "1", "vp-1", "EP\u201301", (50.0, 50.0)),
        FloorFinishLabelObservation("o-eq", "d1", "r1", _SHA, "1", "vp-1", "EX 02", (170.0, 50.0)),
    )
    report = link_green_exclusions_and_epoxy_labels(
        rooms=rooms,
        green_witnesses=(),
        label_observations=obs,
        finish_legend_definitions=legend_defs,
    )
    by_floor = {r.canonical_floor_id: r for r in report.room_records}
    assert by_floor["f-cold"].classification == CLASS_EPOXY_LABEL_ONLY
    assert by_floor["f-cold"].linked_finish_codes == ("EP01",)
    assert by_floor["f-equip"].classification == CLASS_EXCLUSION_LABEL_ONLY
    assert by_floor["f-equip"].linked_finish_codes == ("EX02",)
    assert report.commercial_quantity_allowed is False


def test_a15_conflicting_hyphenated_and_compact_legend_codes_fail_closed() -> None:
    room = FloorExclusionRoomCandidate("f-1", "pf-1", "rf-1", "d1", "r1", _SHA, "1", "vp-1", _SQ1)
    conflicting_defs = (
        FinishLegendDefinitionInput("d-a", "d1", "r1", _SHA, "2", "EP-01", "Epoxy screed"),
        FinishLegendDefinitionInput("d-b", "d1", "r1", _SHA, "2", "EP01", "Vinyl plank"),
    )
    obs = FloorFinishLabelObservation("o-1", "d1", "r1", _SHA, "1", "vp-1", "EP01", (50.0, 50.0))
    report = link_green_exclusions_and_epoxy_labels(
        rooms=(room,),
        green_witnesses=(),
        label_observations=(obs,),
        finish_legend_definitions=conflicting_defs,
    )
    assert "EP01" in report.conflicting_legend_codes
    assert report.room_records[0].classification == CLASS_CONFLICT
    assert report.room_records[0].status == EvidenceResolutionStatus.CONFLICT
