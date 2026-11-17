"""Original cavity-slider clear aperture is distinct from physical wall pocket."""
from copy import deepcopy
import hashlib

import fitz
import pytest

from pb_source_native_cavity_slider_jamb_shadow import (
    match_source_native_cavity_sliders,
)
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def _scene():
    row = lambda rect, rgb: {
        "layer": "Enclosure_WallInternal", "type": "f",
        "fill": (rgb,) * 3, "rect": rect,
    }
    drawings = [
        row((0, 100, 40, 103), 0),
        row((63, 100, 88, 103), 0),
        row((40, 99.6, 41.1, 103.6), 1),
        row((61.9, 99.6, 63, 103.6), 1),
        {"layer": "Enclosure_WallInternal", "type": "s",
         "fill": None, "color": (0, 0, 0),
         "items": [("l", (51., 101.5), (77., 101.5))]},
    ]
    words = [
        (36, 105, 46, 113, "720", 0, 0, 0),
        (50, 105, 60, 113, "CS", 0, 0, 1),
    ]
    return drawings, words


def test_unique_original_host_jamb_leaf_and_label_produce_only_topology_witness():
    drawings, words = _scene()
    found = match_source_native_cavity_sliders(drawings, words, page_index=2)
    assert len(found) == 1
    rec = found[0]
    assert rec.host_path_ids == (0, 1)
    assert rec.jamb_path_ids == (2, 3)
    assert rec.leaf_path_id == 4
    assert rec.printed_width_mm == 720
    assert rec.clear_interval_pdf_pts == (40, 63)
    assert rec.horizontal
    assert not rec.physical_opening_authenticated
    assert not rec.customer_quantity_authorized
    assert rec.to_dict()["customer_quantity_authorized"] is False


@pytest.mark.parametrize("missing", [0, 1, 2, 3, 4])
def test_missing_any_native_wall_jamb_or_leaf_abstains(missing):
    drawings, words = _scene()
    drawings.pop(missing)
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)


def test_label_only_must_not_invent_door():
    _, words = _scene()
    assert not match_source_native_cavity_sliders([], words, page_index=2)


def test_black_wall_through_clear_aperture_prevents_false_closure():
    drawings, words = _scene()
    drawings.append({
        "layer": "Enclosure_WallInternal", "type": "f",
        "fill": (0, 0, 0), "rect": (39, 100, 64, 103),
    })
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)


def test_duplicate_jamb_or_leaf_abstains_instead_of_arbitrary_choice():
    drawings, words = _scene()
    drawings.append(deepcopy(drawings[2]))
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)
    drawings, words = _scene()
    drawings.append(deepcopy(drawings[4]))
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)


def test_foreign_layer_and_wrong_word_width_do_not_infer_aperture():
    drawings, words = _scene()
    drawings[0]["layer"] = "Annotation_FloorPlan"
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)
    drawings, words = _scene()
    words[0] = (36, 105, 46, 113, "1,400", 0, 0, 0)
    assert not match_source_native_cavity_sliders(drawings, words, page_index=2)


def test_private_sha_verified_original_has_six_distinct_cs_source_thresholds():
    p = require_original_3laurel()
    raw = p.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as original:
        d, words = original[2].get_drawings(), original[2].get_text("words")
    found = match_source_native_cavity_sliders(d, words, page_index=2)
    assert len(found) == 6
    assert sorted(x.printed_width_mm for x in found) == [720, 720, 720, 870, 870, 1200]
    assert {x.cs_word_index for x in found} == {330, 332, 340, 342, 364, 367}
    assert len({x.leaf_path_id for x in found}) == 6
    assert len({idx for x in found for idx in x.host_path_ids}) == 12
    assert len({idx for x in found for idx in x.jamb_path_ids}) == 18
    assert all(x.physical_opening_authenticated is False for x in found)
    assert all(x.customer_quantity_authorized is False for x in found)
