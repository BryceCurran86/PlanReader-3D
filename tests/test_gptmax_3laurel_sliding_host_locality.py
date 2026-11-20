"""Source sliding-door host locality must preserve every eligible source aperture."""
import hashlib
import fitz

from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from pb_source_sliding_door_footprint_continuity import detect_exterior_sliding_door_footprint_bridges


def test_existing_450pt_gap_and_1pt_label_margin_imply_filter():
    for start in (-100.0, 0.0, 170.0, 1040.0):
        for gap in (8.0, 50.0, 200.0, 450.0):
            end = start + gap
            for label in (start - 1.0, start, (start + end) / 2, end, end + 1.0):
                assert label - 451.0 <= start <= label + 1.0
                assert label - 1.0 <= end <= label + 451.0


def test_original_three_laurel_native_sliders_unchanged():
    original = require_original_3laurel().read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=original, filetype="pdf") as doc:
        page = doc[2]
        drawings = tuple(page.get_drawings())
        words = tuple(page.get_text("words"))
    doors = detect_exterior_sliding_door_footprint_bridges(
        drawings, words, page_index=2,
    )
    assert len(doors) == 3
    assert {(r.first_host_path_id, r.second_host_path_id, r.axis) for r in doors} == {
        (1214, 1215, "h"),
        (1628, 1629, "v"),
        (2850, 2851, "v"),
    }
    assert all(not d.measurement_authorized for d in doors)
