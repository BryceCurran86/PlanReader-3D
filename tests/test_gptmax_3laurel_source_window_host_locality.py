"""Source-window host locality is a necessary bound, never a guessed closure."""
import hashlib
import fitz

from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first


def test_window_gap_locality_is_a_never_drop_bound():
    # Existing gap <= 160pt, and each label center within 2pt of the two
    # endpoints imply the locality inequalities. Source-neutral proof.
    for start in (-150, 0, 100, 800):
        for gap in (2.0, 4.5, 50.0, 160.0):
            end = start + gap
            for label_pos in (start - 2.0, start, (start + end) / 2, end, end + 2.0):
                assert label_pos - 162.0 <= start <= label_pos + 2.0
                assert label_pos - 2.0 <= end <= label_pos + 162.0


def test_original_3laurel_window_preflight_retains_exact_legacy_candidate_set():
    # This is an existing CANDIDATE-only witness inventory, not a score or
    # proof of 20 physical windows. Never upload the private original PDF.
    path = require_original_3laurel()
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=original, filetype="pdf") as document:
        page = document[2]
        drawings = tuple(page.get_drawings())
        words = tuple(page.get_text("words"))
    result = attempt_source_native_outer_wall_first(
        drawings, source_words=words,
        window_source_drawings=drawings, source_page_index=2,
    )
    actual = {(b.left_host_path_id, b.right_host_path_id, b.axis)
              for b in result.window_footprint_bridges}
    assert actual == {
        (1183, 1192, "h"), (1195, 1198, "h"), (1200, 1204, "h"),
        (1202, 1204, "h"), (1206, 1208, "h"), (1210, 1212, "h"),
        (1515, 1517, "v"), (1519, 1520, "v"), (1520, 3359, "h"),
        (1590, 1517, "v"), (1590, 1629, "h"), (1709, 1708, "h"),
        (1784, 1843, "h"), (1787, 1786, "h"), (1842, 1841, "v"),
        (1843, 1842, "v"), (2812, 2811, "h"), (2943, 2942, "h"),
        (2944, 2943, "h"), (3359, 3360, "h"),
    }
    assert result.source_outside_face_walk is not None
    assert result.source_outside_face_walk.enclosed_dwelling_zone_count == 2
    assert result.source_outside_face_walk.other_source_wall_band_count == 0
    assert result.measurement_authorized is False
