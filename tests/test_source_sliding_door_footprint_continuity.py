"""Source ASD / SGD sliding-door topology, never issued wall or frame area."""

import fitz

from pb_source_sliding_door_footprint_continuity import (
    detect_exterior_sliding_door_footprint_bridges as detect,
)

LAYER = "Enclosure_WallExternal"


def _bar(bounds, *, color=0.0, layer=LAYER):
    return {
        "layer": layer,
        "rect": fitz.Rect(*bounds),
        "fill": (color, color, color),
        "items": (),
    }


def _horizontal():
    return [
        _bar((0, 0, 5, 2.5)),
        _bar((45, 0, 50, 2.5)),
        _bar((5, 0.2, 6, 2.6), color=1.0),
        _bar((44, 0.2, 45, 2.6), color=1.0),
        _bar((8, 0.4, 22, 0.9), color=1.0),
        _bar((28, 1.2, 42, 1.7), color=1.0),
    ]


def _vertical():
    return [
        _bar((60, 0, 62.5, 5)),
        _bar((60, 45, 62.5, 50)),
        _bar((60.2, 5, 62.6, 6), color=1.0),
        _bar((60.2, 44, 62.6, 45), color=1.0),
        _bar((60.4, 8, 60.9, 22), color=1.0),
        _bar((61.2, 28, 61.7, 42), color=1.0),
    ]


def test_native_asd_sliding_door_two_hosts_two_caps_two_tracks():
    d = _horizontal()
    rows = detect(d, [(19, 6, 24, 10, "ASD")], page_index=2)
    assert len(rows) == 1
    b = rows[0]
    assert b.axis == "h"
    assert (b.first_host_path_id, b.second_host_path_id) == (0, 1)
    assert b.jamb_cap_path_ids == (2, 3)
    assert b.sliding_track_path_ids == (4, 5)
    assert b.bounds_pdf_pts == (5.0, 0.0, 45.0, 2.5)
    assert b.label_text == "ASD"
    assert b.measurement_authorized is False
    assert b.physical_wall_authenticated is False
    assert b.to_dict()["kind"] == "source_hosted_sliding_door_footprint_continuity_only"


def test_vertical_source_sgd_is_not_a_window():
    rows = detect(_vertical(), [(66, 19, 71, 28, "sgd")])
    assert len(rows) == 1
    assert rows[0].axis == "v"
    assert rows[0].bounds_pdf_pts == (60.0, 5.0, 62.5, 45.0)


def test_assd_schedule_code_is_sliding_footprint_not_window():
    rows = detect(_vertical(), [(66, 19, 71, 28, "ASSD")])
    assert len(rows) == 1
    assert rows[0].label_text == "ASSD"
    assert rows[0].axis == "v"
    assert rows[0].bounds_pdf_pts == (60.0, 5.0, 62.5, 45.0)
    assert rows[0].measurement_authorized is False
    assert rows[0].physical_wall_authenticated is False


def test_missing_source_word_jamb_track_or_wall_must_abstain():
    d = _horizontal()
    word = [(19, 6, 24, 10, "ASD")]
    assert detect(d, ()) == ()
    assert detect(d, [(19, 6, 24, 10, "UNKNOWN")]) == ()
    for missing in range(len(d)):
        assert detect(d[:missing] + d[missing + 1 :], word) == ()


def test_window_not_silent_slider_and_competing_window_label_blocks_join():
    d = _horizontal()
    assert detect(d, [(19, 6, 24, 10, "ASW")]) == ()
    assert detect(d, [(19, 6, 24, 10, "ASD"), (19, 6, 24, 10, "ASW")]) == ()


def test_figured_two_digit_dimension_does_not_block_unique_asd():
    d = _horizontal()
    rows = detect(d, [(19, 6, 24, 10, "ASD"), (19, 11, 22, 14, "21")])
    assert len(rows) == 1
    assert rows[0].label_text == "ASD"
    assert rows[0].measurement_authorized is False
    assert rows[0].physical_wall_authenticated is False


def test_source_viewport_collision_and_intervening_wall_fail_closed():
    d = _horizontal()
    d[0]["viewport_id"] = "floor-plan"
    d[1]["viewport_id"] = "elevation"
    assert detect(d, [(19, 6, 24, 10, "ASD")]) == ()
    d = _horizontal() + [_bar((24, 0, 27, 2.5))]
    assert detect(d, [(19, 6, 24, 10, "ASD")]) == ()


def test_preflight_short_sliding_hosts_remain_candidate_only():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first

    drawings = _horizontal()
    report = attempt_source_native_outer_wall_first(
        drawings,
        source_ink_already_scoped=True,
        window_source_drawings=drawings,
        source_words=[(19, 6, 24, 10, "ASD")],
    )
    assert len(report.sliding_door_footprint_bridges) == 1
    assert report.status == "ABSTAINED"
    assert report.measurement_authorized is False
    assert report.physical_wall_authenticated is False


def test_internal_joinery_does_not_become_exterior_sliding_door():
    d = _horizontal()
    for row in d:
        row["layer"] = "Interior_Joinery"
    assert detect(d, [(19, 6, 24, 10, "ASD")]) == ()


def test_multiple_labels_cannot_reuse_one_host_as_two_real_doors():
    d = _horizontal()
    text = [(19, 6, 24, 10, "ASD"), (19, 6, 24, 10, "SGD")]
    assert detect(d, text) == ()


def test_layerless_sliding_door_detected_via_rails_and_caps():
    d = _horizontal()
    for row in d:
        row["layer"] = ""
    rows = detect(d, [(19, 6, 24, 10, "SD2")])
    assert len(rows) == 1
    assert rows[0].label_text == "SD2"
    assert rows[0].first_host_path_id == 0
    assert rows[0].second_host_path_id == 1
    assert rows[0].bounds_pdf_pts == (5.0, 0.0, 45.0, 2.5)


def test_source_assd_stack_slider_requires_full_host_caps_and_tracks():
    # Source label "ASSD" is separate from "ASD"; the full hosted
    # physical opening witness, never the acronym, provides topology.
    d = _vertical()
    rows = detect(d, [(66, 19, 71, 28, "ASSD")], page_index=2)
    assert len(rows) == 1
    bridge = rows[0]
    assert bridge.label_text == "ASSD"
    assert bridge.axis == "v"
    assert (bridge.first_host_path_id, bridge.second_host_path_id) == (0, 1)
    assert bridge.jamb_cap_path_ids == (2, 3)
    assert bridge.sliding_track_path_ids == (4, 5)
    assert not bridge.physical_wall_authenticated
    assert not bridge.measurement_authorized
    for absent in range(len(d)):
        assert detect(
            d[:absent] + d[absent + 1:],
            [(66, 19, 71, 28, "ASSD")],
        ) == ()


def test_assd_not_guessed_from_similar_text_or_competing_windows():
    d = _vertical()
    assert detect(d, [(66, 19, 71, 28, "ASS")]) == ()
    assert detect(d, [(66, 19, 71, 28, "ASSD?")]) == ()
    assert detect(d, [(66, 19, 71, 28, "ASSD"), (66, 19, 71, 28, "ASW")]) == ()
    d[0]["viewport_id"] = "floor-plan"
    d[1]["viewport_id"] = "elevation"
    assert detect(d, [(66, 19, 71, 28, "ASSD")]) == ()


def test_original_3laurel_p3_source_assd_closes_only_hosted_aperture():
    import hashlib
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
    from pb_source_native_wall_body_junction_graph_shadow import _unique_source_wall_bars

    path = require_original_3laurel()
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[2]
        drawings = page.get_drawings()
        words = page.get_text("words")
        bars = _unique_source_wall_bars(drawings)
        before = (len(drawings), len(words))
        bridges = detect(drawings, words, page_index=2, wall_bars=bars)
        after = (len(page.get_drawings()), len(page.get_text("words")))
    assert before == after
    assd = [row for row in bridges if row.label_text.lower() == "assd"]
    assert len(assd) == 1
    opening = assd[0]
    # The two original painted wall hosts are separately source-positive;
    # no project-specific path lookup appears in the producer.
    assert opening.first_host_path_id != opening.second_host_path_id
    assert opening.jamb_cap_path_ids[0] != opening.jamb_cap_path_ids[1]
    assert len(opening.sliding_track_path_ids) >= 2
    assert opening.bounds_pdf_pts[0] < opening.bounds_pdf_pts[2]
    assert opening.bounds_pdf_pts[1] < opening.bounds_pdf_pts[3]
    assert not opening.physical_wall_authenticated
    assert not opening.measurement_authorized
