"""PlanReader v1.3.0 native vector geometry and scale-evidence engine.

This module keeps measurement deterministic. It extracts native PDF primitives,
constructs a snapped geometry graph, identifies likely wall-face pairs, derives
closed-space candidates, and aggregates independent scale evidence. AI remains a
semantic helper and is never allowed to invent measured geometry here.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "1.3.0"
SETTING_PREFIX = "vector_geometry_v130_"
_DIM_RE = re.compile(r"(?<![:\d])(?P<num>\d{2,5}(?:\.\d{1,3})?)\s*(?P<unit>mm|m)?(?!\s*[:\d])", re.I)
_SCALE_RE = re.compile(r"(?<!\d)1\s*:\s*(\d{2,4})(?!\d)")


class NativeGeometryIntegrityError(RuntimeError):
    """Fail-closed PDF source-integrity error with deterministic diagnostics."""

    def __init__(self, diagnostics: Dict[str, Any]):
        self.diagnostics = dict(diagnostics)
        super().__init__(json.dumps(self.diagnostics, sort_keys=True, separators=(",", ":")))


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


def _stable_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _point_xy(value: Any) -> Tuple[float, float]:
    try:
        return float(value.x), float(value.y)
    except Exception:
        return float(value[0]), float(value[1])


def _rect_xyxy(value: Any) -> Tuple[float, float, float, float]:
    try:
        return tuple(map(float, (value.x0, value.y0, value.x1, value.y1)))  # type: ignore[return-value]
    except Exception:
        return tuple(map(float, value[:4]))  # type: ignore[return-value]


def _form_xobject_provenance(pdf_page: Any) -> Tuple[List[Dict[str, Any]], str]:
    """Return deterministic reachable Form provenance and reject explicit cycles.

    PyMuPDF already applies page/content/Form CTMs when it emits drawing
    coordinates. This separate provenance record preserves the invocation graph
    and Form matrices without rewriting those canonical page coordinates.
    """
    get_xobjects = getattr(pdf_page, "get_xobjects", None)
    if not callable(get_xobjects):
        records: List[Dict[str, Any]] = []
        return records, _stable_fingerprint(records)

    raw = get_xobjects() or []
    document = getattr(pdf_page, "parent", None)
    records = []
    adjacency: Dict[int, List[int]] = {}
    names: Dict[Tuple[int, int], List[str]] = {}
    nodes = {0}

    for entry in raw:
        if not entry or len(entry) < 3:
            continue
        xref = int(entry[0])
        name = str(entry[1] or "")
        invoker = int(entry[2] or 0)
        bbox = None
        if len(entry) >= 4 and entry[3] is not None:
            try:
                bbox = list(_rect_xyxy(entry[3]))
            except Exception:
                bbox = None
        matrix = None
        if document is not None and hasattr(document, "xref_get_key") and xref > 0:
            try:
                key_type, value = document.xref_get_key(xref, "Matrix")
                if key_type not in {"null", "none"}:
                    matrix = str(value)
            except Exception:
                matrix = None
        records.append(
            {
                "xref": xref,
                "name": name,
                "invoker_xref": invoker,
                "bbox": bbox,
                "matrix": matrix,
            }
        )
        adjacency.setdefault(invoker, []).append(xref)
        names.setdefault((invoker, xref), []).append(name)
        nodes.update((invoker, xref))

    for parent in adjacency:
        adjacency[parent] = sorted(set(adjacency[parent]))

    visited: set[int] = set()
    active: List[int] = []
    active_index: Dict[int, int] = {}

    def visit(node: int) -> Optional[List[int]]:
        if node in active_index:
            return active[active_index[node] :] + [node]
        if node in visited:
            return None
        active_index[node] = len(active)
        active.append(node)
        for child in adjacency.get(node, []):
            cycle = visit(child)
            if cycle:
                return cycle
        active.pop()
        active_index.pop(node, None)
        visited.add(node)
        return None

    cycle_path = None
    ordered_starts = [0] + sorted(node for node in nodes if node != 0)
    for start in ordered_starts:
        cycle_path = visit(start)
        if cycle_path:
            break

    canonical_records = sorted(
        records,
        key=lambda item: (
            int(item["invoker_xref"]),
            int(item["xref"]),
            str(item["name"]),
            json.dumps(item.get("bbox"), sort_keys=True),
            str(item.get("matrix")),
        ),
    )
    if cycle_path:
        cycle_edges = []
        for parent, child in zip(cycle_path, cycle_path[1:]):
            cycle_edges.append(
                {
                    "parent_xref": parent,
                    "child_xref": child,
                    "names": sorted(names.get((parent, child), [])),
                }
            )
        raise NativeGeometryIntegrityError(
            {
                "status": "unresolved",
                "reason": "form_xobject_cycle",
                "cycle_xrefs": cycle_path,
                "cycle_edges": cycle_edges,
                "form_provenance": canonical_records,
            }
        )
    return canonical_records, _stable_fingerprint(canonical_records)


def _get_drawings_with_clip_state(pdf_page: Any) -> Tuple[List[Dict[str, Any]], bool]:
    """Request extended drawing state when supported, preserving hard failures."""
    try:
        return list(pdf_page.get_drawings(extended=True) or []), True
    except TypeError:
        return list(pdf_page.get_drawings() or []), False


def _clip_segment_to_rect(
    segment: Dict[str, Any],
    rect: Sequence[float],
) -> Optional[Dict[str, Any]]:
    """Clip a segment exactly against an axis-aligned rectangular clip."""
    x1, y1 = float(segment["x1"]), float(segment["y1"])
    x2, y2 = float(segment["x2"]), float(segment["y2"])
    xmin, ymin, xmax, ymax = map(float, rect)
    xmin, xmax = min(xmin, xmax), max(xmin, xmax)
    ymin, ymax = min(ymin, ymax), max(ymin, ymax)
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - xmin, xmax - x1, y1 - ymin, ymax - y1)
    lo, hi = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0.0:
            if qi < 0.0:
                return None
            continue
        ratio = qi / pi
        if pi < 0.0:
            lo = max(lo, ratio)
        else:
            hi = min(hi, ratio)
        if lo > hi:
            return None
    clipped = dict(segment)
    clipped["x1"] = x1 + lo * dx
    clipped["y1"] = y1 + lo * dy
    clipped["x2"] = x1 + hi * dx
    clipped["y2"] = y1 + hi * dy
    return clipped


def _source_primitive(
    *,
    primitive_id: str,
    kind: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: float,
    stroke: Any,
    fill: Any,
    layer: str,
    dashes: str,
    active_geometry: bool,
    inactive_reason: Optional[str],
    clip_ids: Sequence[str],
    form_provenance_fingerprint: str,
) -> Dict[str, Any]:
    length = math.hypot(x2 - x1, y2 - y1)
    status = "DEGENERATE" if length == 0.0 else "GEOMETRIC"
    payload = {
        "id": primitive_id,
        "kind": kind,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": width,
        "stroke": stroke,
        "fill": fill,
        "layer": layer,
        "dashes": dashes,
        "geometry_status": status,
        "length_pt": length,
        "active_geometry": bool(active_geometry),
        "inactive_reason": inactive_reason,
        "clip_ids": list(clip_ids),
        "form_provenance_fingerprint": form_provenance_fingerprint,
    }
    payload["source_primitive_fingerprint"] = _stable_fingerprint(payload)
    return payload


def extract_native_page(pdf_page: Any) -> Dict[str, Any]:
    """Extract canonical page geometry while retaining source-integrity evidence.

    Existing ``segments`` semantics stay unchanged for valid non-degenerate
    geometry. Additive ``source_primitives`` preserves pre-clip canonical page
    primitives (including exact degenerates and legacy-filtered sub-point lines);
    ``visible_segments`` is a diagnostic view clipped only when the active clip
    stack is provably rectangular. Non-rectangular clip shapes stay unresolved
    rather than being approximated as physical deletion.
    """
    form_provenance, form_fingerprint = _form_xobject_provenance(pdf_page)
    segments: List[Dict[str, Any]] = []
    visible_segments: List[Dict[str, Any]] = []
    source_primitives: List[Dict[str, Any]] = []
    rects: List[Dict[str, Any]] = []
    clip_provenance: List[Dict[str, Any]] = []
    visibility_diagnostics: List[Dict[str, Any]] = []

    drawings, extended_available = _get_drawings_with_clip_state(pdf_page)
    clip_stack: List[Dict[str, Any]] = []

    for draw_index, drawing in enumerate(drawings):
        if not isinstance(drawing, dict):
            continue
        level = int(_num(drawing.get("level"), 0.0)) if extended_available else 0

        while clip_stack and int(clip_stack[-1]["level"]) >= level:
            clip_stack.pop()

        draw_type = str(drawing.get("type") or "")
        items = drawing.get("items", []) or []
        if draw_type == "clip":
            exact_rect = False
            clip_rect = None
            if len(items) == 1 and items[0] and str(items[0][0]) == "re" and len(items[0]) >= 2:
                try:
                    x0, y0, x1, y1 = _rect_xyxy(items[0][1])
                    clip_rect = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
                    exact_rect = True
                except Exception:
                    clip_rect = None
            scissor = None
            if drawing.get("scissor") is not None:
                try:
                    scissor = list(_rect_xyxy(drawing["scissor"]))
                except Exception:
                    scissor = None
            clip = {
                "id": f"clip{draw_index}",
                "level": level,
                "exact_rect": exact_rect,
                "rect": clip_rect,
                "scissor": scissor,
                "even_odd": bool(drawing.get("even_odd", False)),
                "layer": str(drawing.get("layer") or ""),
            }
            clip["fingerprint"] = _stable_fingerprint(clip)
            clip_provenance.append(clip)
            clip_stack.append(clip)
            continue

        if draw_type == "group":
            continue

        width = _num(drawing.get("width"), 0.0)
        stroke = drawing.get("color")
        fill = drawing.get("fill")
        layer = str(drawing.get("layer") or drawing.get("oc") or "")
        dashes = str(drawing.get("dashes") or "")
        active_clip_ids = [str(item["id"]) for item in clip_stack]
        clips_exact = all(bool(item["exact_rect"]) for item in clip_stack)

        def add_segment(
            primitive_id: str,
            kind: str,
            a: Tuple[float, float],
            b: Tuple[float, float],
            *,
            legacy_line_filter: bool,
        ) -> None:
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            if length == 0.0:
                active = False
                inactive_reason = "degenerate_zero_length"
            elif legacy_line_filter and length < 0.5:
                active = False
                inactive_reason = "legacy_subpoint_filter"
            else:
                active = True
                inactive_reason = None

            source = _source_primitive(
                primitive_id=primitive_id,
                kind=kind,
                x1=a[0],
                y1=a[1],
                x2=b[0],
                y2=b[1],
                width=width,
                stroke=stroke,
                fill=fill,
                layer=layer,
                dashes=dashes,
                active_geometry=active,
                inactive_reason=inactive_reason,
                clip_ids=active_clip_ids,
                form_provenance_fingerprint=form_fingerprint,
            )
            source_primitives.append(source)
            if not active:
                return

            segment = {
                "id": primitive_id,
                "kind": kind,
                "x1": a[0],
                "y1": a[1],
                "x2": b[0],
                "y2": b[1],
                "width": width,
                "stroke": stroke,
                "fill": fill,
                "layer": layer,
                "dashes": dashes,
            }
            segments.append(segment)

            if not clips_exact:
                visibility_diagnostics.append(
                    {
                        "source_primitive_id": primitive_id,
                        "status": "unresolved",
                        "reason": "nonrectangular_clip_shape",
                        "clip_ids": active_clip_ids,
                    }
                )
                return

            visible: Optional[Dict[str, Any]] = dict(segment)
            for clip in clip_stack:
                if visible is None:
                    break
                visible = _clip_segment_to_rect(visible, clip["rect"])
            if visible is None:
                return
            visible["clip_ids"] = active_clip_ids
            visible["visibility_status"] = "VISIBLE"
            visible_segments.append(visible)

        for item_index, item in enumerate(items):
            if not item:
                continue
            kind = str(item[0])
            if kind == "l" and len(item) >= 3:
                try:
                    p1 = _point_xy(item[1])
                    p2 = _point_xy(item[2])
                except Exception:
                    continue
                add_segment(
                    f"d{draw_index}i{item_index}",
                    "line",
                    p1,
                    p2,
                    legacy_line_filter=True,
                )
            elif kind == "re" and len(item) >= 2:
                try:
                    x0, y0, x1, y1 = _rect_xyxy(item[1])
                except Exception:
                    continue
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                rects.append(
                    {
                        "kind": "rect",
                        "bbox": [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)],
                        "width": width,
                        "stroke": stroke,
                        "fill": fill,
                        "layer": layer,
                        "dashes": dashes,
                    }
                )
                for edge in range(4):
                    add_segment(
                        f"d{draw_index}i{item_index}e{edge}",
                        "rect_edge",
                        pts[edge],
                        pts[(edge + 1) % 4],
                        legacy_line_filter=False,
                    )

    words = []
    for idx, word in enumerate(pdf_page.get_text("words") or []):
        if len(word) < 5:
            continue
        try:
            x0, y0, x1, y1 = map(float, word[:4])
        except Exception:
            continue
        text = str(word[4]).strip()
        if text:
            words.append({"id": idx, "text": text, "bbox": [x0, y0, x1, y1]})

    return {
        "width": float(pdf_page.rect.width),
        "height": float(pdf_page.rect.height),
        "segments": segments,
        "words": words,
        "rects": rects,
        "segment_count": len(segments),
        "word_count": len(words),
        "rect_count": len(rects),
        "source_primitives": source_primitives,
        "visible_segments": visible_segments,
        "clip_provenance": clip_provenance,
        "visibility_diagnostics": visibility_diagnostics,
        "raw_geometry": {"source_primitives": source_primitives},
        "visible_geometry": {"segments": visible_segments},
        "form_provenance": form_provenance,
        "form_provenance_fingerprint": form_fingerprint,
        "clip_state_available": extended_available,
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
