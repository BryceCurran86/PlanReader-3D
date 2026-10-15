"""Original PDF exact native line/rectangle ink census for source W4 edge queries.

Caller provides already source-receipted atom edge coordinates. No physical
wall identity, room polygon, area or customer output is issued by this tool.
A negative concerns original indexed LINE/RECT spans only; curved/filled raster
ink and its source-visible status are separate independent authorities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from tools.diag_gpt2_native_w2_ink_source_role import (
    _valid_edge, read_native_ink_receipt,
)


def census_original_native_linear_ink(drawings, *, source_atoms):
    if not isinstance(drawings, (list, tuple)) or not drawings:
        raise ValueError("original_native_drawing_universe_unavailable")
    atoms=[]
    for source_atom in source_atoms:
        atom=_valid_edge(source_atom)
        if atom in atoms:
            raise ValueError("duplicate_original_producer_atom_query")
        atoms.append(atom)
    if not atoms:
        raise ValueError("missing_original_producer_atom_queries")
    unsupported=0
    searchable=0
    degenerate_original_linear_refs=set()
    reports=[]
    for atom in atoms:
        matches=[]
        for path, drawing in enumerate(drawings):
            for index, item in enumerate(drawing.get("items") or []):
                if not item or item[0] not in ("l","re"):
                    unsupported+=1
                    continue
                edge_indexes = (None,) if item[0]=="l" else (0,1,2,3)
                for side in edge_indexes:
                    primitive_id=f"d{path}i{index}"
                    if side is not None:
                        primitive_id+=f"e{side}"
                    try:
                        receipt=read_native_ink_receipt(drawings,primitive_id,atom)
                    except ValueError as exc:
                        # Original PDF can contain zero-area rectangles and
                        # same-endpoint lines. Retain exact rejected source ID,
                        # without treating it as a missing real ink witness.
                        if str(exc)!="selected native wall edge invalid":
                            raise
                        degenerate_original_linear_refs.add(primitive_id)
                        continue
                    searchable+=1
                    if receipt["native_stroke_fully_covers_atomic_wall_candidate"]:
                        matches.append(receipt)
                        if len(matches)>10000:
                            raise ValueError("original_native_linear_ink_candidate_safety_bound")
        matches.sort(key=lambda x:(
            x["original_path_index"],x["original_item_index"],
            -1 if x["original_rectangle_edge_index"] is None
            else x["original_rectangle_edge_index"]))
        reports.append({
            "original_source_candidate_atom_pdf_pts":[list(p) for p in atom],
            "original_indexed_linear_native_full_span_count":len(matches),
            "original_indexed_native_linear_receipts":matches,
            "native_full_span_observed_not_structural_authority":True,
            "source_structural_wall_role_authenticated":False,
            "source_room_ring_closed":False,
            "metric_quantity_published":False,
        })
    return {
        "source_query_atom_count":len(atoms),
        "original_native_indexed_drawing_path_count":len(drawings),
        "original_linear_rect_source_primitive_checks":searchable,
        "original_indexed_degenerate_linear_source_ids":sorted(
            degenerate_original_linear_refs
        ),
        "original_indexed_degenerate_linear_source_count":len(
            degenerate_original_linear_refs
        ),
        "other_native_element_count_not_assessed":unsupported,
        "source_native_linear_ink_queries":reports,
        "all_original_source_line_rect_items_examined":True,
        "complete_native_ink_universe_including_curves_raster":False,
        "source_role_or_room_authentication_granted":False,
        "new_commercial_quantities":[],
        "frozen_benchmark_scored":False,
        "diagnostic_only":True,
    }


def replay_original_source(pdf_bytes: bytes,*, original_sha256: str,
                           page_no: int, source_atoms):
    if type(pdf_bytes) is not bytes or type(page_no) is not int or page_no<1:
        raise ValueError("original_source_pdf_bytes_and_page_required")
    actual=hashlib.sha256(pdf_bytes).hexdigest()
    if actual!=original_sha256:
        raise ValueError("original_source_sha_mismatch")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_no>doc.page_count:
            raise ValueError("original_source_page_missing")
        result=census_original_native_linear_ink(
            doc[page_no-1].get_drawings(),source_atoms=source_atoms
        )
        result["original_pdf_page_count"]=doc.page_count
    result["original_source_sha256"]=actual
    result["original_page"]=page_no
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--page",type=int,required=True)
    p.add_argument("--original-w4-edges-json",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=replay_original_source(
        args.pdf.read_bytes(), original_sha256=args.sha,page_no=args.page,
        source_atoms=json.loads(args.original_w4_edges_json),
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("GPT2_ORIGINAL_P7_W4_NATIVE_LINEAR_FIRSTGATE",json.dumps({
        "source_sha256":report["original_source_sha256"],
        "page":report["original_page"],
        "indexed_source_fullspan_counts":[
            row["original_indexed_linear_native_full_span_count"]
            for row in report["source_native_linear_ink_queries"]
        ],
        "source_structural_wall_role_authenticated":False,
        "new_commercial_quantities":[],
    },sort_keys=True))


if __name__=="__main__":
    main()
