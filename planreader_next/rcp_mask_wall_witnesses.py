"""A120 ceiling layout masks reconciled to actual source-painted wall ink.

A white PDF fill mask can be an excellent LAYOUT SEED without being an
actual drawn wall or ceiling zone boundary. This module checks each
suggested side against INDEPENDENT visible black wall strips, reports
unsupported spans and overlapping masks; no perimeter or m2 is published.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

from .engine import NativePage, NativeRectangle, SourceConflict, load_native_page
from .rcp_zone_scope import propose_rcp_source_zone_rectangles, _is_white_layout_fill

_EDGE_DISTANCE_PT = 8.5
_MAX_WALL_THICKNESS_PT = 14.0
_MIN_WALL_THICKNESS_PT = 2.0
_MIN_WALL_STROKE_LENGTH_PT = 20.0


def _is_dark_wall_like_source_ink(rect: NativeRectangle) -> bool:
    rgb = rect.fill_color
    if (
        not rect.clip_known or rgb is None or len(rgb) not in (1,3,4)
        or any(not math.isfinite(c) or c < 0 or c > 1 for c in rgb)
        or max(rgb) >= .55
    ):
        return False
    x0, y0, x1, y1 = rect.bbox
    minor, major = sorted((x1-x0, y1-y0))
    # Literal dark filled narrow rectangle on the PDF is independent
    # printed ink. Not enough by itself to prove finished-face ownership.
    return (
        _MIN_WALL_THICKNESS_PT <= minor <= _MAX_WALL_THICKNESS_PT
        and major >= _MIN_WALL_STROKE_LENGTH_PT
    )


def _merge(intervals: Sequence[tuple[float,float]]) -> list[list[float]]:
    merged: list[list[float]] = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if not merged or lo > merged[-1][1] + .1:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    return [[round(a, 3), round(b, 3)] for a,b in merged]


def _complement(start: float, stop: float, intervals: list[list[float]]) -> list[list[float]]:
    uncovered = []
    cursor = start
    for lo,hi in intervals:
        if lo > cursor + .1:
            uncovered.append([round(cursor,3),round(lo,3)])
        cursor = max(cursor,hi)
    if cursor < stop - .1:
        uncovered.append([round(cursor,3),round(stop,3)])
    return uncovered


def _distance_to_range(value: float, start: float, stop: float) -> float:
    return max(start-value, value-stop, 0)


def _edge_source_support(
    bbox: tuple[float,float,float,float],
    side: str,
    dark_walls: Sequence[NativeRectangle],
) -> dict[str, Any]:
    x0, y0, x1, y1 = bbox
    if side in ("y_min","y_max"):
        constant = y0 if side == "y_min" else y1
        axis_start,axis_end = x0,x1
        orientation = "horizontal_pdf_native"
    elif side in ("x_min","x_max"):
        constant = x0 if side == "x_min" else x1
        axis_start,axis_end = y0,y1
        orientation = "vertical_pdf_native"
    else:
        raise SourceConflict("source_mask_edge_identity_invalid")
    spans: list[tuple[float,float]] = []
    refs = []
    for rect in dark_walls:
        a,b,c,d = rect.bbox
        if side in ("y_min","y_max"):
            if c-a < d-b or _distance_to_range(constant,b,d)>_EDGE_DISTANCE_PT:
                continue
            lo,hi=max(a,axis_start),min(c,axis_end)
        else:
            if d-b < c-a or _distance_to_range(constant,a,c)>_EDGE_DISTANCE_PT:
                continue
            lo,hi=max(b,axis_start),min(d,axis_end)
        if hi - lo >= 1:
            spans.append((lo,hi))
            refs.append(rect.ref)
    supported=_merge(spans)
    unbacked=_complement(axis_start,axis_end,supported)
    supported_len=sum(y-x for x,y in supported)
    return {
        "side_native": side,
        "side_orientation_native": orientation,
        "axis_range_pdf_pts": [round(axis_start,3),round(axis_end,3)],
        "constant_pdf_pts": round(constant,3),
        "supported_intervals_pdf_pts": supported,
        "unsupported_intervals_pdf_pts": unbacked,
        "visible_dark_wall_ref_candidates": sorted(set(refs)),
        "covered_fraction_by_dark_wall_ink": round(supported_len/(axis_end-axis_start),4),
        "drawn_boundary_authenticated": False,
        "ceiling_area_publishable": False,
    }


def _alternative_dark_wall_for_unsupported_edge(
    mask: NativeRectangle,
    side: str,
    edge: dict[str, Any],
    dark_walls: Sequence[NativeRectangle],
) -> list[dict[str, Any]]:
    """Show where a mask extends PAST a real wall: reviewer-only step hints.

    A different wall 9-40 PDF points from the unsupported white bbox
    side can account for a stepped room/ceiling perimeter. Never replace
    the actual ceiling boundary automatically or infer finished face.
    """
    x0,y0,x1,y1=mask.bbox
    constant=(y0 if side=="y_min" else y1) if side.startswith("y") else (
        x0 if side=="x_min" else x1
    )
    proposals=[]
    for lo,hi in edge["unsupported_intervals_pdf_pts"]:
        alt=[]
        for bar in dark_walls:
            a,b,c,d=bar.bbox
            if side.startswith("y"):
                if c-a < d-b:
                    continue
                distance=_distance_to_range(constant,b,d)
                overlap=max(0,min(hi,c)-max(lo,a))
            else:
                if d-b < c-a:
                    continue
                distance=_distance_to_range(constant,a,c)
                overlap=max(0,min(hi,d)-max(lo,b))
            if not (_EDGE_DISTANCE_PT < distance <= 40.0):
                continue
            fraction=overlap/(hi-lo)
            if fraction < .8:
                continue
            alt.append((
                distance, -fraction, bar.ref,
                {
                    "source_dark_wall_ref":bar.ref,
                    "source_wall_strip_bbox_pdf_pts":list(bar.bbox),
                    "unsupported_mask_side":side,
                    "unsupported_mask_axis_interval_pdf_pts":[lo,hi],
                    "parallel_wall_coverage_fraction":round(fraction,4),
                    "normal_distance_from_mask_bbox_edge_pdf_pts":round(distance,3),
                    "source_owned_step_boundary_candidate_only":True,
                    "physical_finished_face_authenticated":False,
                }
            ))
        if alt:
            proposals.append(sorted(alt)[:1][0][3])
    return proposals


def report_rcp_mask_wall_witnesses(page: NativePage) -> dict[str, Any]:
    """Return every layout mask with edge-wise source dark-wall corroboration."""
    raw = propose_rcp_source_zone_rectangles(
        page, include_fill_masks_as_layout_hints=True
    )
    rects = {r.ref:r for r in page.rectangles}
    dark_walls = [r for r in page.rectangles if _is_dark_wall_like_source_ink(r)]
    rows=[]
    for c in raw["source_zone_rectangle_candidates"]:
        rect=rects[c["source_rectangle_ref"]]
        if not _is_white_layout_fill(rect):
            continue
        edge_receipts={
            edge:_edge_source_support(rect.bbox,edge,dark_walls)
            for edge in ("x_min","y_min","x_max","y_max")
        }
        alt_wall_steps=[
            proof
            for side, edge_info in edge_receipts.items()
            for proof in _alternative_dark_wall_for_unsupported_edge(
                rect,side,edge_info,dark_walls
            )
        ]
        rows.append({
            "source_rectangle_ref":rect.ref,
            "source_sha256":page.source_sha256,
            "rcp_page_index":page.page_index,
            "original_pdf_fill_mask_bbox_pdf_pts": list(rect.bbox),
            "paint_role":"UNSTROKED_WHITE_LAYOUT_MASK_NOT_CEILING_BORDER",
            "material_code_candidate":c["material_code_candidate"],
            "height_mm_source_candidate":c["height_mm"],
            "height_word_refs":c["height_word_refs"],
            "material_word_refs":c["material_word_refs"],
            "edges":edge_receipts,
            "alternative_dark_wall_step_witnesses":alt_wall_steps,
            "physical_ceiling_zone_authenticated":False,
            "metric_ceiling_area_m2":None,
            "commercial_publishable":False,
            "benchmark_credit":False,
        })
    overlaps=[]
    for i, one in enumerate(rows):
        a=one["original_pdf_fill_mask_bbox_pdf_pts"]
        for other in rows[i+1:]:
            b=other["original_pdf_fill_mask_bbox_pdf_pts"]
            intersection=[
                max(a[0],b[0]),max(a[1],b[1]),
                min(a[2],b[2]),min(a[3],b[3]),
            ]
            w=intersection[2]-intersection[0]
            h=intersection[3]-intersection[1]
            if w <= 1 or h <= 1:
                continue
            overlapped_wall_refs=[]
            for wall in dark_walls:
                x0,y0,x1,y1=wall.bbox
                if (
                    x1 >= intersection[0]-_EDGE_DISTANCE_PT
                    and x0 <= intersection[2]+_EDGE_DISTANCE_PT
                    and y1 >= intersection[1]-_EDGE_DISTANCE_PT
                    and y0 <= intersection[3]+_EDGE_DISTANCE_PT
                ):
                    overlapped_wall_refs.append(wall.ref)
            overlaps.append({
                "source_rectangle_refs":[one["source_rectangle_ref"],other["source_rectangle_ref"]],
                "intersection_bbox_pdf_pts":[round(x,3) for x in intersection],
                "overlap_area_pdf_pts2_not_metric":round(w*h,3),
                "independently_painted_dark_wall_refs":sorted(set(overlapped_wall_refs)),
                "paint_mask_overlap_not_real_ceiling_overlap":True,
                "source_boundary_resolution_required":True,
            })
    return {
        "source_sha256":page.source_sha256,
        "rcp_page_index":page.page_index,
        "height_material_callouts":raw["source_height_material_pairs"],
        "layout_mask_candidates":rows,
        "layout_mask_count":len(rows),
        "layout_mask_overlaps":overlaps,
        "strict_stroked_rectangle_count":len(
            propose_rcp_source_zone_rectangles(page)["source_zone_rectangle_candidates"]
        ),
        "dark_wall_ink_rect_count":len(dark_walls),
        "floor_plan_room_ring_required":False,
        "visible_wall_alignment_review_required":True,
        "metric_ceiling_area_count":0,
        "commercial_publishable":False,
        "benchmark_credit":False,
        "official_score":None,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description="A120 original white layout masks vs independently painted dark wall bars")
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--rcp-page",type=int,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    page=load_native_page(args.pdf,args.rcp_page)
    packet=report_rcp_mask_wall_witnesses(page)
    with args.output.open("x",encoding="utf8") as fp:
        json.dump(packet,fp,indent=2,sort_keys=True)
    print(json.dumps({
        "layout_mask_count":packet["layout_mask_count"],
        "overlap_count":len(packet["layout_mask_overlaps"]),
        "metric_ceiling_area_count":0,
        "commercial_publishable":False,
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
