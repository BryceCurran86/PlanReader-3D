"""One printed field: a second different value is not the first value."""
from __future__ import annotations

from pb_drawing_ocr_evidence_layer import DrawingEvidenceParser, EvidenceStatus
from pb_drawing_reading_v1226 import enhanced_title_block_evidence
from pb_legend_register_v1227 import PAGE_TYPE, build_legend_register
from pb_live_floor_plan_level_identity import _normalized_level_label
from pb_material_schedule_v1222 import _infer_substrate, build_material_dictionary
from pb_raster_schedule_extractor import GenericScheduleTableExtractor
from pb_selected_evidence_floor_v1226 import _rebuild_dictionary_item


class _Rect:
    width = 1000.0
    height = 1000.0


class _Page:
    def __init__(self, text: str) -> None:
        self.rect = _Rect()
        self._text = text

    def get_text(self, mode: str):
        if mode == "blocks":
            return [(700.0, 800.0, 980.0, 860.0, self._text, 0, 0)]
        return ""


def _read(text: str, base: dict | None = None) -> dict:
    return enhanced_title_block_evidence(_Page(text), lambda _page: dict(base or {}))


def test_one_drawing_number_is_kept_and_two_numbers_are_blank() -> None:
    one = _read("DRAWING NO A-101\nDRAWING NO A-101")
    two = _read("DRAWING NO A-101\nSHEET NO A-102", {"drawing_no": "A-100"})
    assert one["drawing_no"] == "A-101"
    assert two["drawing_no"] == ""


def test_one_scale_is_kept_and_two_scales_are_blank() -> None:
    one = _read("SCALE 1:100\nSCALE 1 : 100")
    two = _read("SCALE 1:100\nSCALE 1:50", {"scale": "1:20"})
    assert one["scale"] == "1:100"
    assert two["scale"] == ""


def test_one_revision_is_kept_and_revisions_is_not_revision_s() -> None:
    one = _read("REV A\nREV A")
    heading = _read("REVISIONS\nREV C")
    two = _read("REV A\nREV B", {"revision": "Z"})
    assert one["revision"] == "A"
    assert heading["revision"] == "C"
    assert two["revision"] == ""


def test_one_drawing_title_is_kept_and_two_titles_are_blank() -> None:
    one = _read("DRAWING TITLE: Ground Floor Plan")
    two = _read("DRAWING TITLE: Ground Floor Plan\nDRAWING TITLE: Roof Plan", {"drawing_title": "Old"})
    assert one["drawing_title"] == "Ground Floor Plan"
    assert two["drawing_title"] == ""
    assert "Ground Floor Plan" not in two["text"].splitlines()[0] or two["text"].startswith("DRAWING")


def test_schedule_line_keeps_one_pair_and_abstains_on_two() -> None:
    one = DrawingEvidenceParser.parse_schedule_line("W7: 1500 x 1200 - 7 No.")
    repeated = DrawingEvidenceParser.parse_schedule_line("W7: 1500 x 1200 1500 x 1200 - 7 No. 7 No.")
    two_sizes = DrawingEvidenceParser.parse_schedule_line("W7: 1500 x 1200 or 900 x 2100 - 7 No.")
    two_counts = DrawingEvidenceParser.parse_schedule_line("W7: 1500 x 1200 - 7 No. or 11 No.")
    assert one is not None and one.dimensions == [1500.0, 1200.0] and one.quantity == 7.0
    assert one.status == EvidenceStatus.CONFIRMED.value
    assert repeated is not None and repeated.dimensions == [1500.0, 1200.0] and repeated.quantity == 7.0
    assert two_sizes is not None and two_sizes.dimensions is None
    assert two_sizes.status == EvidenceStatus.UNRESOLVED.value
    assert two_counts is not None and two_counts.quantity is None
    assert two_counts.status == EvidenceStatus.UNRESOLVED.value


def test_quantity_and_dimension_cells_keep_one_value() -> None:
    extractor = GenericScheduleTableExtractor()
    assert extractor._parse_quantity_string("7 No.") == 7.0
    assert extractor._parse_quantity_string("7 No. 7 No.") == 7.0
    assert extractor._parse_quantity_string("7 No. or 11 No.") is None
    assert extractor._parse_dimensions_string("1500 x 1200") == [1500.0, 1200.0]
    assert extractor._parse_dimensions_string("1500 x 1200 or 900 x 2100") is None
    assert extractor._unique_labelled_count("W1 7 No. 11 No.", r"\b(\d{1,3})\s*(?:no\.?s?|nos?)\b") is None
    assert extractor._unique_labelled_count("W1 7 No.", r"\b(\d{1,3})\s*(?:no\.?s?|nos?)\b") == 7.0


def test_viewport_label_with_two_storeys_is_not_a_level() -> None:
    assert _normalized_level_label("GROUND FLOOR PLAN") == ("ground_floor", 0)
    assert _normalized_level_label("LEVEL 2 PLAN") == ("level_2", 2)
    assert _normalized_level_label("GROUND FLOOR PLAN AND LEVEL 2 PLAN") is None


def test_conflicting_material_definition_does_not_publish_the_first_description() -> None:
    class App:
        def lquery(self, sql, params=()):
            return [
                {"id": 1, "page_label": "A900", "page_type": "Finishes Schedule", "extracted_text": "EC1 Linea cladding", "image_path": "", "document_id": 1, "page_no": 1, "render_zoom": 1},
                {"id": 2, "page_label": "A901", "page_type": "Finishes Schedule", "extracted_text": "EC1 Rendered blockwork", "image_path": "", "document_id": 1, "page_no": 2, "render_zoom": 1},
            ]

    state = build_material_dictionary(App(), 4)
    assert state["dictionary"]["EC1"]["status"] == "Conflict"
    assert state["dictionary"]["EC1"]["description"] == ""
    rebuilt = _rebuild_dictionary_item(
        "EC1",
        [
            {"description": "Linea cladding", "substrate": "Lineaboard Cladding"},
            {"description": "Rendered blockwork", "substrate": "Rendered / Blockwork"},
        ],
    )
    assert rebuilt is not None
    assert rebuilt["description"] == ""
    assert rebuilt["status"] == "Conflict"


def test_two_substrate_families_are_not_the_first_family() -> None:
    assert _infer_substrate("James Hardie Linea cladding") == "Lineaboard Cladding"
    assert _infer_substrate("rendered blockwork") == "Rendered / Blockwork"
    assert _infer_substrate("Linea cladding and rendered blockwork") == ""


def test_conflicting_legend_description_is_not_published() -> None:
    class App:
        def __init__(self) -> None:
            self.settings = {}

        def lquery(self, sql, params=()):
            return [
                {"id": 1, "page_no": 1, "page_label": "A-001", "page_type": PAGE_TYPE, "extracted_text": "LEGEND\nEC7 - JAMES HARDIE LINEA EXTERNAL CLADDING", "document_id": 1, "image_path": "", "render_zoom": 1, "selected": 1},
                {"id": 2, "page_no": 2, "page_label": "A-002", "page_type": PAGE_TYPE, "extracted_text": "LEGEND\nEC7 - RENDERED BLOCKWORK", "document_id": 1, "image_path": "", "render_zoom": 1, "selected": 1},
            ]

        def set_workspace_setting(self, workspace_id, key, value):
            self.settings[(workspace_id, key)] = value

        def now_stamp(self):
            return "2026-10-17T00:00:00"

    import pb_legend_register_v1227 as legend

    original = legend.auto._pdf_word_lines
    legend.auto._pdf_word_lines = lambda _app, _page: []
    try:
        state = build_legend_register(App(), 1)
    finally:
        legend.auto._pdf_word_lines = original
    assert state["dictionary"]["EC7"]["status"] == "Conflict"
    assert state["dictionary"]["EC7"]["description"] == ""
