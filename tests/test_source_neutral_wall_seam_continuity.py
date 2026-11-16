"""Exact native-grey source fills, never endpoint snapping or wall quantities."""

import fitz

from pb_source_neutral_wall_seam_continuity import (
    detect_source_neutral_wall_seams as detect,
)

LAYER = "Enclosure_WallExternal"


def _paint(bounds, *, tone=0.0, layer=LAYER):
    return {
        "rect": fitz.Rect(*bounds),
        "layer": layer,
        "fill": (tone, tone, tone),
        "items": (),
    }


def _horizontal():
    return [
        _paint((0, 0, 10, 2.5)),
        _paint((10.5, 0, 20.5, 2.5)),
        _paint((10, 0, 10.5, 2.5), tone=0.415686),
    ]


def test_source_neutral_full_thickness_infill_bridges_only_topology():
    rows = detect(_horizontal(), page_index=2)
    assert len(rows) == 1
    b = rows[0]
    assert b.first_host_path_id == 0 and b.second_host_path_id == 1
    assert b.neutral_fill_path_ids == (2,)
    assert b.bounds_pdf_pts == (10.0, 0.0, 10.5, 2.5)
    assert b.axis == "h" and b.page_index == 2
    assert b.physical_wall_authenticated is False
    assert b.measurement_authorized is False
    assert b.to_dict()["kind"] == "source_neutral_grey_wall_seam_continuity_only"


def test_split_gray_source_paint_exactly_tiles_gap():
    d = _horizontal()[:2] + [
        _paint((10, 0, 10.25, 2.5), tone=0.415686),
        _paint((10.25, 0, 10.5, 2.5), tone=0.415686),
    ]
    rows = detect(d)
    assert len(rows) == 1
    assert rows[0].neutral_fill_path_ids == (2, 3)


def test_orthogonal_vertical_seam_is_supported_from_source():
    d = [
        _paint((0, 0, 2.5, 10)),
        _paint((0, 10.5, 2.5, 20.5)),
        _paint((0, 10, 2.5, 10.5), tone=0.415686),
    ]
    rows = detect(d)
    assert len(rows) == 1
    assert rows[0].axis == "v"
    assert rows[0].bounds_pdf_pts == (0.0, 10.0, 2.5, 10.5)


def test_neutral_fill_is_required_not_any_coloured_or_white_drawings():
    d = _horizontal()
    assert detect(d[:2]) == ()
    assert detect(d[:2] + [_paint((10, 0, 10.5, 2.5), tone=1.0)]) == ()
    source_green = _paint((10, 0, 10.5, 2.5), tone=0.415686)
    source_green["fill"] = (0.1, 0.65, 0.1)
    assert detect(d[:2] + [source_green]) == ()
    assert detect(d[:2] + [_paint((10, 0, 10.5, 2), tone=0.415686)]) == ()


def test_gap_is_not_joined_from_arbitrary_nearby_gray_or_unmatched_viewport():
    d = _horizontal()
    d[0]["viewport_id"] = "ground"
    d[2]["viewport_id"] = "elevation"
    assert detect(d) == ()
    d = _horizontal()
    d[2]["layer"] = "Enclosure_Roof"
    assert detect(d) == ()
    d = _horizontal()
    d[1] = _paint((35, 0, 45, 2.5))
    d[2] = _paint((10, 0, 35, 2.5), tone=0.415686)
    assert detect(d) == ()


def test_duplicate_competing_neutral_full_gap_owners_fail_closed():
    d = _horizontal()
    d.append(_paint((10, 0, 10.5, 2.5), tone=0.415686))
    assert detect(d) == ()


def test_short_gray_seam_is_not_a_new_customer_wall_area():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first

    d = _horizontal()
    r = attempt_source_native_outer_wall_first(
        d,
        source_ink_already_scoped=True,
        window_source_drawings=d,
    )
    assert len(r.neutral_wall_seams) == 1
    assert r.status == "ABSTAINED"
    assert r.measurement_authorized is False
    assert r.physical_wall_authenticated is False
