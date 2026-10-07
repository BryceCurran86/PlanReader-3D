from types import SimpleNamespace

from pb_live_physical_net_wall_integration import _merge_documented_room_area_evidence


def _ev(value, unit="m2"):
    return SimpleNamespace(normalized_value=value, unit=unit)


def test_documented_room_area_merge_accepts_single_authority():
    same=_ev(12.5)
    assert _merge_documented_room_area_evidence(
        same_view_by_record={"room-1":same},
        cross_view_by_record={},
    ) == {"room-1":same}


def test_documented_room_area_merge_requires_exact_agreement():
    same=_ev(12.5)
    cross=_ev(12.5)
    out=_merge_documented_room_area_evidence(
        same_view_by_record={"room-1":same},
        cross_view_by_record={"room-1":cross},
    )
    assert out == {"room-1":same}


def test_documented_room_area_merge_suppresses_numeric_conflict():
    assert _merge_documented_room_area_evidence(
        same_view_by_record={"room-1":_ev(12.5)},
        cross_view_by_record={"room-1":_ev(12.6)},
    ) == {}


def test_documented_room_area_merge_suppresses_unit_conflict():
    assert _merge_documented_room_area_evidence(
        same_view_by_record={"room-1":_ev(12.5,"m2")},
        cross_view_by_record={"room-1":_ev(12.5,"ft2")},
    ) == {}
