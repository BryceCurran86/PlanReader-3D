"""A second printed answer is not kept as the first."""
from __future__ import annotations

import fitz

import pb_plan_read_engine_v1228 as reader
import pb_planreader_offline as offline
import pb_vector_geometry_v130 as vector
from pb_3d_surface_editor_v1212 import infer_substrate
from pb_plan_opening_detection_v171 import TextWord, _find_tag_near


def _title_page(*items):
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    for point, text, size in items:
        page.insert_text(point, text, fontsize=size)
    return doc, page


def test_one_title_block_field_is_kept() -> None:
    doc, page = _title_page(
        ((610, 500), "DRAWING NO", 7),
        ((735, 500), "A-205", 10),
        ((610, 520), "DRAWING TITLE", 7),
        ((700, 520), "LEVEL 05 PARTITION PLAN", 11),
        ((610, 545), "SCALE", 7),
        ((700, 545), "1:100", 9),
        ((610, 565), "REV", 7),
        ((700, 565), "B", 9),
    )
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence["drawing_no"] == "A-205"
    assert "PARTITION PLAN" in evidence["drawing_title"].upper()
    assert evidence["scale"] == "1:100"
    assert evidence["revision"] == "B"
    doc.close()


def test_two_title_block_answers_are_not_the_first() -> None:
    doc, page = _title_page(
        ((610, 470), "DRAWING NO", 7),
        ((735, 470), "A-205", 10),
        ((610, 500), "DRAWING NO", 7),
        ((735, 500), "A-206", 10),
        ((610, 520), "DRAWING TITLE", 7),
        ((700, 520), "FLOOR PLAN", 11),
        ((610, 540), "DRAWING TITLE", 7),
        ((700, 540), "NORTH ELEVATION", 11),
        ((610, 555), "SCALE", 7),
        ((700, 555), "1:100", 9),
        ((610, 570), "SCALE", 7),
        ((700, 570), "1:50", 9),
        ((610, 585), "REV", 7),
        ((700, 585), "B", 9),
    )
    # The page is only 595 tall, so the last rows must stay in the title band.
    seeded = {"drawing_no": "KEEP", "scale": "1:20", "drawing_title": "KEEP", "revision": "Z"}
    evidence = reader.spatial_title_block_evidence(page, lambda _page: dict(seeded))
    assert evidence.get("drawing_no", "") == ""
    assert evidence.get("drawing_title", "") == ""
    assert evidence.get("scale", "") == ""
    doc.close()

    doc, page = _title_page(
        ((610, 520), "SCALE", 7),
        ((700, 520), "1:100 / 1:50", 9),
        ((610, 545), "REV", 7),
        ((700, 545), "B", 9),
        ((610, 565), "REV", 7),
        ((735, 565), "C", 9),
    )
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {"scale": "1:20", "revision": "Z"})
    assert evidence.get("scale", "") == ""
    assert evidence.get("revision", "") == ""
    doc.close()


def test_repeated_title_block_values_and_revisions_word_stay() -> None:
    doc, page = _title_page(
        ((610, 500), "DRAWING NO", 7),
        ((735, 500), "A-205", 10),
        ((610, 530), "DRAWING NO", 7),
        ((735, 530), "A-205", 10),
        ((610, 555), "SCALE", 7),
        ((700, 555), "1 : 100", 9),
        ((610, 575), "REVISIONS", 8),
    )
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence["drawing_no"] == "A-205"
    assert evidence["scale"] == "1:100"
    assert evidence.get("revision", "") != "S"
    doc.close()


def test_one_unlabelled_code_is_kept_and_two_are_not() -> None:
    doc, page = _title_page(((700, 540), "A-205", 12))
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence.get("drawing_no") == "A-205"
    doc.close()
    doc, page = _title_page(((700, 520), "A-205", 12), ((700, 545), "A-206", 12))
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence.get("drawing_no", "") == ""
    doc.close()


def test_one_drawing_type_line_is_a_title_and_two_are_not() -> None:
    doc, page = _title_page(((700, 540), "FLOOR PLAN", 14))
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence.get("drawing_title", "").upper() == "FLOOR PLAN"
    doc.close()
    doc, page = _title_page(((700, 520), "FLOOR PLAN", 16), ((700, 545), "NORTH ELEVATION", 11))
    evidence = reader.spatial_title_block_evidence(page, lambda _page: {})
    assert evidence.get("drawing_title", "") == ""
    doc.close()


def test_equal_scale_groups_abstain_and_an_agreeing_group_stays() -> None:
    conflict = vector.solve_scale([
        {"method": "printed_scale", "px_per_m": 100.0, "weight": 1},
        {"method": "printed_scale", "px_per_m": 200.0, "weight": 1},
    ])
    assert conflict["px_per_m"] == 0.0
    assert conflict["verified"] is False
    agreed = vector.solve_scale([
        {"method": "dimension_line", "px_per_m": 100.0, "weight": 5},
        {"method": "dimension_line", "px_per_m": 101.0, "weight": 5},
        {"method": "printed_scale", "px_per_m": 100.2, "weight": 1},
    ])
    assert agreed["verified"] is True


def test_two_opening_tags_near_one_point_abstain() -> None:
    one = TextWord("D01", 0, 0, 10, 10)
    same = TextWord("D01", 12, 0, 22, 10)
    other = TextWord("W01", 30, 0, 40, 10)
    assert _find_tag_near(5, 5, [one]) == ("D01", "door")
    assert _find_tag_near(5, 5, [one, same]) == ("D01", "door")
    assert _find_tag_near(5, 5, [one, other]) == ("", "")


def test_two_named_substrates_abstain() -> None:
    assert infer_substrate("Soffit FC sheet") == "SOF"
    assert infer_substrate("Rendered block") == "RBL"
    assert infer_substrate("Rendered block and timber cladding") == "OTHER"
    assert infer_substrate("screen or glass balustrade") == "OTHER"


def _word(text: str) -> dict:
    return {"text": text, "x0": 0, "y0": 0, "x1": 10, "y1": 10}


def test_one_room_material_colour_or_length_is_kept() -> None:
    rooms = offline.detect_rooms(None, words=[_word("BEDROOM"), _word("KITCHEN/DINING")])
    assert [room["label"] for room in rooms] == ["BEDROOM"]
    materials = offline.detect_materials([_word("tiling"), _word("brick/timber")])
    assert [item["keyword"] for item in materials] == ["tiling"]
    colours = offline.detect_colours([_word("white"), _word("grey-green")])
    assert [item["keyword"] for item in colours] == ["white"]
    dimensions = offline.detect_dimensions(None, words=[_word("820mm"), _word("820 or 900")])
    assert [item["text"] for item in dimensions] == ["820mm"]


def test_scale_consensus_checks_every_center_in_every_input_order():
    from itertools import permutations
    readings = [
        {"method": "dimension_line", "px_per_m": value, "weight": 1}
        for value in (100., 103., 106.)
    ]
    # The middle source supports the complete cluster. Skipping a center
    # merely because it lies near the first one loses that source hypothesis.
    for ordering in permutations(readings):
        result = vector.solve_scale(ordering)
        assert result["px_per_m"] == 103.
        assert result["verified"] is True
        assert len(result["evidence"]) == 3


def test_tied_overlapping_scale_hypotheses_cannot_choose_first_or_smallest():
    from itertools import permutations
    readings = [
        {"method": "dimension_line", "px_per_m": value, "weight": 1}
        for value in (100., 103., 106., 109.)
    ]
    for ordering in permutations(readings):
        result = vector.solve_scale(ordering)
        assert result["px_per_m"] == 0.
        assert result["verified"] is False
