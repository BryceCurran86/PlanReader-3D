"""PlanReader v1.3.0 native vector geometry and scale-evidence engine.

This module keeps measurement deterministic. It extracts native PDF primitives,
constructs a snapped geometry graph, identifies likely wall-face pairs, derives
closed-space candidates, and aggregates independent scale evidence. AI remains a
semantic helper and is never allowed to invent measured geometry here.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

VERSION = "1.3.0"
SETTING_PREFIX = "vector_geometry_v130_"
_DIM_RE = re.compile(r"(?<![:\d])(?P<num>\d{2,5}(?:\.\d{1,3})?)\s*(?P<unit>mm|m)?(?!\s*[:\d])", re.I)
_SCALE_RE = re.compile(r"(?<!\d)1\s*:\s*(\d{2,4})(?!\d)")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _angle_deg(seg: Dict[str, Any]) -> float:
    return math.degrees(math.atan2(seg["y2"] - seg["y1"], seg["x2"] - seg["x1"])) % 180.0


def _angle_delta(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _segment_length(seg: Dict[str, Any]) -> float:
    return math.hypot(seg["x2"] - seg["x1"], seg["y2"] - seg["y1"])


def _bbox(seg: Dict[str, Any]) -> Tuple[float, float, float, float]:
    return min(seg["x1"], seg["x2"]), min(seg["y1"], seg["y2"]), max(seg["x1"], seg["x2"]), max(seg["y1"], seg["y2"])


def _dimension_m(token: Any) -> Optional[float]:
    text = str(token or "").strip().lower().replace(",", "")
    match = _DIM_RE.fullmatch(text)
    if not match:
        return None
    value = _num(match.group("num"))
    unit = str(match.group("unit") or "").lower()
    if unit == "mm" or (not unit and value >= 100):
        value /= 1000.0
    elif unit != "m":
        return None
    return value if 0.25 <= value <= 150.0 else None


def _normalize_scissor(scissor: Any) -> Optional[Tuple[float, float, float, float]]:
    """Return a stable page-space clip rectangle, or None when unknown."""
    if scissor is None:
        return None
    try:
        x0, y0, x1, y1 = map(float, (scissor.x0, scissor.y0, scissor.x1, scissor.y1))
    except Exception:
        try:
            x0, y0, x1, y1 = map(float, scissor)
        except Exception:
            return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


@dataclass(frozen=True)
class _ClipShapeProof:
    """Exact active clip-shape proof from the extended drawing stream."""

    scissor: Optional[Tuple[float, float, float, float]]
    exact_rect: Optional[Tuple[float, float, float, float]]


@dataclass(frozen=True)
class _ClipAssociation:
    clip_present: bool
    scissor: Optional[Tuple[float, float, float, float]]
    exact_shape_known: bool
    exact_rect: Optional[Tuple[float, float, float, float]]


@dataclass(frozen=True)
class _ClipAssociationTable:
    """Extended-drawing clip association result.

    available is False when the extended API failed. by_seqno maps a matched
    drawing seqno to both the legacy effective scissor and an independent
    exact-shape proof. scissor remains diagnostic only: an active clip is
    authority-safe only when every active clip path is proven to be an
    axis-aligned rectangle from the actual extended drawing items.
    """

    available: bool
    by_seqno: Dict[int, _ClipAssociation]


def _normalize_axis_aligned_quad(
    quad: Any,
    *,
    tolerance: float = 1e-4,
) -> Optional[Tuple[float, float, float, float]]:
    """Return the exact bbox only when quad proves an axis-aligned rectangle."""
    try:
        points = [
            (float(quad.ul.x), float(quad.ul.y)),
            (float(quad.ur.x), float(quad.ur.y)),
            (float(quad.ll.x), float(quad.ll.y)),
            (float(quad.lr.x), float(quad.lr.y)),
        ]
    except Exception:
        return None
    if not all(math.isfinite(v) for point in points for v in point):
        return None

    def _clusters(values: Sequence[float]) -> List[float]:
        ordered = sorted(float(value) for value in values)
        groups: List[List[float]] = []
        for value in ordered:
            if not groups or abs(value - groups[-1][-1]) > tolerance:
                groups.append([value])
            else:
                groups[-1].append(value)
        return [sum(group) / len(group) for group in groups]

    xs = _clusters([point[0] for point in points])
    ys = _clusters([point[1] for point in points])
    if len(xs) != 2 or len(ys) != 2:
        return None
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax - xmin <= tolerance or ymax - ymin <= tolerance:
        return None
    corners = ((xmin, ymin), (xmin, ymax), (xmax, ymin), (xmax, ymax))
    for corner in corners:
        if not any(
            abs(point[0] - corner[0]) <= tolerance
            and abs(point[1] - corner[1]) <= tolerance
            for point in points
        ):
            return None
    return (xmin, ymin, xmax, ymax)


def _exact_rect_from_clip_drawing(
    drawing: Mapping[str, Any],
) -> Optional[Tuple[float, float, float, float]]:
    items = drawing.get("items") or ()
    if len(items) != 1 or not items[0]:
        return None
    item = items[0]
    kind = str(item[0])
    if kind == "re" and len(item) >= 2:
        return _normalize_scissor(item[1])
    if kind == "qu" and len(item) >= 2:
        return _normalize_axis_aligned_quad(item[1])
    return None


def _intersect_exact_rects(
    rects: Sequence[Tuple[float, float, float, float]],
) -> Optional[Tuple[float, float, float, float]]:
    if not rects:
        return None
    x0 = max(rect[0] for rect in rects)
    y0 = max(rect[1] for rect in rects)
    x1 = min(rect[2] for rect in rects)
    y1 = min(rect[3] for rect in rects)
    if x1 < x0 or y1 < y0:
        return None
    return (x0, y0, x1, y1)


def _clip_scissor_by_seqno(pdf_page: Any) -> _ClipAssociationTable:
    """Map drawing seqno values to active clip state and exact shape proof.

    The primary non-extended drawing enumeration remains untouched, preserving
    historical primitive IDs. The separate extended pass is used only to prove
    clip provenance. PyMuPDF scissor is never itself accepted as shape
    authority.
    """
    try:
        extended = pdf_page.get_drawings(extended=True) or []
    except Exception:
        return _ClipAssociationTable(available=False, by_seqno={})

    stack: List[Optional[_ClipShapeProof]] = []
    by_seqno: Dict[int, _ClipAssociation] = {}
    for drawing in extended:
        if not isinstance(drawing, dict):
            continue
        dtype = str(drawing.get("type") or "")
        try:
            level = int(drawing.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        if level < 0:
            level = 0

        if dtype.startswith("clip"):
            while len(stack) > level:
                stack.pop()
            while len(stack) < level:
                stack.append(None)
            proof = _ClipShapeProof(
                scissor=_normalize_scissor(drawing.get("scissor")),
                exact_rect=_exact_rect_from_clip_drawing(drawing),
            )
            if len(stack) == level:
                stack.append(proof)
            else:
                stack[level] = proof
            continue

        seqno = drawing.get("seqno")
        if seqno is None:
            continue
        try:
            seq_key = int(seqno)
        except (TypeError, ValueError):
            continue

        limit = min(len(stack), max(level, 0))
        active = [stack[idx] for idx in range(limit) if stack[idx] is not None]
        if not active:
            by_seqno[seq_key] = _ClipAssociation(
                clip_present=False,
                scissor=None,
                exact_shape_known=True,
                exact_rect=None,
            )
            continue

        effective_scissor = None
        for proof in active:
            if proof is not None and proof.scissor is not None:
                effective_scissor = proof.scissor

        exact_shape_known = all(
            proof is not None and proof.exact_rect is not None for proof in active
        )
        exact_rect = (
            _intersect_exact_rects(
                [proof.exact_rect for proof in active if proof and proof.exact_rect]
            )
            if exact_shape_known
            else None
        )
        by_seqno[seq_key] = _ClipAssociation(
            clip_present=True,
            scissor=effective_scissor,
            exact_shape_known=exact_shape_known,
            exact_rect=exact_rect,
        )
    return _ClipAssociationTable(available=True, by_seqno=by_seqno)


def _resolve_clip_fields(
    *,
    clip_table: _ClipAssociationTable,
    seq_key: Optional[int],
) -> Tuple[
    bool,
    bool,
    Optional[Tuple[float, float, float, float]],
    bool,
    Optional[Tuple[float, float, float, float]],
]:
    """Return clip state without conflating scissor with exact clip geometry."""
    if not clip_table.available or seq_key is None or seq_key not in clip_table.by_seqno:
        return False, False, None, False, None
    association = clip_table.by_seqno[seq_key]
    return (
        True,
        association.clip_present,
        association.scissor,
        association.exact_shape_known,
        association.exact_rect,
    )


def extract_native_page(pdf_page: Any) -> Dict[str, Any]:
    """Extract line primitives, text geometry and PDF layer hints from one page.

    Additive native-rectangle retention: in addition to the per-edge
    ``rect_edge`` segments produced historically (unchanged), native ``re``
    rectangle primitives are ALSO retained as closed ``rects`` with their
    full ``bbox``.  ``rects`` is ADDITIVE metadata — it does not alter the
    existing ``segments`` output contract, so B1 (which consumes
    ``segments``) is unaffected.

    Priority-1 additive provenance (does not change historical ``id`` values):
    ``path_index``, ``item_index``, optional ``edge_index``, explicit
    ``*_present`` flags, native page coordinates retained as fields already
    present, and ``clip`` / ``clip_present`` / ``clip_known`` from a separate
    extended drawings association keyed by ``seqno`` (never invents clip).

    Clip ternary (A1): ``clip_known=True, clip_present=False`` means the
    extended association matched the drawing ``seqno`` and no active clip
    exists. ``clip_known=False`` means association unavailable, seqno missing,
    or unmatched — never evidence of “unclipped”.

    Other graphic presence flags (A3 audit): PyMuPDF ``get_drawings()`` dicts
    always include ``color``, ``fill``, ``width``, ``dashes``, and ``layer``.
    Known absence is ``None`` (or ``""`` for layer); there is no separate
    upstream “field not supplied” state to preserve beyond the existing
    ``*_present`` flags. Clip is the exception because it depends on a
    fallible extended association pass.

    Non-finite native coordinates (A2) are skipped at emission — never
    coerced to zero and never claimed present.
    """
    segments: List[Dict[str, Any]] = []
    rects: List[Dict[str, Any]] = []   # ADDITIVE: closed native rectangles
    drawings = pdf_page.get_drawings() or []
    clip_table = _clip_scissor_by_seqno(pdf_page)
    for draw_index, drawing in enumerate(drawings):
        width = _num(drawing.get("width"), 0.0) if isinstance(drawing, dict) else 0.0
        stroke = drawing.get("color") if isinstance(drawing, dict) else None
        fill = drawing.get("fill") if isinstance(drawing, dict) else None
        layer = str(drawing.get("layer") or drawing.get("oc") or "") if isinstance(drawing, dict) else ""
        dashes = str(drawing.get("dashes") or "") if isinstance(drawing, dict) else ""
        width_present = isinstance(drawing, dict) and "width" in drawing and drawing.get("width") is not None
        stroke_present = isinstance(drawing, dict) and "color" in drawing and stroke is not None
        fill_present = isinstance(drawing, dict) and "fill" in drawing and fill is not None
        layer_present = bool(str(layer).strip())
        dashes_present = bool(str(dashes).strip())
        seqno = drawing.get("seqno") if isinstance(drawing, dict) else None
        try:
            seq_key = int(seqno) if seqno is not None else None
        except (TypeError, ValueError):
            seq_key = None
        (
            clip_known,
            clip_present,
            clip,
            clip_shape_known,
            clip_exact_rect,
        ) = _resolve_clip_fields(
            clip_table=clip_table, seq_key=seq_key
        )

        def _graphic_fields() -> Dict[str, Any]:
            return {
                "width": width,
                "width_present": width_present,
                "stroke": stroke,
                "stroke_present": stroke_present,
                "fill": fill,
                "fill_present": fill_present,
                "layer": layer,
                "layer_present": layer_present,
                "dashes": dashes,
                "dashes_present": dashes_present,
                "clip": list(clip) if clip is not None else None,
                "clip_present": clip_present,
                "clip_known": clip_known,
                "clip_shape_known": clip_shape_known,
                "clip_exact_rect": (
                    list(clip_exact_rect) if clip_exact_rect is not None else None
                ),
                "path_index": int(draw_index),
            }

        for item_index, item in enumerate(drawing.get("items", []) if isinstance(drawing, dict) else []):
            if not item:
                continue
            kind = str(item[0])
            if kind == "l" and len(item) >= 3:
                p1, p2 = item[1], item[2]
                try:
                    x1, y1, x2, y2 = float(p1.x), float(p1.y), float(p2.x), float(p2.y)
                except Exception:
                    try:
                        x1, y1, x2, y2 = float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])
                    except Exception:
                        continue
                if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                    continue
                if math.hypot(x2 - x1, y2 - y1) < 0.5:
                    continue
                payload = {
                    "id": f"d{draw_index}i{item_index}",
                    "kind": "line",
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "item_index": int(item_index),
                    **_graphic_fields(),
                }
                segments.append(payload)
            elif kind == "re" and len(item) >= 2:
                rect = item[1]
                try:
                    x0, y0, x1, y1 = map(float, (rect.x0, rect.y0, rect.x1, rect.y1))
                except Exception:
                    continue
                if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                    continue
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                # ADDITIVE: retain the closed native rectangle identity too.
                rects.append({
                    "kind": "rect",
                    "bbox": [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)],
                    "item_index": int(item_index),
                    **_graphic_fields(),
                })
                for edge in range(4):
                    a, b = pts[edge], pts[(edge + 1) % 4]
                    segments.append({
                        "id": f"d{draw_index}i{item_index}e{edge}",
                        "kind": "rect_edge",
                        "x1": a[0],
                        "y1": a[1],
                        "x2": b[0],
                        "y2": b[1],
                        "item_index": int(item_index),
                        "edge_index": int(edge),
                        **_graphic_fields(),
                    })

    words = []
    for idx, word in enumerate(pdf_page.get_text("words") or []):
        if len(word) < 5:
            continue
        try:
            x0, y0, x1, y1 = map(float, word[:4])
        except Exception:
            continue
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            continue
        text = str(word[4]).strip()
        if text:
            words.append({"id": idx, "text": text, "bbox": [x0, y0, x1, y1]})

    return {
        "width": float(pdf_page.rect.width), "height": float(pdf_page.rect.height),
        "segments": segments, "words": words,
        "rects": rects,
        "segment_count": len(segments), "word_count": len(words),
        "rect_count": len(rects),
    }


def snap_geometry(segments: Sequence[Dict[str, Any]], tolerance_pt: float = 1.25) -> Dict[str, Any]:
    """Snap nearby endpoints into stable graph nodes without changing long geometry."""
    nodes: List[Dict[str, Any]] = []
    node_for: Dict[Tuple[str, int], int] = {}

    def locate(pt: Tuple[float, float]) -> int:
        best = -1
        best_d = tolerance_pt + 1.0
        for idx, node in enumerate(nodes):
            d = math.hypot(node["x"] - pt[0], node["y"] - pt[1])
            if d <= tolerance_pt and d < best_d:
                best, best_d = idx, d
        if best >= 0:
            node = nodes[best]
            count = node["samples"] + 1
            node["x"] = (node["x"] * node["samples"] + pt[0]) / count
            node["y"] = (node["y"] * node["samples"] + pt[1]) / count
            node["samples"] = count
            return best
        nodes.append({"id": len(nodes), "x": pt[0], "y": pt[1], "samples": 1})
        return len(nodes) - 1

    edges = []
    for seg in segments:
        a = locate((float(seg["x1"]), float(seg["y1"])))
        b = locate((float(seg["x2"]), float(seg["y2"])))
        if a == b:
            continue
        edge = dict(seg)
        edge.update({"a": a, "b": b})
        edge["length_pt"] = _segment_length(seg)
        edge["angle_deg"] = _angle_deg(seg)
        edges.append(edge)
        node_for[(str(seg.get("id")), 0)] = a
        node_for[(str(seg.get("id")), 1)] = b

    adjacency: Dict[int, List[int]] = {idx: [] for idx in range(len(nodes))}
    for edge_index, edge in enumerate(edges):
        adjacency[edge["a"]].append(edge_index)
        adjacency[edge["b"]].append(edge_index)
    for node in nodes:
        node["degree"] = len(adjacency[node["id"]])
    return {"nodes": nodes, "edges": edges, "adjacency": adjacency}


def _parallel_gap(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[float]:
    if _angle_delta(_angle_deg(a), _angle_deg(b)) > 2.5:
        return None
    ax, ay = a["x2"] - a["x1"], a["y2"] - a["y1"]
    length = math.hypot(ax, ay)
    if length <= 0:
        return None
    return abs((b["x1"] - a["x1"]) * ay - (b["y1"] - a["y1"]) * ax) / length


def _projection_overlap(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    vx, vy = a["x2"] - a["x1"], a["y2"] - a["y1"]
    length = math.hypot(vx, vy)
    if length <= 0:
        return 0.0
    ux, uy = vx / length, vy / length
    a0, a1 = 0.0, length
    vals = [((b["x1"] - a["x1"]) * ux + (b["y1"] - a["y1"]) * uy), ((b["x2"] - a["x1"]) * ux + (b["y2"] - a["y1"]) * uy)]
    b0, b1 = min(vals), max(vals)
    return max(0.0, min(a1, b1) - max(a0, b0))


def detect_wall_pairs(segments: Sequence[Dict[str, Any]], px_per_m: float = 0.0) -> List[Dict[str, Any]]:
    """Return likely paired wall faces from parallel, overlapping native lines."""
    long_segments = [s for s in segments if _segment_length(s) >= 16.0]
    out: List[Dict[str, Any]] = []
    for i, a in enumerate(long_segments):
        la = _segment_length(a)
        for b in long_segments[i + 1:]:
            gap = _parallel_gap(a, b)
            if gap is None:
                continue
            if px_per_m > 0:
                min_gap, max_gap = 0.04 * px_per_m, 0.45 * px_per_m
            else:
                min_gap, max_gap = 0.8, 18.0
            if not (min_gap <= gap <= max_gap):
                continue
            overlap = _projection_overlap(a, b)
            if overlap < min(la, _segment_length(b)) * 0.45 or overlap < 12.0:
                continue
            width_m = gap / px_per_m if px_per_m > 0 else 0.0
            score = min(100.0, 50.0 + 35.0 * overlap / max(la, 1.0))
            if 0.07 <= width_m <= 0.30:
                score += 10.0
            out.append({
                "face_a": a.get("id"), "face_b": b.get("id"),
                "gap_pt": round(gap, 4), "wall_width_m": round(width_m, 4) if width_m else None,
                "overlap_pt": round(overlap, 3), "confidence": round(min(score, 100.0), 1),
            })
    return sorted(out, key=lambda item: (-item["confidence"], -item["overlap_pt"]))


def printed_scale_evidence(text: str, page_width_pt: float, render_zoom: float = 1.0) -> List[Dict[str, Any]]:
    out = []
    for match in _SCALE_RE.finditer(str(text or "")):
        denom = int(match.group(1))
        px_per_m = max(0.01, float(render_zoom)) * 1000.0 / (0.352778 * denom)
        out.append({"method": "printed_scale", "label": f"1:{denom}", "px_per_m": px_per_m, "weight": 1.0, "confidence": 55})
    return out


def dimension_scale_evidence(native: Dict[str, Any], render_zoom: float = 1.0) -> List[Dict[str, Any]]:
    """Pair plausible dimension text with nearby parallel linework."""
    segments = native.get("segments") or []
    evidence: List[Dict[str, Any]] = []
    for word in native.get("words") or []:
        real_m = _dimension_m(word.get("text"))
        if real_m is None:
            continue
        x0, y0, x1, y1 = word["bbox"]
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        h = max(1.0, y1 - y0)
        nearby = []
        for seg in segments:
            sx0, sy0, sx1, sy1 = _bbox(seg)
            if cx < sx0 - 50 or cx > sx1 + 50 or cy < sy0 - 50 or cy > sy1 + 50:
                continue
            length = _segment_length(seg)
            if not 8.0 <= length <= 1800.0:
                continue
            mx, my = (seg["x1"] + seg["x2"]) / 2.0, (seg["y1"] + seg["y2"]) / 2.0
            distance = math.hypot(mx - cx, my - cy)
            if distance <= max(55.0, h * 8.0):
                nearby.append((distance, length, seg))
        for distance, length, seg in sorted(nearby)[:4]:
            pxpm = length * max(0.01, render_zoom) / real_m
            if 5.0 <= pxpm <= 5000.0:
                evidence.append({
                    "method": "dimension_line", "label": str(word.get("text")),
                    "dimension_m": real_m, "line_id": seg.get("id"),
                    "px_per_m": pxpm, "weight": max(1.0, 7.0 - distance / 10.0),
                    "confidence": 70,
                })
    return evidence


def solve_scale(evidence: Sequence[Dict[str, Any]], tolerance: float = 0.035) -> Dict[str, Any]:
    """Robust consensus solver over independent scale evidence."""
    valid = [dict(e) for e in evidence if 5.0 <= _num(e.get("px_per_m")) <= 5000.0]
    if not valid:
        return {"px_per_m": 0.0, "verified": False, "confidence": 0, "evidence": [], "agreement_percent": None}
    best_group: List[Dict[str, Any]] = []
    best_weight = -1.0
    for candidate in valid:
        base = _num(candidate["px_per_m"])
        group = [e for e in valid if abs(_num(e["px_per_m"]) - base) / max(base, 1e-9) <= tolerance]
        weight = sum(max(0.25, _num(e.get("weight"), 1.0)) for e in group)
        if weight > best_weight:
            best_weight, best_group = weight, group
    weights = [max(0.25, _num(e.get("weight"), 1.0)) for e in best_group]
    values = [_num(e["px_per_m"]) for e in best_group]
    solved = sum(v * w for v, w in zip(values, weights)) / sum(weights)
    spread = max(abs(v - solved) / solved for v in values) if values else 1.0
    methods = {str(e.get("method")) for e in best_group}
    dimension_count = sum(1 for e in best_group if e.get("method") == "dimension_line")
    verified = dimension_count >= 2 or (dimension_count >= 1 and len(methods) >= 2)
    confidence = 55 + min(30, 9 * len(best_group)) + (10 if verified else 0) - min(20, int(spread * 400))
    return {
        "px_per_m": round(solved, 5), "verified": bool(verified),
        "confidence": max(0, min(100, int(confidence))),
        "evidence": best_group,
        "agreement_percent": round(spread * 100.0, 3),
        "methods": sorted(methods),
    }


def analyse_pdf_page(pdf_page: Any, render_zoom: float = 1.0, existing_px_per_m: float = 0.0) -> Dict[str, Any]:
    native = extract_native_page(pdf_page)
    full_text = pdf_page.get_text("text") or ""
    evidence = dimension_scale_evidence(native, render_zoom)
    evidence.extend(printed_scale_evidence(full_text, native["width"], render_zoom))
    if existing_px_per_m > 0:
        evidence.append({"method": "existing_calibration", "label": "existing", "px_per_m": existing_px_per_m, "weight": 1.25, "confidence": 65})
    scale = solve_scale(evidence)
    graph = snap_geometry(native["segments"])
    walls = detect_wall_pairs(native["segments"], scale.get("px_per_m") or existing_px_per_m)
    return {
        "version": VERSION,
        "native": {"width": native["width"], "height": native["height"], "segment_count": native["segment_count"], "word_count": native["word_count"]},
        "scale": scale,
        "graph": {"node_count": len(graph["nodes"]), "edge_count": len(graph["edges"]), "junction_count": sum(1 for n in graph["nodes"] if n.get("degree", 0) >= 3)},
        "wall_pairs": walls[:1500],
        "wall_pair_count": len(walls),
    }


def analyse_stored_page(app: Any, page_id: int) -> Dict[str, Any]:
    rows = app.lquery("SELECT p.*,d.path FROM pages p JOIN documents d ON d.id=p.document_id WHERE p.id=?", (int(page_id),))
    if not rows:
        raise ValueError("Page not found")
    row = rows[0]
    path = Path(str(row.get("path") or ""))
    if not path.is_file() or path.suffix.lower() != ".pdf" or getattr(app, "fitz", None) is None:
        raise ValueError("Native vector analysis requires the original PDF file")
    pdf = app.fitz.open(path)
    try:
        pdf_page = pdf.load_page(int(row.get("page_no") or 1) - 1)
        result = analyse_pdf_page(pdf_page, _num(row.get("render_zoom"), 1.0), _num(row.get("px_per_m"), 0.0))
    finally:
        pdf.close()
    result["page_id"] = int(page_id)
    result["page_label"] = str(row.get("page_label") or "")
    app.set_workspace_setting(int(row["workspace_id"]), f"{SETTING_PREFIX}{int(page_id)}", json.dumps(result))
    return result


def apply(app: Any) -> None:
    if getattr(app, "_pb_vector_geometry_v130_applied", False):
        return
    app._pb_vector_geometry_v130_applied = True
    app.extract_native_page_v130 = extract_native_page
    app.snap_geometry_v130 = snap_geometry
    app.detect_wall_pairs_v130 = detect_wall_pairs
    app.solve_scale_v130 = solve_scale
    app.analyse_pdf_page_v130 = analyse_pdf_page
    app.analyse_stored_page_v130 = lambda page_id: analyse_stored_page(app, page_id)
