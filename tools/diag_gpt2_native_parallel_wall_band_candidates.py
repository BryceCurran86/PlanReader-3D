"""Read-only positive-native-geometry companion stroke census for a source edge.

The exact native PDF path/ink receipt is an input. Pairing opposite parallel
strokes or selecting the nearest stroke does NOT authenticate a physical wall,
source-room face, source scale or metric quantity. The census never reads
benchmark labels, target object IDs or reference quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

import fitz

from tools.diag_gpt2_native_w2_ink_source_role import (
    SOURCE_PDF, SOURCE_SHA, decode_primitive_id, _valid_edge,
    read_native_ink_receipt,
)

def _point(x:Any)->tuple[float,float]:
    return float(x.x),float(x.y)


def _parallel_overlap(
    source_atom:Any, observed:Any
) -> dict[str,float]|None:
    """Unsigned perpendicular distance and overlap from original endpoints.

    Geometric coincidence, by itself, is not source-wall authority.
    """
    a,b=_valid_edge(source_atom)
    c,d=_valid_edge(observed)
    vx,vy=b[0]-a[0],b[1]-a[1]
    wx,wy=d[0]-c[0],d[1]-c[1]
    length=math.hypot(vx,vy)
    other=math.hypot(wx,wy)
    if not (length>0 and other>0):
        return None
    # Scale-independent direction tolerance; do not relax to accept
    # nearby diagonal or nearly perpendicular annotation strokes.
    if abs(vx*wy-vy*wx)/(length*other) > 1e-5:
        return None
    ux,uy=vx/length,vy/length
    distances=tuple((p[0]-a[0])*(-uy)+(p[1]-a[1])*ux for p in (c,d))
    if abs(distances[0]-distances[1])>1e-4:
        return None
    if abs(distances[0])<=1e-4:
        # The existing source line itself or a collinear copy is not evidence
        # of a distinct positive-width wall-band companion.
        return None
    start,end=sorted(tuple((p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (c,d)))
    common=max(0.,min(length,end)-max(0.,start))
    if common<=1e-4:
        return None
    return {
        "source_positive_parallel_offset_pdf_pts":round(distances[0],7),
        "source_positive_parallel_abs_offset_pdf_pts":round(abs(distances[0]),7),
        "overlap_with_original_wall_atom_pdf_pts":round(common,7),
        "original_atom_fully_parallel_covered":bool(
            start<=1e-4 and end>=length-1e-4
        ),
    }


def candidate_parallel_native_strokes(
    drawings:Sequence[dict],
    original_primitive_id:str,
    source_atom_edge:Any,
    *,
    output_limit:int=18,
) -> dict:
    """Source-positive shadow inventory, not a chosen physical wall mate."""
    if not(1<=output_limit<=100):
        raise ValueError("bounded source inventory required")
    src=read_native_ink_receipt(drawings,original_primitive_id,source_atom_edge)
    if not src["native_stroke_fully_covers_atomic_wall_candidate"]:
        raise ValueError("native seed stroke does not own the selected atom")
    source_path,source_item,_=decode_primitive_id(original_primitive_id)
    atom=_valid_edge(source_atom_edge)
    candidates=[]
    for path_index,drawing in enumerate(drawings):
        items=drawing.get("items") or ()
        if not isinstance(items,(list,tuple)):
            continue
        for item_index,item in enumerate(items):
            if path_index==source_path and item_index==source_item:
                continue
            if not isinstance(item,(list,tuple)) or len(item)<3 or item[0]!="l":
                continue
            try:
                geo=(_point(item[1]),_point(item[2]))
                info=_parallel_overlap(atom,geo)
            except (TypeError,ValueError,IndexError,OverflowError,AttributeError):
                continue
            if info is None:continue
            ink=dict(
                kind=drawing.get("type"),
                stroke=drawing.get("color"),
                width_pdf_pts=drawing.get("width"),
                layer=drawing.get("layer"),
                dashes=drawing.get("dashes"),
                seqno=drawing.get("seqno"),
            )
            row={
                "native_source_primitive_id":f"d{path_index}i{item_index}",
                "native_original_edge_pdf_pts":[list(p) for p in geo],
                "native_graphic_state_candidate_only":{
                    k:(list(v) if isinstance(v,tuple) else v)
                    for k,v in ink.items()
                },
                **info,
                "source_wall_band_candidate_only":True,
                "structural_wall_identity_authenticated":False,
            }
            candidates.append(row)
    candidates.sort(key=lambda r:(
        r["source_positive_parallel_abs_offset_pdf_pts"],
        r["native_source_primitive_id"],
    ))
    return {
        "source_selected_primitive_id":original_primitive_id,
        "source_selected_primitive_verified":True,
        "source_original_native_path_count":len(drawings),
        "source_parallel_candidate_count":len(candidates),
        "source_parallel_candidate_first_receipts":candidates[:output_limit],
        "candidate_inventory_truncated":len(candidates)>output_limit,
        "selected_physical_wall_band_companion":None,
        "source_room_composite_closed":False,
        "metric_room_area_published":False,
        "source_wall_role_authenticated":False,
        "benchmark_accuracy_granted":False,
        "original_source_geometry_only":True,
    }


def original(pdf:Path,sha:str,page_no:int,source_id:str,edge:Any)->dict:
    data=pdf.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=sha: raise ValueError("original immutable PDF SHA mismatch")
    with fitz.open(stream=data,filetype="pdf") as doc:
        if not 1<=page_no<=doc.page_count:
            raise ValueError("page out of bounds")
        r=candidate_parallel_native_strokes(doc[page_no-1].get_drawings(),source_id,edge)
        r["original_sha256"]=digest
        r["original_pdf_page"]=page_no
        r["original_pdf_page_count"]=doc.page_count
        return r


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pdf",type=Path,default=SOURCE_PDF)
    p.add_argument("--sha",default=SOURCE_SHA)
    p.add_argument("--page",type=int,required=True)
    p.add_argument("--primitive",required=True)
    p.add_argument("--atomic-edge-json",required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    r=original(a.pdf,a.sha,a.page,a.primitive,json.loads(a.atomic_edge_json))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print("GPT2_NATIVE_PARALLEL_STROKE_CENSUS",json.dumps(r,sort_keys=True))
if __name__=="__main__": main()
