"""Protected original 3Laurel page-3 internal door symbol source regression.

If private PDF is absent in public CI the existing resolver marks NOT_RUN;
a wrong SHA always fails. No private drawing bytes are committed.
"""
import hashlib
import fitz

from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers
from pb_source_internal_door_completeness_shadow import inspect_source_internal_door_completeness


def test_authenticated_original_internal_swing_and_cs_callouts_have_distinct_counts():
    original = require_original_3laurel()
    data = original.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[2]
        paths = tuple(page.get_drawings())
        words = tuple(page.get_text("words"))
    assert len(paths) == 11030
    hosted = detect_source_internal_swing_room_barriers(paths, words, page_index=2)
    review = inspect_source_internal_door_completeness(paths, words, page_index=2)
    assert review.swing_symbol_count == 7
    assert review.hosted_swing_count == 7
    assert review.unhosted_swing_symbol_count == 0
    assert review.cavity_slider_callout_count == 6
    assert review.cavity_slider_geometry_authenticated_count == 0
    assert len(hosted) == 7
    assert len({r.swing_arc_path_id for r in hosted}) == 7
    assert set((2195, 2337, 2591, 2629)).issubset(
        {r.swing_arc_path_id for r in hosted}
    )
    assert sorted(
        m.label_width_mm for m in review.marks
        if m.kind == "native_cavity_slider_callout"
    ) == [720, 720, 720, 870, 870, 1200]
    assert not review.physical_openings_authenticated
    assert not review.measurement_authorized
    assert all(not r.physical_wall_authenticated and not r.measurement_authorized
               for r in hosted)
    assert all(m.status == "NEEDS_JAMB_WITNESS" for m in review.marks
               if m.kind == "native_cavity_slider_callout")
