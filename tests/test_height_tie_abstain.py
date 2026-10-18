"""Two top-ranked height readings are not the first one."""
from pb_height_evidence_v150 import HeightEvidence, resolve_height, resolve_room_heights


def _reading(height: float, evidence_id: str) -> HeightEvidence:
    return HeightEvidence(
        id=evidence_id,
        height_type="floor_to_ceiling",
        raw_text=f"{height} m",
        height_m=height,
        extraction_method="dimension_parse",
        confidence=0.8,
        status="Measured",
        priority=2,
        anchor=(1.0, 1.0),
    )


def test_one_top_height_stays_and_a_tie_does_not() -> None:
    one, evidence = resolve_height([_reading(2.4, "a"), _reading(2.4, "b")])
    assert one == 2.4
    assert evidence.status == "Measured"
    tied, conflict = resolve_height([_reading(2.4, "a"), _reading(3.0, "b")])
    assert conflict.status == "Conflict"
    assert tied != 2.4
    rooms = resolve_room_heights(
        [{"room_ref": "R1", "label": "Living", "polygon": [(0, 0), (4, 0), (4, 4), (0, 4)]}],
        [_reading(2.4, "a"), _reading(3.0, "b")],
    )
    assert rooms["R1"]["height_status"] == "Conflict"
    assert rooms["R1"]["height_m"] is None
