"""Unlabelled parallel strokes can be topology-only wall-face candidates."""
from __future__ import annotations

from pb_layered_wall_doorway_room_ring_shadow import (
    REASON_NO_WALL_INK,
    REASON_PRIMITIVE_CAP,
    _collect_dark_fill_strips,
    _collect_stroke_pair_strips,
    _collect_wall_end_closing_strips,
    build_layered_wall_doorway_room_rings,
    expand_labelled_stroke_pair_viewports,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32


def _line(x0, y0, x1, y1, color=None):
    import fitz
    return {
        "layer": "",
        "fill": None,
        "color": color,
        "rect": fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
        "items": [("l", fitz.Point(x0, y0), fitz.Point(x1, y1))],
    }


def _stroke_room():
    # 2 pt thick unlabelled walls, no wall layer name.
    return [
        _line(0, 0, 100, 0), _line(0, 2, 100, 2),
        _line(0, 98, 100, 98), _line(0, 100, 100, 100),
        _line(0, 0, 0, 100), _line(2, 0, 2, 100),
        _line(98, 0, 98, 100), _line(100, 0, 100, 100),
    ]


def test_stroke_pairs_stay_off_by_default():
    result = build_layered_wall_doorway_room_rings(_stroke_room(), source_sha256=SHA, page_index=0)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (REASON_NO_WALL_INK,)
    assert result.rings == ()


def _stroke_room_with_jamb_door():
    # East wall interrupted 40..64, closed only by unique jamb caps.
    return [
        _line(0, 0, 100, 0), _line(0, 2, 100, 2),
        _line(0, 98, 100, 98), _line(0, 100, 100, 100),
        _line(0, 0, 0, 100), _line(2, 0, 2, 100),
        _line(98, 0, 98, 40), _line(100, 0, 100, 40),
        _line(98, 64, 98, 100), _line(100, 64, 100, 100),
        _line(98, 40, 100, 40),
        _line(98, 64, 100, 64),
    ]


def test_opt_in_stroke_pairs_are_topology_only_not_a_wall_layer():
    result = build_layered_wall_doorway_room_rings(
        _stroke_room(), source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count >= 4
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    assert all(not ring.takeoff_eligible and ring.diagnostic_only for ring in result.rings)
    closed = [ring for ring in result.rings if ring.status is EvidenceResolutionStatus.CANDIDATE]
    assert closed
    assert closed[0].bounding_wall_path_indices == (0, 1, 2, 3, 4, 5, 6, 7)
    owners = {owner for edge in closed[0].edge_owner_ids for owner in edge}
    assert {f"layered_wall_strip:{index}" for index in range(8)} <= owners


def test_unique_jamb_caps_close_a_stroke_pair_door_gap():
    result = build_layered_wall_doorway_room_rings(
        _stroke_room_with_jamb_door(), source_sha256=SHA, page_index=0,
        stroke_pair_wall_faces=True,
    )
    closed = [ring for ring in result.rings if ring.status is EvidenceResolutionStatus.CANDIDATE]
    assert closed
    assert result.unresolved_gap_count == 0
    assert any(item.kind == "source_stroke_closure" for item in result.closures)
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_three_line_hatch_does_not_invent_a_wall():
    hatch = [_line(0, 0, 80, 0), _line(0, 2, 80, 2), _line(0, 4, 80, 4)]
    result = build_layered_wall_doorway_room_rings(
        hatch, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 0
    assert result.rings == ()


def test_short_unique_stroke_pair_is_still_a_topology_wall():
    short = [_line(0, 0, 10, 0), _line(0, 2, 10, 2)]
    result = build_layered_wall_doorway_room_rings(
        short, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 1
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_furniture_spacing_is_not_a_wall_face():
    far = [_line(0, 0, 80, 0), _line(0, 20, 80, 20)]
    result = build_layered_wall_doorway_room_rings(
        far, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 0


def test_disjoint_inner_face_paths_do_not_own_the_other_substrip():
    rows = [_line(0, 0, 100, 0), _line(0, 2, 40, 2), _line(60, 2, 100, 2)]
    owned = {
        tuple(round(value, 2) for value in strip.polygon.bounds): strip.native_path_indices()
        for strip in _collect_stroke_pair_strips(rows)
    }
    assert owned[(0.0, 0.0, 40.0, 2.0)] == (0, 1)
    assert owned[(60.0, 0.0, 100.0, 2.0)] == (0, 2)


def test_long_outer_face_pairs_each_unique_inner_span():
    drawings = [
        _line(0, 0, 200, 0),
        _line(0, 2, 70, 2),
        _line(130, 2, 200, 2),
        _line(80, 4, 120, 4),
        _line(80, 6, 120, 6),
    ]
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 2
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_adjacent_collinear_partner_spans_both_own_full_merged_strip():
    # Adjacent source paths truly contribute to the same continuous strip.
    # Their refs must BOTH be retained, unlike disjoint noncontributing paths.
    from pb_layered_wall_doorway_room_ring_shadow import _collect_stroke_pair_strips

    drawings = [
        _line(0, 0, 100, 0),
        _line(0, 2, 40, 2),
        _line(40, 2, 100, 2),
    ]
    strips = _collect_stroke_pair_strips(drawings)
    assert len(strips) == 1
    assert strips[0].native_path_indices() == (0, 1, 2)
    assert tuple(round(v, 2) for v in strips[0].polygon.bounds) == (0.0, 0.0, 100.0, 2.0)


def test_split_collinear_opposite_face_is_one_wall_not_rival_partners():
    split = [
        _line(0, 0, 100, 0),
        _line(0, 2, 40, 2),
        _line(40, 2, 100, 2),
        _line(0, 0, 0, 100),
        _line(2, 0, 2, 100),
        _line(0, 98, 100, 98),
        _line(0, 100, 100, 100),
        _line(98, 0, 98, 100),
        _line(100, 0, 100, 100),
    ]
    result = build_layered_wall_doorway_room_rings(
        split, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count >= 4
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    assert all(not ring.takeoff_eligible and ring.diagnostic_only for ring in result.rings)
    closed = next(ring for ring in result.rings if ring.status is EvidenceResolutionStatus.CANDIDATE)
    assert {0, 1, 2} <= set(closed.bounding_wall_path_indices)


def test_multi_neighbourhood_clip_keeps_original_path_indices():
    drawings = _stroke_room() + [_line(400, 0, 400, 20), _line(402, 0, 402, 20)]
    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=SHA,
        page_index=0,
        stroke_pair_wall_faces=True,
        viewport_pdf_pts=[(0, 0, 110, 110), (390, -5, 410, 25)],
    )
    assert result.wall_strip_count >= 5
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_stroke_pair_consumed_drawings_over_primitive_cap_abstain():
    drawings = [_line(0, i, 20, i) for i in range(20001)]
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (REASON_PRIMITIVE_CAP,)
    assert result.rings == ()
    assert result.wall_strip_count == 0


def test_far_fat_path_does_not_cap_a_local_stroke_pair_viewport():
    import fitz
    items = [("l", fitz.Point(4000 + i, 4000 + i), fitz.Point(4001 + i, 4001 + i)) for i in range(20001)]
    fat = {
        "layer": "",
        "fill": None,
        "rect": fitz.Rect(4000, 4000, 24002, 24002),
        "items": items,
    }
    result = build_layered_wall_doorway_room_rings(
        _stroke_room() + [fat],
        source_sha256=SHA,
        page_index=0,
        stroke_pair_wall_faces=True,
        viewport_pdf_pts=(0, 0, 110, 110),
    )
    assert result.reason_codes != (REASON_PRIMITIVE_CAP,)
    assert result.wall_strip_count >= 4
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_halo_shrinks_to_stay_under_the_primitive_cap():
    import fitz
    seed = (40.0, 40.0, 60.0, 60.0)
    # 160 pt halo reaches x=-120; 150 pt stops at x=-110. Park the overflow
    # primitives on that rim so a 160 pt halo exceeds the cap and a slightly
    # smaller one still contains the room.
    overflow = []
    for index in range(20001):
        y = float(index) * 0.01
        overflow.append(_line(-115.0, y, -114.5, y))
    grown = expand_labelled_stroke_pair_viewports(_stroke_room() + overflow, [seed])
    x0, y0, x1, y1 = grown[0]
    assert x0 <= 0.0
    assert y0 <= 0.0
    assert x1 >= 100.0
    assert y1 >= 100.0
    assert x0 > -160.0


def test_labelled_halo_grows_along_connected_stroke_pairs():
    seed = (40.0, 40.0, 60.0, 60.0)
    grown = expand_labelled_stroke_pair_viewports(_stroke_room(), [seed])
    x0, y0, x1, y1 = grown[0]
    assert x0 <= 0.0
    assert y0 <= 0.0
    assert x1 >= 100.0
    assert y1 >= 100.0


def test_three_line_hatch_halo_still_does_not_invent_a_wall():
    hatch = [_line(0, 0, 80, 0), _line(0, 2, 80, 2), _line(0, 4, 80, 4)]
    grown = expand_labelled_stroke_pair_viewports(hatch, [(10.0, 10.0, 20.0, 20.0)])
    assert grown == [(10.0, 10.0, 20.0, 20.0)]


def test_one_path_with_over_cap_items_abstains_before_pairing():
    import fitz
    items = [("l", fitz.Point(i, i), fitz.Point(i + 1, i + 1)) for i in range(20001)]
    fat = {
        "layer": "",
        "fill": None,
        "rect": fitz.Rect(0, 0, 20002, 20002),
        "items": items,
    }
    result = build_layered_wall_doorway_room_rings(
        _stroke_room() + [fat], source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (REASON_PRIMITIVE_CAP,)
    assert result.rings == ()
    assert result.wall_strip_count == 0


def _double_drawn_room():
    # 0.48 pt CAD double-stroke on each 5.76 pt wall face.
    faces = (
        ((0.0, 0.48), True),
        ((5.76, 6.24), True),
        ((93.76, 94.24), True),
        ((99.52, 100.0), True),
        ((0.0, 0.48), False),
        ((5.76, 6.24), False),
        ((93.76, 94.24), False),
        ((99.52, 100.0), False),
    )
    rows = []
    for perps, horiz in faces:
        for perp in perps:
            if horiz:
                rows.append(_line(0, perp, 100, perp, color=(0.0, 0.0, 0.0)))
            else:
                rows.append(_line(perp, 0, perp, 100, color=(0.0, 0.0, 0.0)))
    return rows


def test_double_drawn_black_faces_are_one_wall_not_rival_partners():
    result = build_layered_wall_doorway_room_rings(
        _double_drawn_room(), source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    closed = [ring for ring in result.rings if ring.status is EvidenceResolutionStatus.CANDIDATE]
    assert closed
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_tessellated_black_shorts_merge_into_a_topology_wall():
    rows = []
    for x0 in range(0, 100, 10):
        rows.append(_line(x0, 0, x0 + 9.9, 0, color=(0.0, 0.0, 0.0)))
        rows.append(_line(x0, 4, x0 + 9.9, 4, color=(0.0, 0.0, 0.0)))
    strips = _collect_stroke_pair_strips(rows)
    assert len(strips) == 1
    assert strips[0].polygon.bounds[2] - strips[0].polygon.bounds[0] >= 90.0


def test_grey_grid_and_green_hatch_are_not_wall_faces():
    grey = [
        _line(0, y, 80, y, color=(0.5, 0.5, 0.5))
        for y in (0.0, 2.0, 34.0, 36.0)
    ]
    green = [
        _line(0, 0, 10, 10, color=(0.0, 0.5, 0.0)),
        _line(2, 0, 12, 10, color=(0.0, 0.5, 0.0)),
    ]
    result = build_layered_wall_doorway_room_rings(
        grey + green, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 0
    assert result.rings == ()


def _fill_rect(x0, y0, x1, y1, fill):
    import fitz
    return {
        "layer": "",
        "fill": fill,
        "color": None,
        "fill_opacity": 1.0,
        "rect": fitz.Rect(x0, y0, x1, y1),
        "items": [("re", fitz.Rect(x0, y0, x1, y1))],
    }


def _dark_fill_room():
    dark = (0.195, 0.195, 0.195)
    return [
        _fill_rect(0, 0, 100, 5, dark),
        _fill_rect(0, 95, 100, 100, dark),
        _fill_rect(0, 0, 5, 100, dark),
        _fill_rect(95, 0, 100, 100, dark),
    ]


def test_dark_filled_wall_strips_are_topology_walls_white_masks_are_not():
    dark_strips = _collect_dark_fill_strips(_dark_fill_room())
    assert len(dark_strips) == 4
    white = _collect_dark_fill_strips([_fill_rect(0, 0, 400, 300, (1.0, 1.0, 1.0))])
    assert white == []
    result = build_layered_wall_doorway_room_rings(
        _dark_fill_room(), source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    closed = [ring for ring in result.rings if ring.status is EvidenceResolutionStatus.CANDIDATE]
    assert closed
    assert all(not ring.takeoff_eligible for ring in result.rings)


def _u_room_open_south():
    dark = (0.195, 0.195, 0.195)
    return [
        _fill_rect(0, 20, 5, 120, dark),
        _fill_rect(200, 20, 205, 120, dark),
        _fill_rect(0, 115, 205, 120, dark),
    ]


def test_wall_end_stroke_closes_only_when_both_native_ends_meet_major_walls():
    closer = _line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))
    drawings = _u_room_open_south() + [closer]
    supports = _collect_dark_fill_strips(_u_room_open_south())
    assert len(_collect_wall_end_closing_strips(drawings, supports)) == 1
    prolonged = _u_room_open_south() + [_line(5, 20, 400, 20, color=(0.0, 0.0, 0.0))]
    assert _collect_wall_end_closing_strips(prolonged, supports) == []
    open_south = build_layered_wall_doorway_room_rings(
        _u_room_open_south(), source_sha256=SHA, page_index=0,
        stroke_pair_wall_faces=True, wall_end_stroke_closures=True,
    )
    closed_south = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0,
        stroke_pair_wall_faces=True, wall_end_stroke_closures=True,
    )
    assert not any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in open_south.rings)
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in closed_south.rings)
    assert all(not ring.takeoff_eligible for ring in closed_south.rings)
