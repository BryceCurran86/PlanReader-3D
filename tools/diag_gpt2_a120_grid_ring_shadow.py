"""Original-source stroked GRID ceiling enclosure shadow; no quantity authority.

White masking rectangles are not ink. All four native line paths and competing
marks remain source candidates; no PDF scale, W4 room or FIRM quantity is issued.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import fitz


@dataclass(frozen=True)
class NativeLine:
    axis: str
    coordinate: float
    low: float
    high: float
    path_id: int
    item_id: int
    width_pt: float


def _stroked_lines(page, min_span_pt: float):
    result = []
    drawings = page.get_drawings()
    if len(drawings) > 120000:
        raise ValueError("source_drawing_universe_exceeds_shadow_bound")
    for i, draw in enumerate(drawings):
        width = draw.get("width")
        if (draw.get("type") != "s" or draw.get("color") != (0., 0., 0.)
            or type(width) not in (int, float) or not math.isfinite(width)
            or width <= 0 or draw.get("stroke_opacity") != 1):
            continue
        for j, item in enumerate(draw.get("items") or ()):
            if len(item) < 3 or item[0] != "l":
                continue
            p0, p1 = item[1:3]
            if abs(p0.y-p1.y) <= min(width*0.05, 0.03) and abs(p0.x-p1.x) >= min_span_pt:
                result.append(NativeLine("h", (p0.y+p1.y)/2, min(p0.x,p1.x), max(p0.x,p1.x), i,j,width))
            elif abs(p0.x-p1.x) <= min(width*0.05, 0.03) and abs(p0.y-p1.y) >= min_span_pt:
                result.append(NativeLine("v", (p0.x+p1.x)/2, min(p0.y,p1.y), max(p0.y,p1.y), i,j,width))
    if len(result) > 10000:
        raise ValueError("source_long_line_universe_exceeds_shadow_bound")
    return result


def _interior_source_grid_ink_shadow(page, box):
    """Reject an ordinary empty rectangle with a GRID word but no 2-axis ink."""
    x0,y0,x1,y1 = box
    width,height = x1-x0,y1-y0
    if width <= 0 or height <= 0:
        return None
    margin = max(1.0, min(width,height)*0.001)
    min_length = max(5.0, min(width,height)*0.06)
    source_axes = {"h": {}, "v": {}}
    drawings = page.get_drawings()
    if len(drawings) > 120000:
        return None
    for path_id,draw in enumerate(drawings):
        stroke_width = draw.get("width")
        if (draw.get("type") != "s" or draw.get("color") != (0.,0.,0.)
            or draw.get("stroke_opacity") != 1
            or type(stroke_width) not in (float,int)
            or not math.isfinite(stroke_width) or stroke_width <= 0):
            continue
        for item_id,item in enumerate(draw.get("items") or ()):
            if len(item) < 3 or item[0] != "l":
                continue
            a,b = item[1:3]
            if not (x0+margin < a.x < x1-margin and y0+margin < a.y < y1-margin
                    and x0+margin < b.x < x1-margin and y0+margin < b.y < y1-margin):
                continue
            if abs(a.y-b.y) < 0.03 and abs(a.x-b.x) >= min_length:
                axis = "h"; coordinate = (a.y+b.y)*0.5
            elif abs(a.x-b.x) < 0.03 and abs(a.y-b.y) >= min_length:
                axis = "v"; coordinate = (a.x+b.x)*0.5
            else:
                continue
            source_axes[axis].setdefault(round(coordinate,2),set()).add((path_id,item_id))
    if any(len(positions) < 4 for positions in source_axes.values()):
        return None
    return {
        "source_interior_grid_h_positions":len(source_axes["h"]),
        "source_interior_grid_v_positions":len(source_axes["v"]),
        "source_interior_grid_h_path_ids":tuple(sorted({
            path_id for pairs in source_axes["h"].values() for path_id,_ in pairs
        })),
        "source_interior_grid_v_path_ids":tuple(sorted({
            path_id for pairs in source_axes["v"].values() for path_id,_ in pairs
        })),
        "grid_lattice_evidence_tier":"original_black_stroked_candidate_only",
    }


def original_stroked_grid_rectangles_shadow(page, *, min_span_pt: float = 200.0, code: str = "GRID"):
    """Enumerate all source-line quartets: never choose first or nearest."""
    if (type(min_span_pt) not in (int, float)
            or not math.isfinite(min_span_pt) or min_span_pt <= 0):
        raise ValueError("finite_positive_min_span_required")
    if type(code) is not str or not code.isalpha() or code.upper() != code:
        raise ValueError("literal_material_code_required")
    words = tuple(page.get_text("words"))
    marks = tuple(w for w in words if str(w[4]).strip() == code)
    candidates = []
    segments = _stroked_lines(page,min_span_pt)
    horizontal = [a for a in segments if a.axis == "h"]
    vertical = [a for a in segments if a.axis == "v"]
    for i,top in enumerate(horizontal):
        for bottom in horizontal[i+1:]:
            gap = max(top.width_pt,bottom.width_pt)*1.05
            if abs(top.low-bottom.low) > gap or abs(top.high-bottom.high) > gap:
                continue
            if abs(top.coordinate-bottom.coordinate) < min_span_pt:
                continue
            x0 = (top.low+bottom.low)*0.5
            x1 = (top.high+bottom.high)*0.5
            y0,y1 = sorted((top.coordinate,bottom.coordinate))
            # Tolerance is proportional to source STROKE WIDTH, not the
            # physical W2 wall snap or a guess at page dimensions.
            def matched(x):
                return [v for v in vertical
                    if abs(v.coordinate-x) <= max(v.width_pt,gap)*1.05
                    and abs(v.low-y0) <= max(v.width_pt,gap)*1.05
                    and abs(v.high-y1) <= max(v.width_pt,gap)*1.05]
            left,right = matched(x0),matched(x1)
            if not left or not right:
                continue
            inside = [w for w in marks
                if x0 < (w[0]+w[2])/2 < x1 and y0 < (w[1]+w[3])/2 < y1]
            if len(inside) != 1:
                continue
            rival_codes = ("GRID","IP","IPF1","FPB","WFPB")
            rivals = [w for w in words
                if w[4] in rival_codes and w[4] != code
                and x0 < (w[0]+w[2])/2 < x1 and y0 < (w[1]+w[3])/2 < y1]
            if rivals:
                continue
            lattice = _interior_source_grid_ink_shadow(page,(x0,y0,x1,y1))
            if lattice is None:
                continue
            for l in left:
                for r in right:
                    ids = (top.path_id,bottom.path_id,l.path_id,r.path_id)
                    if len(set(ids)) != 4:
                        continue
                    candidates.append(dict(
                        bbox_pdf_pts=[round(x,5) for x in (x0,y0,x1,y1)],
                        source_path_ids=ids,
                        source_mark_address=tuple(inside[0][5:8]),
                        **lattice,
                        original_stroked_perimeter_pt=round(2*((x1-x0)+(y1-y0)),5),
                        source_graphic_area_pt2=round((x1-x0)*(y1-y0),5),
                        physical_room_source_authority=False,
                        source_scale_authority=False,
                        firm_quantity_m2=None,
                    ))
    candidates.sort(key=lambda row:(row["bbox_pdf_pts"],row["source_path_ids"]))
    return dict(
        status="candidate_source_stroked_ceiling_region" if candidates else "unresolved",
        material_code=code,candidate_count=len(candidates),candidates=candidates,
        first_unclosed_gate="source_producer_viewport_wall_and_material_ownership",
        new_firm_quantities=0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf",required=True)
    ap.add_argument("--sha256",required=True)
    ap.add_argument("--page",type=int,required=True)
    ap.add_argument("--min-span-pt",type=float,default=200.0)
    args = ap.parse_args()
    data = Path(args.pdf).read_bytes()
    if hashlib.sha256(data).hexdigest() != args.sha256:
        raise SystemExit("private_source_sha_mismatch")
    with fitz.open(stream=data,filetype="pdf") as doc:
        if args.page < 1 or args.page > len(doc):
            raise SystemExit("source_page_range")
        result = original_stroked_grid_rectangles_shadow(
            doc[args.page-1],min_span_pt=args.min_span_pt,
        )
    result["original_source_sha256"] = args.sha256
    result["original_page_number"] = args.page
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
