"""One source-measured m² witness cannot authenticate two different rooms."""
from dataclasses import replace
from pb_room_area_quantity import build_room_area_quantities
from tests.test_room_area_quantity_v2 import (
    _room,_context,_document,_viewport,_entity,_explicit_area,
)


def _run(first_ev,second_ev):
    rooms=(
        _room("room-a",points=((0,0),(10,0),(10,10),(0,10))),
        _room("room-b",points=((20,0),(30,0),(30,10),(20,10))),
    )
    return build_room_area_quantities(
        rooms=rooms,
        entities_by_room_id={
            "room-a":_entity("room-a",ids=("room-ev",first_ev.evidence_id)),
            "room-b":_entity("room-b",ids=("room-ev",second_ev.evidence_id)),
        },
        context=_context(),document=_document(ids=tuple(dict.fromkeys(
            ("room-ev",first_ev.evidence_id,second_ev.evidence_id)
        ))),
        viewport=_viewport(),page_no=1,
        explicit_area_evidence_by_room_id={
            "room-a":first_ev,"room-b":second_ev,
        },
    )


def test_distinct_original_area_receipts_remain_independently_documented():
    rows=_run(
        _explicit_area(7.5,evidence_id="area-source-a"),
        _explicit_area(8.5,evidence_id="area-source-b"),
    )
    assert len(rows)==2
    assert all(not row.abstained for row in rows)
    assert [r.value for r in rows] == [7.5,8.5]


def test_reused_exact_figured_area_source_quarantines_both_physical_rooms():
    original=_explicit_area(7.5,evidence_id="same-original-measure")
    rows=_run(original,replace(original))
    assert len(rows)==2
    assert all(row.abstained for row in rows)
    assert all("original_area_evidence_owned_by_multiple_rooms" in row.blocking_reasons
               for row in rows)


def test_one_original_measure_reissued_with_different_value_also_quarantines_both():
    original=_explicit_area(7.5,evidence_id="same-original-measure")
    rows=_run(original,replace(original,normalized_value=13.5))
    assert all(row.abstained for row in rows)
