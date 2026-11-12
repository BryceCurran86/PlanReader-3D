"""Unlabelled parallel strokes can be topology-only wall-face candidates."""
from __future__ import annotations

from pb_layered_wall_doorway_room_ring_shadow import (
    REASON_NO_WALL_INK,
    REASON_PRIMITIVE_CAP,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32


def _line(x0, y0, x1, y1):
    import fitz
    return {
        "layer": "",
        "fill": None,
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


def test_three_line_hatch_does_not_invent_a_wall():
    hatch = [_line(0, 0, 80, 0), _line(0, 2, 80, 2), _line(0, 4, 80, 4)]
    result = build_layered_wall_doorway_room_rings(
        hatch, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 0
    assert result.rings == ()


def test_furniture_spacing_is_not_a_wall_face():
    far = [_line(0, 0, 80, 0), _line(0, 20, 80, 20)]
    result = build_layered_wall_doorway_room_rings(
        far, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count == 0


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
