"""Two printed answers inside one face, note, or schedule are not the first."""
from pb_accuracy_v13_engines_v145 import (
    attach_room_labels,
    detect_openings,
    semantic_assignment,
)


def test_one_label_in_a_face_stays_and_two_do_not() -> None:
    face = ((0, 0), (4, 0), (4, 3), (0, 3))
    one = attach_room_labels([face], [{"x": 1, "y": 1, "label": "Bedroom"}, {"x": 2, "y": 1, "label": "Bedroom"}])
    assert one[0]["label"] == "Bedroom"
    two = attach_room_labels([face], [{"x": 1, "y": 1, "label": "Bedroom"}, {"x": 2, "y": 1, "label": "Living"}])
    assert two[0]["label"] == ""


def test_one_opening_kind_stays_and_a_door_and_window_tag_does_not() -> None:
    assert detect_openings([{"tag": "D01", "swing": True}])[0]["kind"] == "door"
    assert detect_openings([{"tag": "W01", "parallel_lines": 3}])[0]["kind"] == "window"
    assert detect_openings([{"tag": "D01 W01"}])[0]["kind"] == "opening"


def test_two_schedule_rows_do_not_lend_the_first_description() -> None:
    rows = [
        {"code": "PT1", "description": "white paint"},
        {"code": "PT1", "description": "grey paint"},
    ]
    result = semantic_assignment("PT1", rows)
    assert result["status"] == "review"
    assert result["description"] is None
    assert semantic_assignment("PT1", [rows[0]])["description"] == "white paint"
