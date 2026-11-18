"""Production-reachable inside-face footprint stage (#4549-01..10 wiring).

Invoked from the original PDF extractor and private footprint runner after the
existing exterior ink contour. Emits review/topology receipts only — never
raises FIRM, customer rows, or frozen-benchmark authority.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pb_source_dual_dwelling_opening_topology_shadow import (
    TopologyEdge,
    build_dual_dwelling_opening_topology,
)
from pb_source_external_footprint_inside_face_start_shadow import (
    ExteriorWallSegment,
    build_external_footprint_inside_face_bundle,
    classify_wall_ink_band,
)
from pb_source_wall_stub_junction_geometry_runtime import (
    GeometryPrimitive,
    run_wall_stub_junction_geometry_stage,
)

_WALL_LAYER = re.compile(r"Wall|WALL|A-WALL|Enclosure", re.I)
_NON_WALL = re.compile(r"dim|anno|text|grid|title|border|note|hatch", re.I)


def _xy(point: Any) -> tuple[float, float] | None:
    try:
        if hasattr(point, "x"):
            x, y = float(point.x), float(point.y)
        else:
            x, y = float(point[0]), float(point[1])
        if math.isfinite(x) and math.isfinite(y):
            return x, y
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    return None


def _gray_of(row: Mapping[str, Any]) -> float | None:
    for key in ("color", "fill"):
        ink = row.get(key)
        if isinstance(ink, (tuple, list)) and len(ink) >= 3:
            try:
                vals = [float(v) for v in ink[:3]]
                if all(math.isfinite(v) and 0 <= v <= 1 for v in vals):
                    return sum(vals) / 3.0
            except (TypeError, ValueError):
                continue
    return None


def _stroke_weight(row: Mapping[str, Any]) -> float:
    for key in ("width", "stroke_width", "linewidth"):
        try:
            w = float(row.get(key) or 0.0)
            if math.isfinite(w) and w > 0:
                return w
        except (TypeError, ValueError):
            continue
    return 1.0


def exterior_wall_segments_from_drawings(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_bounds_pdf_pts: tuple[float, float, float, float],
) -> tuple[ExteriorWallSegment, ...]:
    """Promote dark wall-layer strokes into inside-face walker segments."""
    out: list[ExteriorWallSegment] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if _NON_WALL.search(layer) and not _WALL_LAYER.search(layer):
            continue
        if not _WALL_LAYER.search(layer) and row.get("type") != "s":
            continue
        gray = _gray_of(row)
        if gray is None:
            continue
        weight = _stroke_weight(row)
        ink = classify_wall_ink_band(
            gray=gray, stroke_weight_pt=weight, near_page_frame=False,
        )
        if ink.role not in {"structural_wall", "structural_wall_candidate"}:
            continue
        for item in row.get("items") or ():
            if not item or item[0] != "l" or len(item) < 3:
                continue
            a, b = _xy(item[1]), _xy(item[2])
            if a is None or b is None:
                continue
            out.append(
                ExteriorWallSegment(
                    wall_id=index,
                    start_pdf_pts=a,
                    end_pdf_pts=b,
                    gray=gray,
                    stroke_weight_pt=weight,
                )
            )
            break
    return tuple(out)


def _topology_edges_from_segments(
    segments: Sequence[ExteriorWallSegment],
    *,
    party_path_ids: Sequence[int] = (),
) -> tuple[TopologyEdge, ...]:
    party = set(int(i) for i in party_path_ids)
    edges: list[TopologyEdge] = []
    for seg in segments:
        if seg.label == "PAGE_FRAME":
            continue
        role = "party" if seg.wall_id in party else "external"
        edges.append(
            TopologyEdge(
                edge_id=seg.wall_id,
                start_pdf_pts=seg.start_pdf_pts,
                end_pdf_pts=seg.end_pdf_pts,
                role=role,
                kind="wall",
            )
        )
    return tuple(edges)


def run_inside_face_footprint_runtime_stage(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_bounds_pdf_pts: tuple[float, float, float, float],
    source_words: Sequence[Any] = (),
    page_index: int = -1,
) -> dict[str, object]:
    """Executable stage for original-app footprint/topology review receipts."""
    segments = exterior_wall_segments_from_drawings(
        drawings, page_bounds_pdf_pts=page_bounds_pdf_pts,
    )
    bundle = build_external_footprint_inside_face_bundle(
        segments, page_bounds_pdf_pts=page_bounds_pdf_pts,
    )

    dual: dict[str, object] = {
        "status": "ABSTAINED",
        "reason": "dual_dwelling_stage_not_run_without_party_edges",
        "measurement_authorized": False,
        "commercial_publishable": False,
    }
    # When party path ids are known from shared-divider detection, compose.
    try:
        from pb_source_shared_dwelling_envelope_shadow import (
            detect_native_shared_dwelling_dividers,
        )

        dividers = detect_native_shared_dwelling_dividers(
            drawings, source_words, source_page_index=page_index,
        )
        party_paths = tuple(
            pid
            for d in dividers
            for pid in getattr(d, "wall_native_path_ids", ())
        )
        if party_paths:
            topo = _topology_edges_from_segments(segments, party_path_ids=party_paths)
            # Split dwelling graphs by which side of party each external edge mid falls.
            party_x = None
            for d in dividers:
                if getattr(d, "orientation", "") == "vertical" and d.wall_bounds_pdf_pts:
                    party_x = (
                        float(d.wall_bounds_pdf_pts[0]) + float(d.wall_bounds_pdf_pts[2])
                    ) / 2.0
                    break
            a_ids: list[int] = []
            b_ids: list[int] = []
            for e in topo:
                if e.role == "party":
                    a_ids.append(e.edge_id)
                    b_ids.append(e.edge_id)
                    continue
                mid_x = (e.start_pdf_pts[0] + e.end_pdf_pts[0]) / 2.0
                if party_x is None or mid_x <= party_x:
                    a_ids.append(e.edge_id)
                else:
                    b_ids.append(e.edge_id)
            receipt = build_dual_dwelling_opening_topology(
                topo, dwelling_a_edge_ids=a_ids, dwelling_b_edge_ids=b_ids,
            )
            dual = receipt.to_dict()
    except Exception as exc:  # fail closed — never block the outer extractor
        dual = {
            "status": "ABSTAINED",
            "reason": f"dual_dwelling_runtime_exception:{type(exc).__name__}",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }

    geom_prims = tuple(
        GeometryPrimitive(
            primitive_id=s.wall_id,
            start_pdf_pts=s.start_pdf_pts,
            end_pdf_pts=s.end_pdf_pts,
            kind="wall",
            label=s.label,
            stroke_weight_pt=s.stroke_weight_pt,
        )
        for s in segments
    )
    stub_junction = run_wall_stub_junction_geometry_stage(geom_prims)

    return {
        "status": bundle.start.status if bundle.walk.status == "CANDIDATE" else (
            bundle.start.status if bundle.start.status != "CANDIDATE" else bundle.walk.status
        ),
        "reason": (
            bundle.walk.reason
            if bundle.walk.status == "CANDIDATE"
            else bundle.start.reason if bundle.start.status != "CANDIDATE"
            else bundle.walk.reason
        ),
        "page_index": page_index,
        "inside_face_start": bundle.start.to_dict(),
        "clockwise_walk": bundle.walk.to_dict(),
        "ink_sample_count": len(bundle.ink_samples),
        "dual_dwelling": dual,
        "wall_stub_junction_geometry": stub_junction,
        "segment_count": len(segments),
        "tasks_covered": [
            "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
            "11", "12", "13", "14", "15",
        ],
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }
