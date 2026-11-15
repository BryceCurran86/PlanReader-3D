"""Source-painted D13 door gate must be translation invariant and fail closed."""
from __future__ import annotations

import pb_source_cross_view_floor_correspondence_shadow as m


def _segment(a, b, c, d):
    return {"x1": a, "y1": b, "x2": c, "y2": d}


def _case(dx=0.0, dy=0.0):
    box_t = (20.0 + dx, 100.0 + dy, 174.0 + dx, 350.0 + dy)
    box_s = (100.0 + dx, 124.0 + dy, 254.0 + dx, 374.0 + dy)
    # 154 pt room width / 2200 mm => 0.07 pt/mm.
    # 920 mm schedule opening => 64.4 pt between the painted inner jambs.
    t = [
        _segment(50, 100, 120, 100),
        _segment(50, 93.5, 120, 93.5),
        _segment(50, 93.5, 50, 100),
        _segment(120, 93.5, 120, 100),
        _segment(52.8, 93.5, 52.8, 100),
        _segment(117.2, 93.5, 117.2, 100),
        _segment(117.2, 100, 117.2, 164.4),
    ] + [
        _segment(61 + i, 101 + i, 105 + i, 148 + i)
        for i in range(5)
    ]
    s = [
        _segment(130, 117.5, 130, 124),
        _segment(200, 117.5, 200, 124),
        _segment(150, 123.5, 150, 374),
        _segment(165, 123.5, 165, 374),
    ]
    def shift(seg):
        return _segment(seg["x1"] + dx, seg["y1"] + dy,
                        seg["x2"] + dx, seg["y2"] + dy)
    words = (
        (30 + dx, 130 + dy, 45 + dx, 145 + dy, "PWD"),
        (150 + dx, 94 + dy, 163 + dx, 100 + dy, "D13"),
    )
    return dict(support_segments=[shift(q) for q in s],
                target_segments=[shift(q) for q in t],
                words_tgt=words, box_sup=box_s, box_tgt=box_t,
                door_callout="D13", scheduled_width_mm=920.0,
                room_width_mm=2200.0)


def test_d13_physical_gate_painted_geometry_translates():
    base = m._authenticate_d13_physical_doorway_boundary(**_case())
    shifted = m._authenticate_d13_physical_doorway_boundary(**_case(100, 200))
    assert base is not None
    assert shifted is not None
    assert abs(base["clear_opening_width_pdf_pt"] - 64.4) < 0.01
    assert shifted["jamb_gap_target_pdf_pts"] == (150.0, 220.0)
    assert shifted["jamb_gap_support_pdf_pts"] == (230.0, 300.0)
    assert shifted["threshold_inside_face_y_pdf_pt"] == 300.0


def test_d13_physical_gate_rejects_missing_door_leaf_and_finish_jamb():
    c = _case()
    c["target_segments"] = [
        s for s in c["target_segments"]
        if not (s["x1"] == 117.2 and s["y1"] == 100 and s["y2"] == 164.4)
    ]
    assert m._authenticate_d13_physical_doorway_boundary(**c) is None
    c = _case()
    c["support_segments"] = c["support_segments"][1:]
    assert m._authenticate_d13_physical_doorway_boundary(**c) is None


def test_d13_physical_gate_rejects_unbound_room_label():
    c = _case()
    c["words_tgt"] = (c["words_tgt"][1],)
    assert m._authenticate_d13_physical_doorway_boundary(**c) is None
