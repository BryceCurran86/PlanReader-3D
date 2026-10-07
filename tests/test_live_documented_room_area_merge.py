from types import SimpleNamespace

from pb_live_physical_net_wall_integration import _merge_documented_room_area_evidence


def _ev(value, unit="m2"):
    return SimpleNamespace(normalized_value=value, unit=unit)


def test_documented_room_area_merge_accepts_same_view_fallback():
    same = _ev(12.5)
    assert _merge_documented_room_area_evidence(
        same_view_by_record={"room-1": same},
        cross_view_by_record={},
    ) == {"room-1": same}


def test_documented_room_area_merge_preserves_existing_cross_view_authority():
    same = _ev(12.5)
    cross = _ev(12.5)
    out = _merge_documented_room_area_evidence(
        same_view_by_record={"room-1": same},
        cross_view_by_record={"room-1": cross},
    )
    assert out == {"room-1": cross}


def test_same_view_disagreement_cannot_erase_proven_cross_view_area():
    same = _ev(12.6)
    cross = _ev(12.5)
    out = _merge_documented_room_area_evidence(
        same_view_by_record={"room-1": same},
        cross_view_by_record={"room-1": cross},
    )
    assert out == {"room-1": cross}


def test_same_view_unit_disagreement_cannot_erase_proven_cross_view_area():
    same = _ev(12.5, "ft2")
    cross = _ev(12.5, "m2")
    out = _merge_documented_room_area_evidence(
        same_view_by_record={"room-1": same},
        cross_view_by_record={"room-1": cross},
    )
    assert out == {"room-1": cross}


def test_same_view_only_record_is_retained_alongside_cross_view_records():
    same = _ev(8.0)
    cross = _ev(12.5)
    out = _merge_documented_room_area_evidence(
        same_view_by_record={"room-2": same},
        cross_view_by_record={"room-1": cross},
    )
    assert out == {
        "room-1": cross,
        "room-2": same,
    }
