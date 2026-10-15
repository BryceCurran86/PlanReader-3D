"""Native original-PDF finish-mark/frame locality diagnostics, NEVER viewport authority.

Source word authentication, native drawing frames and semantic viewport roles
are independent receipts. A coincident or containing rectangle cannot become
a plan, physical floor, material occurrence or customer quantity from a cluster
of repeated text labels. Incomplete plan/legend/schedule coverage ABSTAINS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import fitz

from tools.diag_gpt1_page11_source_plan_ft3_mark_census import source_plan_mark_census
from pb_viewport_segmentation import (
    _frame_looks_like_table,
    _title_field_owned_regions,
    calibrate_viewport_layout,
    extract_vector_frames,
    segment_page_viewports,
)
from pb_drawing_evidence_binding import DrawingViewType

SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")

def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (tuple,list)) or len(value) != 4:
        return None
    try:
        a=tuple(float(v) for v in value)
    except (TypeError,ValueError,OverflowError):
        return None
    return a if all(map(math.isfinite,a)) and a[0]<a[2] and a[1]<a[3] else None

def _contains(outer: tuple[float,float,float,float], inner: tuple[float,float,float,float]) -> bool:
    return all((outer[0]<=inner[0],outer[1]<=inner[1],
                inner[2]<=outer[2],inner[3]<=outer[3]))

def _source_token(value: Any) -> str:
    return getattr(value,"value",value) if isinstance(getattr(value,"value",value),str) else ""

def audit_source_frame_locality(
    mark_census: Mapping[str,Any],
    raw_frames: Sequence[Any],
    viewports: Sequence[Any],
    *,
    expected_sha: str,
    frame_table_roles: Mapping[tuple[float,float,float,float],tuple[bool,bool]]|None=None,
) -> dict:
    """Evidence-only: stable frame-to-word diagnostics and first withheld gate."""
    if mark_census.get("original_source_sha256")!=expected_sha:
        raise ValueError("original source SHA mismatch")
    if str(mark_census.get("page_id"))!="11":
        raise ValueError("only original page 11 source lineage is supported")
    marks=tuple(mark_census.get("marks") or ())
    if not marks:
        raise ValueError("no native source observation evidence")
    counts={}
    for mark in marks:
        ident=mark.get("source_word_observation_id")
        if not isinstance(ident,str) or not ident.startswith("source_observation_"):
            raise ValueError("invalid native observation lineage")
        counts[ident]=counts.get(ident,0)+1
    if any(n!=1 for n in counts.values()):
        raise ValueError("replayed source observation receipt")
    boxes={}
    for ident,mark in ((m["source_word_observation_id"],m) for m in marks):
        bb=_bbox(mark.get("native_bbox_pdf_points"))
        if bb is None:
            raise ValueError("non-finite native mark geometry")
        boxes[ident]=bb
    frames=[_bbox(x) for x in raw_frames]
    if any(b is None for b in frames):
        raise ValueError("unverified native vector frame geometry")
    if len(set(frames))!=len(frames):
        raise ValueError("duplicate original vector frame")
    frame_records=[]
    roles=frame_table_roles or {}
    for bb in sorted(frames):
        ids=sorted(ident for ident,box in boxes.items() if _contains(bb,box))
        line_grid,closed_cells=roles.get(bb,(False,False))
        frame_records.append({
            "native_frame_bbox_pdf_pts":list(bb),
            "whole_source_mark_observation_ids":ids,
            "whole_mark_count":len(ids),
            "source_has_table_like_line_grid":bool(line_grid),
            "source_has_closed_schedule_cells":bool(closed_cells),
            "candidate_only_not_a_source_plan_owner":True,
            "new_plan_viewport_published":False,
        })
    source_plan_owners=[
        v for v in viewports
        if _source_token(getattr(v,"view_type",None))==DrawingViewType.FLOOR_FINISH_PLAN.value
        and _source_token(getattr(v,"status",None))=="resolved"
        and _bbox(getattr(v,"bounding_box",None)) is not None
    ]
    authenticated_plan_owners=[]
    for v in source_plan_owners:
        if not mark_census.get("viewports_non_overlapping"):
            continue
        # The original viewport product already carries its source producer
        # identity. It is never minted from raw vector frame coincidences.
        from pb_viewport_segmentation import is_segment_page_viewports_product
        if is_segment_page_viewports_product(v):
            authenticated_plan_owners.append(v)
    candidate_mark_ids=set(k for fr in frame_records for k in fr["whole_source_mark_observation_ids"])
    source_verified=all(m.get("source_text_verified") is True for m in marks)
    source_only=not (len(authenticated_plan_owners)==1 and source_verified)
    return {
        "original_source_sha256":expected_sha,
        "page_id":"11",
        "source_mark_count":len(marks),
        "all_native_source_mark_text_authenticated":source_verified,
        "original_native_frame_count":len(frame_records),
        "native_frames_source_first_gates":frame_records,
        "original_source_uncontained_mark_observation_ids":sorted(set(counts)-candidate_mark_ids),
        "single_native_frame_max_whole_mark_count":max((r["whole_mark_count"] for r in frame_records),default=0),
        "authenticated_floor_finish_plan_viewport_count":len(authenticated_plan_owners),
        "source_first_unclosed_authority":(
            "source_plan_viewport_unresolved" if source_only else
            "material_occurrence_and_physical_floor_ownership_unresolved"
        ),
        "native_source_frame_is_not_floor_finish_plan_authority":True,
        "material_occurrence_universe_complete":False,
        "physical_floor_source_ownership_authenticated_by_audit":False,
        "metric_floor_finish_area_published":False,
        "new_customer_quantity_published":False,
        "benchmark_identity_or_score_granted":False,
        "diagnostic_only":True,
    }

def from_original(pdf:Path,expected_sha:str) -> dict:
    payload=pdf.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=expected_sha:
        raise ValueError("original PDF SHA mismatch")
    census=source_plan_mark_census(
        pdf,original_sha256=expected_sha,source_page=11,code="FT3"
    )
    with fitz.open(stream=payload,filetype="pdf") as doc:
        assert doc.page_count==31
        page=doc[10]
        assert page.rotation==90
        cal=calibrate_viewport_layout(page)
        frames=tuple(extract_vector_frames(page,cal))
        views=tuple(segment_page_viewports(page,page_number=11))
        roles={tuple(f):(
            bool(_frame_looks_like_table(f,page,cal)),
            bool(_frame_looks_like_table(f,page,cal,allow_line_grid_only=False)),
        ) for f in frames}
        report=audit_source_frame_locality(
            census,frames,views,expected_sha=expected_sha,frame_table_roles=roles
        )
        report["native_page_rotation"]=page.rotation
        report["source_title_field_count"]=len(_title_field_owned_regions(page))
        return report

def main(argv:Sequence[str]|None=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,default=PDF)
    parser.add_argument("--source-sha256",default=SHA)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    report=from_original(args.pdf,args.source_sha256)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("GPT2_ORIGINAL_FT3_NATIVE_FRAME_SOURCE_FIRST_GATE",json.dumps(report,sort_keys=True))
if __name__=="__main__":
    main()
