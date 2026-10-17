"""Rekeyed evidence IDs cannot reuse both original figured source dimensions."""
from dataclasses import dataclass
from pb_source_room_area_receipt_index import unique_source_room_area_evidence_by


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    metadata: dict


@dataclass(frozen=True)
class Record:
    source_room_face_record_id: str
    physical_room_id: str
    area_evidence: Evidence


def _row(n, pair):
    return Record(
        source_room_face_record_id=f"original-face-{n}",
        physical_room_id=f"physical-room-{n}",
        area_evidence=Evidence(
            evidence_id=f"figured-area-{n}",
            metadata={"figured_dimension_ids":list(pair)},
        ),
    )


def _index(*rows):
    return unique_source_room_area_evidence_by(
        tuple(rows),key="physical_room_id",record_type=Record
    )


def test_two_original_rooms_with_two_independent_dimension_pairs_are_available():
    rows=(_row("a",("h-1","v-1")),_row("b",("h-2","v-2")))
    indexed=_index(*rows)
    assert set(indexed)=={"physical-room-a","physical-room-b"}


def test_two_rooms_reusing_same_original_figured_axes_both_abstain():
    rows=(_row("a",("h-1","v-1")),_row("b",("v-1","h-1")))
    for source_rows in (rows,rows[::-1]):
        assert dict(_index(*source_rows)) == {}


def test_single_dimension_axis_can_be_shared_when_pair_is_independent():
    indexed=_index(
        _row("a",("h-shared","v-a")),
        _row("b",("h-shared","v-b")),
    )
    assert len(indexed)==2


def test_missing_figured_pair_does_not_invent_numeric_measurements():
    row=_row("a",("h-1","v-1"))
    untyped=Record(row.source_room_face_record_id,row.physical_room_id,
                   Evidence("source-text-area",{}))
    indexed=_index(untyped)
    assert "physical-room-a" in indexed
    # This index does not grant metric value. Its caller must prove the area.


def test_malformed_present_source_figured_pair_must_not_be_treated_as_missing():
    original = _row("a", ("h", "v"))
    for wrong in ([], ["h"], ["h", "h"], "h,v", ["h", 12], None, True):
        untrusted = Record(
            original.source_room_face_record_id, original.physical_room_id,
            Evidence("original-figured-area-a", {"figured_dimension_ids": wrong}),
        )
        assert dict(_index(untrusted)) == {}


def test_explicit_source_area_without_figured_pair_can_still_be_indexed():
    original = _row("a", ("h", "v"))
    genuine_explicit = Record(
        original.source_room_face_record_id, original.physical_room_id,
        Evidence("source-explicit-printed-area", {}),
    )
    assert tuple(_index(genuine_explicit)) == ("physical-room-a",)
