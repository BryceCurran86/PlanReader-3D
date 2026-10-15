"""Original immutable PDF audit: missing split drawing-title ownership.

This read-only trace separates source text, source title-block suppression,
candidate split-title geometry and genuinely published viewport authority.
Nothing in this module synthesizes a title, wall, finish, room or quantity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_viewport_segmentation import (
    _TITLE_SHAPE_RE, _text_fragments, _title_field_owned_regions,
    _bbox_center, _to_visual_bbox, _point_in_bbox, _normalise_text,
    extract_view_title_anchors, calibrate_viewport_layout,
    extract_vector_frames, segment_page_viewports,
)
from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType

def census(pdf: Path, *, sha: str, page_no: int) -> dict:
    data = pdf.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError("immutable original PDF SHA mismatch")
    with fitz.open(stream=data, filetype="pdf") as doc:
        page=doc.load_page(page_no-1)
        title_regions=_title_field_owned_regions(page)
        raw=page.get_text("dict") or {}
        lines=[]
        for block_number, block in enumerate(raw.get("blocks", [])):
            if block.get("type", 0)!=0:
                continue
            for line_number, line in enumerate(block.get("lines", [])):
                text=_normalise_text(" ".join(str(span.get("text", "")) for span in line.get("spans", ())))
                if not text: continue
                bbox=list(map(float,line.get("bbox", (0,0,0,0))))
                if len(bbox)!=4: continue
                region_membership=[
                    index for index, region in enumerate(title_regions)
                    if _point_in_bbox(_bbox_center(_to_visual_bbox(page,bbox)),region)
                ]
                lines.append(dict(block=block_number,line=line_number,text=text,bbox=bbox,
                                  region_membership=region_membership,
                                  native_dir=list(line.get("dir") or (1.0,0.0)),
                                  source_line_is_full_view_title=bool(_TITLE_SHAPE_RE.fullmatch(text))))
        titlepieces=[i for i,row in enumerate(lines)
                     if ("FLOOR FINISH" in row["text"].upper() or
                         "PARTITIONS PLAN" in row["text"].upper() or
                         "INTERNAL FINISHES SCHEDULE" in row["text"].upper())]
        title_examples=[]
        for i in titlepieces:
            a=lines[i]
            nearby=[]
            for j,b in enumerate(lines):
                if i==j: continue
                if abs((a["bbox"][1]+a["bbox"][3])/2-(b["bbox"][1]+b["bbox"][3])/2)<max(42., 3*(a["bbox"][3]-a["bbox"][1])):
                    nearby.append(dict(index=j,block=b["block"],text=b["text"],bbox=b["bbox"],
                                       region_membership=b["region_membership"]))
            title_examples.append(dict(index=i,source_line=a,nearby_same_source_y=nearby[:40]))
        candidate_title_joins=[]
        for i in titlepieces:
            for j in range(len(lines)):
                if i==j:continue
                a,b=lines[i],lines[j]
                combined=_normalise_text(a["text"]+" "+b["text"])
                if not _TITLE_SHAPE_RE.fullmatch(combined):continue
                view_type=DrawingViewClassifier.classify_text(combined).value
                if view_type==DrawingViewType.UNKNOWN.value:continue
                candidate_title_joins.append(dict(parts=[i,j],texts=[a["text"],b["text"]],
                     blocks=[a["block"],b["block"]],view_type=view_type,
                     both_source_lines=True,
                     title_region_membership=[a["region_membership"],b["region_membership"]],
                     independently_valid_spatial_join=False,
                     publishable_viewport=False))
        anchors=extract_view_title_anchors(page)
        viewport=segment_page_viewports(page,page_number=page_no)
        frames=extract_vector_frames(page,calibrate_viewport_layout(page))
        return dict(original_sha256=sha,page_no=page_no,rotation=page.rotation,
            title_owned_region_bboxes=title_regions,
            title_examples=title_examples,
            candidate_title_joins=candidate_title_joins,
            published_title_anchors=[dict(text=a.text,type=a.view_type,bbox=a.bbox) for a in anchors],
            source_vector_frame_bboxes=frames,
            viewports=[dict(id=v.view_id,type=v.view_type,status=v.status,
                bbox=v.bounding_box,label=v.label,provenance=v.provenance) for v in viewport],
            first_gate="plan_viewport_and_floor_occurrence_owner_unproven",
            diagnostic_only_no_finish_or_quantity=True)

def main():
    p=argparse.ArgumentParser();p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--sha",required=True);p.add_argument("--page",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    x=p.parse_args()
    r=census(x.pdf,sha=x.sha,page_no=x.page)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(r,indent=2,sort_keys=True,default=str)+"\n")
    print("GPT2_ORIGINAL_PAGE11_SPLIT_TITLE_FIRST_FAILURE",json.dumps(r,sort_keys=True,default=str))
if __name__=="__main__":main()
