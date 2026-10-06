from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_cross_view_room_area_authority as cross_view
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "11"
TARGETS = ("AIRLOCK", "LAUNDRY", "PWD", "OFFICE")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="gpt2-a140-four-room-gates-diag",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )

    trusted=cross_view._trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_labels=TARGETS,
    )
    results={}
    for target in TARGETS:
        lines=tuple(line for line in trusted if _norm(line.text)==target)
        dims=(
            cross_view._trusted_native_dimensions_for_page(
                source,
                revision_id=published.revision.revision_id,
                page_id=PAGE_ID,
                candidate_lines=lines,
            )
            if lines else ()
        )
        hs=tuple(d for d in dims if d.orientation==cross_view.DimensionOrientation.HORIZONTAL.value)
        vs=tuple(d for d in dims if d.orientation==cross_view.DimensionOrientation.VERTICAL.value)

        spatial=[]
        scale=[]
        witness=[]
        for line in lines:
            for h in hs:
                for v in vs:
                    if not cross_view._line_inside_dimension_pair(line,h,v):
                        continue
                    spatial.append((h.dimension_id,v.dimension_id))
                    if not cross_view._figured_pair_scale_consistent(
                        page_id=PAGE_ID,
                        horizontal=h,
                        vertical=v,
                    ):
                        continue
                    scale.append((h.dimension_id,v.dimension_id))
                    if cross_view._witness_systems_intersect(h,v):
                        witness.append((h.dimension_id,v.dimension_id))

        owned_h=[
            (line.text,d.dimension_id)
            for line in lines
            for d in hs
            if cross_view._dimension_is_immediate_label_annotation(line,d)
        ]
        owned_v=[
            (line.text,d.dimension_id)
            for line in lines
            for d in vs
            if cross_view._dimension_is_immediate_label_annotation(line,d)
        ]
        annotation_pairs=[]
        for _,hid in owned_h:
            h=next(d for d in hs if d.dimension_id==hid)
            for _,vid in owned_v:
                v=next(d for d in vs if d.dimension_id==vid)
                if cross_view._figured_pair_scale_consistent(
                    page_id=PAGE_ID,
                    horizontal=h,
                    vertical=v,
                ):
                    annotation_pairs.append((hid,vid))

        results[target]={
            "trusted_line_count":len(lines),
            "trusted_lines":[
                {
                    "text":line.text,
                    "bbox":list(line.bbox),
                    "block_no":line.block_no,
                    "line_no":line.line_no,
                    "source_partition_id":line.source_partition_id,
                }
                for line in lines
            ],
            "trusted_dimension_count":len(dims),
            "horizontal_count":len(hs),
            "vertical_count":len(vs),
            "trusted_dimensions":[
                {
                    "dimension_id":str(d.dimension_id),
                    "orientation":str(d.orientation),
                    "value_mm":float(d.value_mm),
                    "endpoints_pt":[list(d.endpoints_pt[0]),list(d.endpoints_pt[1])],
                    "text_block_no":d.text_block_no,
                    "text_line_no":d.text_line_no,
                    "text_word_no":d.text_word_no,
                }
                for d in dims
            ],
            "spatial_pair_count":len(spatial),
            "scale_consistent_pair_count":len(scale),
            "witness_intersecting_pair_count":len(witness),
            "annotation_horizontal_count":len(owned_h),
            "annotation_vertical_count":len(owned_v),
            "annotation_pair_count":len(annotation_pairs),
        }

    print(json.dumps({
        "source_sha256":sha,
        "page_id":PAGE_ID,
        "mode":"DIAGNOSTIC_ONLY_A140_FIGURED_DIMENSION_GATES",
        "targets":results,
    },indent=2,sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
