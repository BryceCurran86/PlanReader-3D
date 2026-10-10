"""Source-SHA checked original/proposed RCP viewport first-gate ledger.

Diagnostic only. Neither a title nor a derived sibling viewport proves an
original plan viewport or any material occurrence/metric quantity.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import fitz
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import segment_page_viewports, is_authoritative_derived_viewport, validate_non_overlapping_viewports

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

def audit(source: bytes) -> dict:
    sha=hashlib.sha256(source).hexdigest()
    if sha!=SOURCE_SHA:
        raise ValueError("source_sha_mismatch")
    doc=fitz.open(stream=source,filetype="pdf")
    try:
        if len(doc)!=31:
            raise ValueError("source_page_universe_mismatch")
        page=doc[8]  # Authenticated source page number 9.
        views=segment_page_viewports(page,page_number=9)
        nonoverlap=validate_non_overlapping_viewports(views)
        rows=[]
        for v in views:
            status=str(getattr(v,"status",""))
            typ=str(getattr(v,"view_type",""))
            rows.append({
                "view_id":str(v.view_id),
                "label":str(v.label),
                "view_type":typ,
                "status":status,
                "boundary_source":str(v.boundary_source),
                "bounding_box_pdf_pts":None if v.bounding_box is None else list(v.bounding_box),
                "authoritative_derived":bool(is_authoritative_derived_viewport(v)),
            })
        for row in rows:
            row["first_authority_gate"] = (
                "nonoverlapping_viewports_unproven" if not nonoverlap else
                "missing_source_viewport_boundary" if row["bounding_box_pdf_pts"] is None else
                "source_viewport_resolved" if row["status"].lower().split(".")[-1] == "resolved" else
                "source_derived_viewport_authenticated" if row["authoritative_derived"] else
                "derived_or_ambiguous_viewport_not_authenticated"
            )
        rcps=[row for row in rows if row["view_type"]==DrawingViewType.REFLECTED_CEILING_PLAN.value]
        authoritative=[row for row in rcps if
            row["bounding_box_pdf_pts"] is not None
            and (row["status"].lower().split(".")[-1] == "resolved" or row["authoritative_derived"])
        ]
        return {
            "source_sha256":sha, "source_page_number":9,
            "non_overlapping_source_viewports":bool(nonoverlap),
            "rcp_rows":rcps,"all_viewports":rows,
            "original_view_p9_2_first_gate":next((
                row["first_authority_gate"] for row in rows
                if row["view_id"] == "view_p9_2"
            ), "source_viewport_record_absent"),
            "authenticated_rcp_count":len(authoritative) if nonoverlap else 0,
            "original_rcp_view_p9_2_authenticated":bool(nonoverlap and any(row["view_id"]=="view_p9_2" for row in authoritative)),
            "material_occurrences_published":0,
            "metric_quantities_published":0,
            "diagnostic_only":True,
        }
    finally:
        doc.close()

if __name__=="__main__":
    print("GPT2_PAGE9_ORIGINAL_RCP_FIRST_GATES",json.dumps(audit(PDF.read_bytes()),sort_keys=True))
