"""Shared source-owned closed physical wall-face graph prerequisite.

Authoritative physical geometry safety gate for 3Laurel room finish and ceiling customer issuers:
- pb_three_laurel_vinyl_floor_customer.py
- pb_three_laurel_wet_area_floor_customer.py
- pb_three_laurel_wall_tile_customer.py
- pb_three_laurel_ceiling_customer.py

Replaces isolated, duplicated span/corner heuristics with a single, shared source-owned
closed physical wall-face cycle prerequisite. Enforces fail-closed:
1. Rejects pure text-dump decoys lacking authentic CAD structural primitives.
2. Rejects non-wall layer strokes (e.g., Annotation_Dimensions, Annotation_General, Grid, Title).
3. Rejects schedule table labels (e.g. area schedule listings with 'M2' or 'm²').
4. Rejects open-bottom rooms (such as the 5th-gen 35 pt gap adversarial decoy in #4354).
5. Rejects disconnected stroke sets lacking closed physical corner junctions or evidenced openings.
6. Rejects unrelated isolated fills/marks outside the candidate room envelope.
7. Preserves authentic 3Laurel room enclosures across all customer trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import fitz

DISALLOWED_LAYERS = (
    "annotation_dimensions",
    "annotation_general",
    "annotation_floorplan",
    "dimensions",
    "dimension",
    "dim",
    "grid",
    "title_block",
    "titleblock",
    "border",
    "marker_section",
    "marker_elevationexterior",
    "text",
)

AUTHENTIC_WALL_LAYERS = (
    "enclosure_wallinternal",
    "enclosure_wallexternal",
    "a-wall",
    "wall",
)


@dataclass(frozen=True)
class RoomWallFaceEnclosureWitness:
    enclosed: bool
    reason: str
    room_label: str
    label_rect: Optional[tuple[float, float, float, float]] = None
    native_wall_drawing_indices: tuple[int, ...] = ()
    wall_layers: tuple[str, ...] = ()
    viewport_rect: Optional[tuple[float, float, float, float]] = None
    bounding_box: Optional[tuple[float, float, float, float]] = None
    primitives_authenticated: bool = False
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False


def _spans_continuous(
    segments: Sequence[tuple[float, float]],
    target_start: float,
    target_end: float,
    tol: float = 4.0,
) -> bool:
    """Check if a sequence of collinear 1D intervals continuously covers [target_start, target_end] with gaps <= tol."""
    if not segments:
        return False
    segs = sorted((min(s[0], s[1]), max(s[0], s[1])) for s in segments)
    cur_start, cur_end = segs[0]
    if cur_start > target_start + tol:
        return False
    for s in segs[1:]:
        if s[0] <= cur_end + tol:
            cur_end = max(cur_end, s[1])
        else:
            if cur_end >= target_end - tol:
                return True
            cur_start, cur_end = s
            if cur_start > target_start + tol:
                return False
    return cur_end >= target_end - tol


def witness_room_wall_face_enclosure(
    page: fitz.Page,
    label: str,
    *,
    search_radius: float = 250.0,
    min_span: float = 20.0,
    corner_tol: float = 12.0,
) -> RoomWallFaceEnclosureWitness:
    """Witness that a candidate room label is enclosed by a connected physical wall-face cycle.

    Parameters:
        page: fitz.Page containing the floor plan vectors and text.
        label: Room label string (e.g. 'MEDIA', 'BED 2', 'BATHROOM', etc.).
        search_radius: Maximum PDF point radius around the label centroid to search.
        min_span: Minimum required wall span width in PDF points.
        corner_tol: Maximum tolerance in PDF points for corner junctions.

    Returns:
        RoomWallFaceEnclosureWitness describing the authentic CAD physical wall-face cycle
        evidence, or fail-closed reason.
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
                if abs(w[1] - y0) < 5 and abs(w[0] - x1) < 150:
                    text_upper = w[4].upper()
                    if "M2" in text_upper or "M²" in w[4] or "m²" in w[4] or "AREA:" in text_upper:
                        is_schedule = True
                        break
            if not is_schedule:
                matches.append(fitz.Rect(x0, y0, x1, y1))

    if not matches:
        return RoomWallFaceEnclosureWitness(
            enclosed=False,
            reason="room_label_not_found_on_page",
            room_label=label,
        )

    drawings = page.get_drawings() or []

    for label_rect in matches:
        cx = (label_rect.x0 + label_rect.x1) / 2.0
        cy = (label_rect.y0 + label_rect.y1) / 2.0

        h_lines: list[tuple[float, float, float, int, str]] = []  # min_x, max_x, y, drawing_idx, layer
        v_lines: list[tuple[float, float, float, int, str]] = []  # x, min_y, max_y, drawing_idx, layer

        for d_idx, d in enumerate(drawings):
            layer = str(d.get("layer") or "")
            layer_lower = layer.lower()

            # Reject non-wall layers (e.g. dimensions, annotations, grid lines)
            if any(disallowed in layer_lower for disallowed in DISALLOWED_LAYERS):
                continue

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
                        h_lines.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2.0, d_idx, layer))
                    elif dx <= 1.0 and abs((x1 + x2) / 2.0 - cx) < search_radius:
                        v_lines.append(((x1 + x2) / 2.0, min(y1, y2), max(y1, y2), d_idx, layer))

        # Require candidate walls in all four cardinal directions relative to room centroid
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
        for ht in h_above:
            for hb in h_below:
                left_x = max(ht[0], hb[0])
                right_x = min(ht[1], hb[1])
                if right_x - left_x < min_span:
                    continue

                top_y = ht[2]
                bottom_y = hb[2]

                # Ensure centroid is strictly enclosed inside candidate perimeter
                if not (left_x - corner_tol <= cx <= right_x + corner_tol and top_y - corner_tol <= cy <= bottom_y + corner_tol):
                    continue

                # Collinear left vertical lines
                vl_candidates = [
                    vl for vl in v_left
                    if abs(vl[0] - left_x) <= corner_tol
                ]
                vl_segs = [(vl[1], vl[2]) for vl in vl_candidates]
                if not _spans_continuous(vl_segs, top_y, bottom_y, tol=corner_tol):
                    continue

                # Collinear right vertical lines
                vr_candidates = [
                    vr for vr in v_right
                    if abs(vr[0] - right_x) <= corner_tol
                ]
                vr_segs = [(vr[1], vr[2]) for vr in vr_candidates]
                if not _spans_continuous(vr_segs, top_y, bottom_y, tol=corner_tol):
                    continue

                # Verify structural CAD primitives (fills, curves, or thick strokes)
                # MUST be physically associated with this room boundary (not an isolated dot outside)
                margin = 8.0
                envelope_rect = fitz.Rect(left_x - margin, top_y - margin, right_x + margin, bottom_y + margin)

                associated_fills = 0
                associated_curves = 0
                associated_thick = 0
                wall_layers_found: set[str] = set()

                wall_drawings_indices = {ht[3], hb[3]} | {vl[3] for vl in vl_candidates} | {vr[3] for vr in vr_candidates}
                for idx in wall_drawings_indices:
                    d = drawings[idx]
                    ly = d.get("layer")
                    if ly:
                        wall_layers_found.add(ly)
                    w = d.get("width") or 0.0
                    if w >= 0.25:
                        associated_thick += 1

                for d_idx, d in enumerate(drawings):
                    r = d.get("rect")
                    if not r:
                        continue
                    # Primitive must touch or fall within the room envelope
                    if envelope_rect.intersects(r):
                        if d.get("fill") is not None:
                            associated_fills += 1
                        w = d.get("width") or 0.0
                        if w >= 0.25:
                            associated_thick += 1
                        for it in d.get("items", ()):
                            if it[0] == "c":
                                associated_curves += 1

                # Reject text-only decoys or isolated geometry lacking CAD primitives associated with room
                if associated_fills == 0 and associated_curves == 0 and associated_thick == 0:
                    continue

                return RoomWallFaceEnclosureWitness(
                    enclosed=True,
                    reason="authenticated_physical_wall_cycle",
                    room_label=label,
                    label_rect=(label_rect.x0, label_rect.y0, label_rect.x1, label_rect.y1),
                    native_wall_drawing_indices=tuple(sorted(wall_drawings_indices)),
                    wall_layers=tuple(sorted(wall_layers_found)),
                    viewport_rect=(0.0, 0.0, float(page.rect.width), float(page.rect.height)),
                    bounding_box=(left_x, top_y, right_x, bottom_y),
                    primitives_authenticated=True,
                    physical_wall_authenticated=True,
                    measurement_authorized=False,
                )

    return RoomWallFaceEnclosureWitness(
        enclosed=False,
        reason="no_closed_physical_wall_cycle_found",
        room_label=label,
    )


def is_room_enclosed_by_physical_wall_faces(
    page: fitz.Page,
    label: str,
    *,
    search_radius: float = 250.0,
    min_span: float = 20.0,
    corner_tol: float = 12.0,
) -> bool:
    """Verify that a candidate room label is enclosed by a connected physical wall-face cycle."""
    witness = witness_room_wall_face_enclosure(
        page,
        label,
        search_radius=search_radius,
        min_span=min_span,
        corner_tol=corner_tol,
    )
    return witness.enclosed
