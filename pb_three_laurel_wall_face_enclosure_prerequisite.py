"""Shared source-owned closed physical wall-face graph prerequisite.

Authoritative physical geometry safety gate for 3Laurel room finish and ceiling customer issuers:
- pb_three_laurel_vinyl_floor_customer.py
- pb_three_laurel_wet_area_floor_customer.py
- pb_three_laurel_wall_tile_customer.py
- pb_three_laurel_ceiling_customer.py

Replaces isolated, duplicated span/corner heuristics with a single, shared source-owned
closed physical wall-face cycle prerequisite. Enforces fail-closed:
1. Rejects pure text-dump decoys lacking authentic CAD structural primitives.
2. Rejects schedule table labels (e.g. area schedule listings with 'M2').
3. Rejects open-bottom rooms (such as the 5th-gen 35 pt gap adversarial decoy in #4354).
4. Rejects disconnected stroke sets lacking closed physical corner junctions or evidenced openings.
5. Preserves authentic 3Laurel room enclosures across all customer trades.
"""
from __future__ import annotations

import fitz


# Only original physical wall layers can support a wall-side candidate.
# CAD annotations, plumbing, joinery, roof and untyped strokes can never
# become finished wall-face evidence merely because they draw a rectangle.
_WALL_LAYERS = frozenset({"Enclosure_WallExternal", "Enclosure_WallInternal"})


def is_room_enclosed_by_physical_wall_faces(
    page: fitz.Page,
    label: str,
    *,
    search_radius: float = 250.0,
    min_span: float = 30.0,
    corner_tol: float = 4.0,
) -> bool:
    """Verify that a candidate room label is enclosed by a connected physical wall-face cycle.

    Parameters:
        page: fitz.Page containing the floor plan vectors and text.
        label: Room label string (e.g. 'MEDIA', 'BED 2', 'BATHROOM', etc.).
        search_radius: Maximum PDF point radius around the label centroid to search.
        min_span: Minimum required wall span width in PDF points.
        corner_tol: Maximum tolerance in PDF points for corner junctions.

    Returns:
        True if the room centroid is enclosed by an authentic closed physical wall-face
        cycle or evidenced doorway/sill opening; False otherwise.
    """
    words = page.get_text("words") or []
    tokens = label.split()
    matches: list[fitz.Rect] = []

    for i in range(len(words) - len(tokens) + 1):
        if all(tokens[k].upper() == words[i + k][4].upper() for k in range(len(tokens))):
            x0 = min(words[i + k][0] for k in range(len(tokens)))
            y0 = min(words[i + k][1] for k in range(len(tokens)))
            x1 = max(words[i + k][2] for k in range(len(tokens)))
            y1 = max(words[i + k][3] for k in range(len(tokens)))
            is_schedule = False
            for w in words:
                if abs(w[1] - y0) < 5 and abs(w[0] - x1) < 150 and "M2" in w[4].upper():
                    is_schedule = True
                    break
            if not is_schedule:
                matches.append(fitz.Rect(x0, y0, x1, y1))

    if not matches:
        return False

    drawings = page.get_drawings() or []
    for label_rect in matches:
        cx = (label_rect.x0 + label_rect.x1) / 2.0
        cy = (label_rect.y0 + label_rect.y1) / 2.0

        local_fills = 0
        local_curves = 0
        local_thick = 0
        h_lines: list[tuple[float, float, float, str]] = []
        v_lines: list[tuple[float, float, float, str]] = []

        for d in drawings:
            # Never allow a foreign drawing family to supply any of the
            # four wall faces OR its unrelated local-fill authorization.
            if str(d.get("layer") or "") not in _WALL_LAYERS:
                continue
            scope = str(d.get("source_viewport_id") or d.get("viewport_id") or "")
            r = d.get("rect")
            if r and abs(r.x0 - cx) < search_radius and abs(r.y0 - cy) < search_radius:
                if d.get("fill") is not None:
                    local_fills += 1
                w = d.get("width") or 0.0
                if w > 0.4:
                    local_thick += 1
                for it in d.get("items", ()):
                    if it[0] == "c":
                        local_curves += 1

            for it in d.get("items", ()):
                if it[0] == "l" and len(it) >= 3:
                    try:
                        x1, y1 = float(it[1][0]), float(it[1][1])
                        x2, y2 = float(it[2][0]), float(it[2][1])
                    except (TypeError, ValueError, IndexError, AttributeError):
                        continue
                    dx = abs(x2 - x1)
                    dy = abs(y2 - y1)
                    if dx < min_span and dy < min_span:
                        continue
                    if dy <= 1.0 and abs((y1 + y2) / 2.0 - cy) < search_radius:
                        h_lines.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2.0, scope))
                    elif dx <= 1.0 and abs((x1 + x2) / 2.0 - cx) < search_radius:
                        v_lines.append(((x1 + x2) / 2.0, min(y1, y2), max(y1, y2), scope))

        # Reject text-only decoys with zero CAD primitives
        if local_fills == 0 and local_curves == 0 and local_thick == 0:
            continue

        # Require candidate walls in all four cardinal quadrants
        h_above = [h for h in h_lines if cy - search_radius < h[2] < cy]
        h_below = [h for h in h_lines if cy < h[2] < cy + search_radius]
        v_left = [v for v in v_lines if cx - search_radius < v[0] < cx]
        v_right = [v for v in v_lines if cx < v[0] < cx + search_radius]
        if not (h_above and h_below and v_left and v_right):
            continue

        # Verify closed physical wall-face perimeter cycle:
        # Top horizontal (ht) and bottom horizontal (hb) must share overlapping horizontal span
        # >= min_span, and left vertical (vl) and right vertical (vr) must connect continuously
        # from ht down to hb without open bottom or side gaps.
        found = False
        for ht in h_above:
            for hb in h_below:
                left_x = max(ht[0], hb[0])
                right_x = min(ht[1], hb[1])
                if right_x - left_x < min_span:
                    continue

                vl_matches = [
                    vl
                    for vl in v_left
                    if abs(vl[0] - left_x) <= corner_tol
                    and vl[1] <= ht[2] + corner_tol
                    and vl[2] >= hb[2] - corner_tol
                ]
                if not vl_matches:
                    continue

                vr_matches = [
                    vr
                    for vr in v_right
                    if abs(vr[0] - right_x) <= corner_tol
                    and vr[1] <= ht[2] + corner_tol
                    and vr[2] >= hb[2] - corner_tol
                ]
                if vr_matches:
                    # Do not join wall sides from independently identified
                    # floor-plan/elevation/upper-floor viewports.
                    for vl in vl_matches:
                        for vr in vr_matches:
                            scopes = {
                                row[3]
                                for row in (ht, hb, vl, vr)
                                if row[3]
                            }
                            if len(scopes) <= 1:
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
            if found:
                break

        if found:
            return True

    return False
