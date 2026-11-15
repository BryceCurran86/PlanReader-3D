"""Source-native framed doorway proof for an authenticated cross-sheet room.

This helper does not issue commercial quantities or trust caller-supplied source
authority. Its consumer must authenticate PDF bytes, page role and registration.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence


def authenticate_source_native_room_doorway(
    *,
    support_segments: Sequence[Mapping[str, float]],
    target_segments: Sequence[Mapping[str, float]],
    words_tgt: Sequence[Sequence[Any]],
    box_sup: tuple[float, float, float, float],
    box_tgt: tuple[float, float, float, float],
    door_callout: str,
    scheduled_width_mm: float,
    room_width_mm: float,
    room_label: str,
) -> Optional[dict[str, Any]]:
    """Find exactly one painted frame, leaf, swing and matched finish threshold."""
    if not support_segments or not target_segments or not words_tgt:
        return None
    tx0, ty0, tx1, ty1 = box_tgt
    sx0, sy0, sx1, sy1 = box_sup
    if room_width_mm <= 0 or scheduled_width_mm <= 0 or tx1 <= tx0 or ty1 <= ty0:
        return None
    scale = (tx1 - tx0) / room_width_mm
    nominal_clear_pt = scheduled_width_mm * scale

    def lines(segments):
        horiz, vert, diag = [], [], []
        for s in segments:
            x1, y1, x2, y2 = (float(s[k]) for k in ("x1", "y1", "x2", "y2"))
            xlo, xhi = min(x1, x2), max(x1, x2)
            ylo, yhi = min(y1, y2), max(y1, y2)
            if abs(y2 - y1) < 0.15 and xhi - xlo > 0.1:
                horiz.append((xlo, xhi, (y1 + y2) / 2))
            elif abs(x2 - x1) < 0.15 and yhi - ylo > 0.1:
                vert.append(((x1 + x2) / 2, ylo, yhi))
            elif xhi - xlo > 0.1 and yhi - ylo > 0.1:
                diag.append((xlo, xhi, ylo, yhi))
        return horiz, vert, diag

    th, tv, td = lines(target_segments)
    _, sv, _ = lines(support_segments)
    if not th or not tv or not sv:
        return None

    def close(a, b, tolerance=0.16):
        return abs(a - b) <= tolerance

    def vertical_edge(x, bottom, top, verticals):
        return any(
            close(vx, x) and close(lo, bottom) and close(hi, top)
            for vx, lo, hi in verticals
        )

    candidates = set()
    for left, right, inside_y in th:
        outer_width = right - left
        if not close(inside_y, ty0, 0.55):
            continue
        if not (nominal_clear_pt < outer_width <= nominal_clear_pt + 12.0):
            continue
        if left < tx0 - 3.0 or right > tx1 + 3.0:
            continue
        for out_left, out_right, outside_y in th:
            depth = inside_y - outside_y
            if not 3.0 <= depth <= 12.0:
                continue
            if not (close(out_left, left) and close(out_right, right)):
                continue
            if not (
                vertical_edge(left, outside_y, inside_y, tv)
                and vertical_edge(right, outside_y, inside_y, tv)
            ):
                continue
            # The clear frame opening is found from independent painted
            # returns, not an expected coordinate or scheduled area.
            def continuous_inner_returns(x_min, x_max):
                # CAD wall/jamb ink is frequently split into multiple
                # collinear strokes at frame-layer intersections. Require
                # complete endpoint-to-endpoint paint, not one long segment.
                found = []
                xs = sorted({x for x, _, _ in tv if x_min < x < x_max})
                for x in xs:
                    intervals = sorted(
                        (lo, hi) for vx, lo, hi in tv
                        if close(vx, x, 1.05)
                        and lo >= outside_y - 0.2
                        and hi <= inside_y + 0.2
                    )
                    if not intervals or intervals[0][0] > outside_y + 0.2:
                        continue
                    covered = intervals[0][1]
                    for lo, hi in intervals[1:]:
                        if lo > covered + 0.2:
                            break
                        covered = max(covered, hi)
                    if covered >= inside_y - 0.2:
                        # Both frame endpoints must be painted on this
                        # same anchored jamb axis. Nearby layer fragments
                        # can bridge the middle, but cannot invent an axis.
                        has_outer_anchor = any(
                            close(vx, x, 0.12) and close(lo, outside_y, 0.2)
                            for vx, lo, hi in tv
                        )
                        has_inner_anchor = any(
                            close(vx, x, 0.12) and close(hi, inside_y, 0.2)
                            for vx, lo, hi in tv
                        )
                        if has_outer_anchor and has_inner_anchor:
                            found.append(x)
                return found

            inner_left = continuous_inner_returns(left + 0.5, left + 5.0)
            inner_right = continuous_inner_returns(right - 5.0, right - 0.5)
            for ix0 in inner_left:
                for ix1 in inner_right:
                    clear_pt = ix1 - ix0
                    if clear_pt <= 0 or abs(clear_pt / scale - scheduled_width_mm) > 3.0:
                        continue
                    has_leaf = any(
                        close(x, ix1) and close(lo, inside_y)
                        and close(hi, inside_y + clear_pt, 0.35)
                        for x, lo, hi in tv
                    )
                    swing_chords = sum(
                        ix0 - 0.5 <= xlo < xhi <= ix1 + 0.5
                        and inside_y - 0.3 <= ylo < yhi <= inside_y + clear_pt + 1.0
                        for xlo, xhi, ylo, yhi in td
                    )
                    if not has_leaf or swing_chords < 5:
                        continue

                    # The registration already comes from independently
                    # ranked painted source lines. Both PDF page geometries
                    # must agree with that same verified translation.
                    sx_left, sx_right = left + sx0 - tx0, right + sx0 - tx0
                    sy_inside, sy_outside = inside_y + sy0 - ty0, outside_y + sy0 - ty0
                    if not (
                        vertical_edge(sx_left, sy_outside, sy_inside, sv)
                        and vertical_edge(sx_right, sy_outside, sy_inside, sv)
                    ):
                        continue
                    tile_ends = sum(
                        sx0 + 10.0 <= x <= sx1 - 10.0
                        and sy_inside - 3.0 <= lo <= sy_inside + 0.9
                        and sy1 - 1.5 <= hi <= sy1 + 1.0
                        for x, lo, hi in sv
                    )
                    if tile_ends < 2:
                        continue
                    candidates.add((left, right, ix0, ix1, inside_y))

    room_words = [
        w for w in words_tgt
        if len(w) >= 5 and str(w[4]).strip().upper() == room_label.upper()
        and tx0 <= float(w[0]) <= tx1 and ty0 <= float(w[1]) <= ty1
    ]
    callout_words = [
        w for w in words_tgt
        if len(w) >= 5 and str(w[4]).strip().upper() == door_callout.upper()
        and tx0 - 10.0 <= float(w[0]) <= tx1 + 10.0
        and ty0 - 15.0 <= float(w[1]) <= ty0 + 12.0
    ]
    if len(room_words) != 1 or len(callout_words) != 1 or len(candidates) != 1:
        return None

    left, right, ix0, ix1, inside_y = next(iter(candidates))
    return {
        "clear_opening_width_pdf_pt": round(ix1 - ix0, 2),
        "jamb_gap_target_pdf_pts": (round(left, 2), round(right, 2)),
        "jamb_gap_support_pdf_pts": (
            round(left + sx0 - tx0, 2),
            round(right + sx0 - tx0, 2),
        ),
        "threshold_inside_face_y_pdf_pt": round(inside_y, 2),
        "threshold_aligned_with_internal_face": True,
        "threshold_deduction_m2": 0.0,
    }
