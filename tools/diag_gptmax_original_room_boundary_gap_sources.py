"""Read-only native-source room perimeter seam inspection (never a face grant).

Given an immutable source PDF and *producer-authenticated* original W4 scope,
report short aligned gaps between distinct, source-owned W2 edge fragments near
native printed room words. Examine original PDF path and painted pixels at each
gap. Pixel or label proximity cannot establish structural equivalence, a closed
room, floor identity, metric area or a construction quantity.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import fitz


def _candidate_edges(scope: Mapping[str, Any]) -> list[dict[str, Any]]:
    if scope.get("status") != "corroborated" or not scope.get("records"):
        raise ValueError("authenticated producer W4 scope required")
    result = []
    seen = set()
    for r in scope["records"]:
        wall = r.get("wall_candidate_id")
        if not isinstance(wall, str) or not wall or wall in seen:
            raise ValueError("W4 wall identity missing or reused")
        seen.add(wall)
        for edge in r.get("source_edge_fragments", ()):
            line = edge.get("geometry")
            ids = edge.get("source_primitive_ids")
            if (not isinstance(line, list) or len(line) != 4
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in line)
                    or not isinstance(ids, list) or not ids or not all(isinstance(x,str) and x for x in ids)):
                raise ValueError("source edge missing authenticated geometry/parents")
            x0, y0, x1, y1 = map(float,line)
            if x0 == x1 and y0 != y1:
                axis, fixed, lo, hi = "vertical", x0, min(y0, y1), max(y0, y1)
            elif y0 == y1 and x0 != x1:
                axis, fixed, lo, hi = "horizontal", y0, min(x0, x1), max(x0, x1)
            else:
                continue
            result.append({
                "axis": axis, "fixed": fixed, "low": lo, "high": hi,
                "wall_candidate_id": wall, "edge_id": edge.get("edge_id"),
                "source_primitive_ids": sorted(set(ids)),
            })
    return result


def short_source_gap_candidates(scope: Mapping[str, Any], *, max_gap_pt: float) -> list[dict[str, Any]]:
    if not (type(max_gap_pt) in (int,float) and 0 < max_gap_pt <= 3 and math.isfinite(max_gap_pt)):
        raise ValueError("invalid bounded diagnostic gap")
    edges = _candidate_edges(scope)
    by_axis: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        by_axis[(edge["axis"], round(edge["fixed"], 4))].append(edge)
    gaps = []
    seen = set()
    for (axis, fixed), items in by_axis.items():
        ordered = sorted(items, key=lambda e:(e["low"],e["high"],e["wall_candidate_id"]))
        for a in ordered:
            for b in ordered:
                gap = b["low"] - a["high"]
                if gap <= 0:
                    continue
                if gap > max_gap_pt:
                    # Ordered successors cannot restart earlier along this axis.
                    break
                if a["edge_id"] == b["edge_id"] and a["wall_candidate_id"] == b["wall_candidate_id"]:
                    continue
                key=(axis, fixed, round(a["high"],6), round(b["low"],6))
                if key in seen:
                    continue
                seen.add(key)
                gaps.append({
                    "axis":axis,
                    "fixed_coordinate_pdf_pts":fixed,
                    "gap_start_pdf_pts":a["high"],
                    "gap_end_pdf_pts":b["low"],
                    "gap_width_pdf_pts":round(gap,6),
                    "first_wall_id":a["wall_candidate_id"],
                    "second_wall_id":b["wall_candidate_id"],
                    "first_w2_edge_id":a["edge_id"],
                    "second_w2_edge_id":b["edge_id"],
                    "first_source_primitive_ids":a["source_primitive_ids"],
                    "second_source_primitive_ids":b["source_primitive_ids"],
                    "native_gap_may_be_real_opening":True,
                    "virtual_wall_bridge_authorized":False,
                })
    return sorted(gaps,key=lambda g:(g["axis"],g["fixed_coordinate_pdf_pts"],g["gap_start_pdf_pts"],g["gap_end_pdf_pts"]))


def inspect_original_source_gaps(pdf_bytes: bytes, source_report: Mapping[str,Any], *,
                                  page_id: str, max_gap_pt:float=2.5,
                                  native_word_filter: str="BED") -> dict:
    if not isinstance(pdf_bytes,bytes) or not pdf_bytes:
        raise ValueError("original PDF required")
    sha=hashlib.sha256(pdf_bytes).hexdigest()
    if source_report.get("source_sha256")!=sha or source_report.get("primitive_safety_cap")!=20_000:
        raise ValueError("original source SHA/cap mismatch")
    scopes=[s for s in source_report.get("source_owned_wall_scopes",())
            if s.get("page_id")==page_id and s.get("source_sha256")==sha]
    if len(scopes)!=1:
        raise ValueError("original page scope unavailable or ambiguous")
    gaps=short_source_gap_candidates(scopes[0],max_gap_pt=max_gap_pt)
    doc=fitz.open(stream=pdf_bytes,filetype="pdf")
    try:
        if not page_id.isdigit() or not (1<=int(page_id)<=len(doc)):
            raise ValueError("invalid original source page")
        page=doc[int(page_id)-1]
        words=page.get_text("words",sort=False)
        native=[dict(text=str(w[4]),bbox=[float(v) for v in w[:4]],
                     source_block=int(w[5]),source_line=int(w[6]),source_word=int(w[7]))
                for w in words if str(w[4]).upper()==native_word_filter.upper()]
        # Bound original render/native-path work to the independently printed
        # room words. This is a diagnostic locality filter, never proof of
        # a physical room owner, polygon, or metric quantity.
        def word_distance(g):
            axis=g["axis"]
            fixed=g["fixed_coordinate_pdf_pts"]
            mid=(g["gap_start_pdf_pts"]+g["gap_end_pdf_pts"])/2
            cx,cy=(fixed,mid) if axis=="vertical" else (mid,fixed)
            return min((math.hypot((w["bbox"][0]+w["bbox"][2])/2-cx,
                                   (w["bbox"][1]+w["bbox"][3])/2-cy)
                        for w in native),default=math.inf)
        gaps=[g for g in sorted(gaps,key=word_distance) if word_distance(g)<=120][:80]
        drawings=page.get_drawings()
        for g in gaps:
            fixed,start,end=(g["fixed_coordinate_pdf_pts"],
                             g["gap_start_pdf_pts"],g["gap_end_pdf_pts"])
            if g["axis"]=="vertical":
                gap_box=fitz.Rect(fixed-2,start-2,fixed+2,end+2)
                anchor=(fixed,(start+end)/2)
            else:
                gap_box=fitz.Rect(start-2,fixed-2,end+2,fixed+2)
                anchor=((start+end)/2,fixed)
            nearby=sorted(((math.hypot((w["bbox"][0]+w["bbox"][2])/2-anchor[0],
                                        (w["bbox"][1]+w["bbox"][3])/2-anchor[1]),w) for w in native),
                          key=lambda x:x[0])
            g["nearest_original_native_room_word_distance_pt"]=round(nearby[0][0],6) if nearby else None
            g["nearby_native_room_words"]=[p[1] for p in nearby[:3] if p[0]<=160]
            source_paths=[]
            for i,path in enumerate(drawings):
                rect=path.get("rect")
                if rect is None or not rect.intersects(gap_box):
                    continue
                items=[]
                for item in path.get("items",()):
                    if item and item[0]=="l":
                        a,b=item[1:3]
                        if fitz.Rect(min(a.x,b.x)-0.05,min(a.y,b.y)-0.05,
                                     max(a.x,b.x)+0.05,max(a.y,b.y)+0.05).intersects(gap_box):
                            items.append([[round(a.x,4),round(a.y,4)],
                                          [round(b.x,4),round(b.y,4)]])
                if items:
                    source_paths.append({"native_draw_path_index":i,
                                         "stroke_color":path.get("color"),
                                         "width":path.get("width"),
                                         "native_lines":items})
            g["original_native_vector_lines_crossing_gap_crop"]=source_paths
            # Original 300DPI FULL page paint only (not images-only); never
            # infer structural line continuation from non-white pixels.
            clip=gap_box & page.rect
            pix=page.get_pixmap(matrix=fitz.Matrix(300/72,300/72),clip=clip,alpha=False)
            buf=pix.samples;step=pix.n
            raw_nonwhite=sum(1 for o in range(0,len(buf),step)
                             if min(buf[o],buf[o+1],buf[o+2])<220)
            g["full_source_crop_nonwhite_pixel_count"]=raw_nonwhite
            g["original_full_render_crop_size"]=[pix.width,pix.height]
            g["positive_wall_role_authorized"]=False
        return {
            "source_sha256":sha,"page_id":page_id,
            "original_room_word_filter_is_diagnostic_only":native_word_filter,
            "original_native_room_words":native,
            "source_gap_count":len(gaps),
            "source_primitive_gaps":gaps,
            "original_wall_gap_snap_is_not_authorized":True,
            "physical_room_face_granted":False,
            "metric_room_area_granted":False,
            "customer_quantity_granted":False,
            "benchmark_score_granted":False,
        }
    finally:
        doc.close()


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--source-report",type=Path,required=True)
    parser.add_argument("--page-id",default="3")
    parser.add_argument("--max-gap-pt",type=float,default=2.5)
    parser.add_argument("--native-room-word",default="BED")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    r=inspect_original_source_gaps(args.pdf.read_bytes(),
                                   json.loads(args.source_report.read_text()),
                                   page_id=args.page_id,max_gap_pt=args.max_gap_pt,
                                   native_word_filter=args.native_room_word)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"page":r["page_id"],"original_sha":r["source_sha256"],
                      "gap_count":r["source_gap_count"],"room_authorized":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
