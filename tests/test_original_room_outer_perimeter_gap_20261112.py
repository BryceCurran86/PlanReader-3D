"""Generic source topology: an unrelated internal wall break is not an exterior perimeter breach.

3Laurel original p3 has many collinear native-wall hypotheses; these tests
prevent an internal partial partition from vetoing an independently closed
outer ring, while keeping an actual exterior wall interruption unsafe.
These are geometry-only CANDIDATE tests, not physical/metric/customer proofs.
"""
from __future__ import annotations

from pb_layered_wall_doorway_room_ring_shadow import (
    REASON_OPEN_GAP,
    REASON_RING_CLOSED,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32


def _dark_wall(x0, y0, x1, y1):
    import fitz
    return {
        "layer": "Enclosure_WallInternal",
        "fill": (0.12, 0.12, 0.12),
        "color": None,
        "fill_opacity": 1.0,
        "rect": fitz.Rect(x0, y0, x1, y1),
        "items": [("re", fitz.Rect(x0, y0, x1, y1), 1)],
    }


def _wall_box(*, interior_gap: bool, perimeter_gap: bool, transpose: bool = False):
    bounds = (
        [(0, 0, 75, 5), (105, 0, 220, 5)] if perimeter_gap
        else [(0, 0, 220, 5)]
    )
    segments = [
        *bounds,
        (0, 215, 220, 220),
        (0, 0, 5, 220),
        (215, 0, 220, 220),
    ]
    if interior_gap:
        segments += [(25, 80, 75, 85), (105, 80, 175, 85)]
    if transpose:
        segments = [(y0, x0, y1, x1) for x0, y0, x1, y1 in segments]
    return [_dark_wall(*coords) for coords in segments]


def _result(*, interior_gap, perimeter_gap, transpose=False):
    return build_layered_wall_doorway_room_rings(
        _wall_box(interior_gap=interior_gap, perimeter_gap=perimeter_gap, transpose=transpose),
        source_sha256=SHA, page_index=0, dark_painted_wall_source=True,
    )


def test_original_outer_ring_survives_unrelated_internal_collinear_wall_gap():
    without = _result(interior_gap=False, perimeter_gap=False)
    with_internal = _result(interior_gap=True, perimeter_gap=False)
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in without.rings)
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in with_internal.rings)
    assert all(REASON_OPEN_GAP not in r.reason_codes for r in with_internal.rings)
    assert any(REASON_RING_CLOSED in r.reason_codes for r in with_internal.rings)
    assert all(not r.takeoff_eligible and not r.metric_area_issued for r in with_internal.rings)


def test_open_exterior_wall_is_not_rescued_by_an_internal_wall_gap():
    result = _result(interior_gap=True, perimeter_gap=True)
    assert not any(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.rings)
    assert all(not r.takeoff_eligible for r in result.rings)


def test_internal_gap_no_longer_vetoes_axis_swapped_enclosed_region():
    result = _result(interior_gap=True, perimeter_gap=False, transpose=True)
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.rings)
    assert all(not r.commercial_projection_allowed for r in result.rings)


def test_unrelated_collinear_wall_outside_room_does_not_break_closed_ring():
    # Source ink after the end of a fully enclosed room can be collinear with
    # one of its perimeter walls. A gap to that separate wall has only ONE end
    # on this room's outer boundary; the other end belongs to a different
    # construction part and cannot invalidate the completed enclosure.
    drawings = _wall_box(interior_gap=False, perimeter_gap=False)
    # Right wall joins the top at the top's native endpoint, not by an
    # overlapping five-point corner rectangle. The resulting room is still
    # enclosed, but its end touches the collinear exterior gap.
    drawings[0] = _dark_wall(0, 0, 215, 5)
    drawings[3] = _dark_wall(215, 5, 220, 220)
    drawings.append(_dark_wall(265, 0, 325, 5))
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0, dark_painted_wall_source=True,
    )
    assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.rings)
    assert any(REASON_RING_CLOSED in r.reason_codes for r in result.rings)
    assert all(not r.takeoff_eligible for r in result.rings)


def test_only_two_endpoints_on_same_outer_ring_can_veto_as_unclosed_gap():
    from shapely.geometry import Polygon
    from pb_layered_wall_doorway_room_ring_shadow import (
        _Gap, _unresolved_collinear_gap_breaches_outer_ring,
    )
    room = Polygon(((0, 0), (100, 0), (100, 100), (0, 100)))
    def gap(horizontal, band, lo, hi, collinear=True):
        return _Gap(horizontal, band, lo, hi, (1,), (2,), collinear)
    # The unclosed band actually interrupts this external perimeter.
    assert _unresolved_collinear_gap_breaches_outer_ring(room, gap(True, (-1, 1), 20, 80))
    # A second wall run beyond the room is not the other end of THIS room wall.
    assert not _unresolved_collinear_gap_breaches_outer_ring(room, gap(True, (-1, 1), 80, 130))
    # An internal partial divider does not break the independently closed shell.
    assert not _unresolved_collinear_gap_breaches_outer_ring(room, gap(True, (49, 51), 20, 80))
    # Axis rotation preserves the decision.
    assert _unresolved_collinear_gap_breaches_outer_ring(room, gap(False, (-1, 1), 20, 80))
    # A perpendicular-wall end is never evidence of a broken collinear band.
    assert not _unresolved_collinear_gap_breaches_outer_ring(room, gap(True, (-1, 1), 20, 80, False))

def test_ring_gap_decision_is_order_translation_and_scale_invariant():
    import fitz

    original = _wall_box(interior_gap=True, perimeter_gap=False)
    signature_before = tuple((row["layer"], tuple(row["rect"])) for row in original)
    for factor, tx, ty in ((1.0, 40.0, 33.0), (0.5, 0.0, 0.0), (2.0, 0.0, 0.0)):
        altered = []
        for row in original:
            rect = row["rect"]
            new = fitz.Rect(
                rect.x0 * factor + tx, rect.y0 * factor + ty,
                rect.x1 * factor + tx, rect.y1 * factor + ty,
            )
            altered.append({**row, "rect": new, "items": [("re", new, 1)]})
        result = build_layered_wall_doorway_room_rings(
            list(reversed(altered)), source_sha256=SHA, page_index=0,
            dark_painted_wall_source=True,
        )
        assert any(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.rings)
        assert all(not r.takeoff_eligible and not r.commercial_projection_allowed for r in result.rings)
    assert tuple((row["layer"], tuple(row["rect"])) for row in original) == signature_before
