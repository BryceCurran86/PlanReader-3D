"""Original PDF native path/ink first gate for a W2 -> W4 source edge.

This tool inspects only an exact producer-provided PDF primitive reference;
neither native ink nor W2 source ancestry proves that a line is a physical
wall rather than a drafting grid or annotation. No room topology, wall
identity, quantity, score or benchmark data are produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

import fitz

_IDENTIFIER=re.compile(r"^d([0-9]+)i([0-9]+)(?:e([0-3]))?$")
SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
SOURCE_PDF="documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"


def decode_primitive_id(value:str)->tuple[int,int,int|None]:
    if not isinstance(value,str) or not value or value.strip()!=value:
        raise ValueError("native path primitive reference is malformed")
    m=_IDENTIFIER.fullmatch(value)
    if m is None:
        raise ValueError("native path primitive reference is malformed")
    path,item,edge=int(m[1]),int(m[2]),int(m[3]) if m[3] is not None else None
    return path,item,edge


def _valid_edge(edge:Any)->tuple[tuple[float,float],tuple[float,float]]:
    try:
        a,b=edge
        first=tuple(float(v) for v in a)
        second=tuple(float(v) for v in b)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("selected native wall edge invalid")
    if (len(first)!=2 or len(second)!=2 or not all(map(math.isfinite,(*first,*second)))
        or first==second):
        raise ValueError("selected native wall edge invalid")
    return first,second


def _point(v:Any)->tuple[float,float]:
    return (float(v.x),float(v.y))


def read_native_ink_receipt(
    drawings:Sequence[dict], primitive_id:str,
    source_atom_edge:Any,
) -> dict:
    """Exact original path and item, never infer a nearby replacement."""
    path,item,edge_index=decode_primitive_id(primitive_id)
    atom=_valid_edge(source_atom_edge)
    if path>=len(drawings):
        raise ValueError("native path index absent from original source")
    drawing=drawings[path]
    items=drawing.get("items") or []
    if item>=len(items):
        raise ValueError("native item index absent from original source")
    primitive=items[item]
    if not primitive or primitive[0] not in ("l","re"):
        raise ValueError("unsupported native primitive shape")
    if primitive[0]=="l":
        if edge_index is not None:
            raise ValueError("line primitive cannot specify a rectangle edge")
        source_edge=(_point(primitive[1]),_point(primitive[2]))
    else:
        if edge_index is None:
            raise ValueError("native rectangle edge index required")
        rect=fitz.Rect(primitive[1])
        vertices=((rect.x0,rect.y0),(rect.x1,rect.y0),
                  (rect.x1,rect.y1),(rect.x0,rect.y1))
        source_edge=vertices[edge_index],vertices[(edge_index+1)%4]
    src=_valid_edge(source_edge)
    sx,sy=src[0];ex,ey=src[1]
    vx,vy=ex-sx,ey-sy
    length=math.hypot(vx,vy)
    def project(p):
        return ((p[0]-sx)*vx+(p[1]-sy)*vy)/(length*length)
    cross=[abs((p[0]-sx)*vy-(p[1]-sy)*vx)/length for p in atom]
    t0,t1=sorted(project(p) for p in atom)
    full=bool(max(cross)<=1e-4 and t0>=-1e-5 and t1<=1.+1e-5)
    metadata={
        "native_drawing_kind":drawing.get("type"),
        "native_path_seqno":drawing.get("seqno"),
        "native_stroke_width":drawing.get("width"),
        "native_line_dashes":drawing.get("dashes"),
        "native_layer":drawing.get("layer"),
        "native_stroke_color":drawing.get("color"),
        "native_fill_color":drawing.get("fill"),
        "native_fill_opacity":drawing.get("fill_opacity"),
    }
    def as_json_scalar(value):
        if isinstance(value,(str,int,float,bool,type(None))):return value
        if isinstance(value,(tuple,list)):return [as_json_scalar(v) for v in value]
        return str(value)
    metadata={k:as_json_scalar(v) for k,v in metadata.items()}
    return {
        "original_native_primitive_ref":primitive_id,
        "original_path_index":path,
        "original_item_index":item,
        "original_rectangle_edge_index":edge_index,
        "native_path_count":len(drawings),
        "native_path_item_count":len(items),
        "native_element_kind":primitive[0],
        "native_source_edge_pdf_pts":[list(p) for p in src],
        "original_atomic_edge_pdf_pts":[list(p) for p in atom],
        "native_stroke_fully_covers_atomic_wall_candidate":full,
        "native_stroke_contains_candidate_only_not_wall_role":True,
        "original_native_paint_metadata_candidate_only":metadata,
        "structural_wall_role_authenticated":False,
        "source_room_face_closed_by_tool":False,
        "quantity_or_metric_area_published":False,
        "diagnostic_only":True,
    }


def original_source_receipt(
    path:Path,sha:str,page_no:int,
    primitive_id:str,atom:Any
)->dict:
    source=path.read_bytes()
    actual=hashlib.sha256(source).hexdigest()
    if actual!=sha:raise ValueError("original source PDF SHA mismatch")
    with fitz.open(stream=source,filetype="pdf") as pdf:
        if not(1<=page_no<=pdf.page_count):raise ValueError("invalid original PDF page")
        result=read_native_ink_receipt(
            pdf[page_no-1].get_drawings(),primitive_id,atom
        )
        result["source_sha256"]=actual
        result["original_pdf_page"]=page_no
        result["original_pdf_page_count"]=pdf.page_count
        return result


def main(argv:Sequence[str]|None=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,default=SOURCE_PDF)
    parser.add_argument("--sha",default=SOURCE_SHA)
    parser.add_argument("--page",type=int,required=True)
    parser.add_argument("--primitive",required=True)
    parser.add_argument("--atomic-edge-json",required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args(argv)
    report=original_source_receipt(a.pdf,a.sha,a.page,a.primitive,json.loads(a.atomic_edge_json))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("GPT2_ORIGINAL_NATIVE_W2_INK_WASHUP_FIRST_GATE",json.dumps(report,sort_keys=True))
if __name__=="__main__":
    main()
