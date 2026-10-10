"""Read-only audit of actual PDF material codes and schedule ownership."""
from collections import Counter
from pathlib import Path
import hashlib, json, re
import fitz
from pb_viewport_segmentation import segment_page_viewports
from pb_material_schedule_v1222 import parse_schedule_text, semantic_finish_from_schedule_entry
SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
CODES=re.compile(r"(?<![A-Z0-9])(?:FPB|WFPB|IPF1|GRID|FT2|FT3)(?![A-Z0-9])",re.I)
SCHEDULE=re.compile(r"(?:FINISH|MATERIAL|CEILING|FLOOR|LINING).{0,40}(?:SCHEDULE|LEGEND)|(?:SCHEDULE|LEGEND).{0,40}(?:FINISH|MATERIAL|CEILING|FLOOR|LINING)",re.I)
def _native_lateral_row_neighbours(blocks, code_bbox, code_block):
    """Native sibling text cell candidates; proximity is never authentication.

    Only enumerate distinct text blocks at the same vertical drawing baseline
    and return their exact PDF block IDs/bounds for independent schedule-row
    structure and source-word verification. Never parse adjacent text as a
    definition or assign any material to a room.
    """
    x0,y0,x1,y1=(float(v) for v in code_bbox)
    height=y1-y0
    if height<=0:
        return []
    out=[]
    for idx,block in enumerate(blocks):
        if idx==code_block or block.get("type")!=0:
            continue
        bbox=block.get("bbox")
        if bbox is None or len(bbox)<4:
            continue
        bx0,by0,bx1,by1=(float(v) for v in bbox[:4])
        inter_y=max(0.0,min(y1,by1)-max(y0,by0))
        if inter_y < .45*min(height,max(0.,by1-by0)):
            continue
        gap=max(bx0-x1,x0-bx1,0.0)
        if gap > max(250.,height*12):
            continue
        words=[
            str(span.get("text") or "").strip()
            for line in block.get("lines",[])
            for span in line.get("spans",[])
            if str(span.get("text") or "").strip()
        ]
        if not words:
            continue
        out.append({
            "native_block_no":idx,
            "bbox":[bx0,by0,bx1,by1],
            "horizontal_gap_pdf_pts":round(gap,3),
            "text":" ".join(words)[:160],
            "candidate_only":True,
        })
    return sorted(out,key=lambda x:(x["horizontal_gap_pdf_pts"],x["native_block_no"]))[:12]

if __name__=="__main__":
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    if sha!="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007":
        raise RuntimeError("immutable_maryborough_source_sha_mismatch")
    doc=fitz.open(stream=payload,filetype="pdf")
    if doc.page_count!=31:
        raise RuntimeError("unexpected_source_page_count")
    report={"source_sha256":sha,"page_count":len(doc),"scoped_source_pages":[9,11],"matches":[],"schedule_headings":[]}
    # Scan only independently identified source schedule/finish pages, not
    # the entire document through an expensive plan segmentation pass.
    for n in (9,11):
        page=doc.load_page(n-1)
        views=segment_page_viewports(page,page_number=n)
        native_blocks=page.get_text("dict").get("blocks",[])
        for block_idx,block in enumerate(native_blocks):
            if block.get("type")!=0: continue
            lines=[" ".join(str(span.get("text","")).strip() for span in line.get("spans",[]) if str(span.get("text","")).strip()) for line in block.get("lines",[])]
            for line_idx,raw in enumerate(lines):
                val=raw.strip()
                if not val:continue
                codes=sorted(set(x.upper() for x in CODES.findall(val)))
                heading=bool(SCHEDULE.search(val))
                if not codes and not heading:continue
                bbox=block.get("lines",[])[line_idx].get("bbox",block.get("bbox"))
                cx=(bbox[0]+bbox[2])/2;cy=(bbox[1]+bbox[3])/2
                owners=[{"view":v.view_id,"type":v.view_type,"status":v.status} for v in views if v.bounding_box and v.bounding_box[0]<=cx<=v.bounding_box[2] and v.bounding_box[1]<=cy<=v.bounding_box[3]]
                entry={"page":n,"block":block_idx,"line":line_idx,"text":val[:240],"bbox":bbox,"viewport_owners":owners,"surrounding_lines":lines[max(0,line_idx-2):line_idx+3]}
                if codes:
                    if any(c in ("FT2","FT3") for c in codes):
                        entry["native_same_row_neighbours"] = (
                            _native_lateral_row_neighbours(
                                native_blocks, bbox, block_idx,
                            )
                        )
                        entry["neighbour_row_is_authenticated"] = False
                    heading_lines = [i for i, line in enumerate(lines) if SCHEDULE.search(line)]
                    description = CODES.sub("", val).strip(" :;-")
                    exact_code_line = len(codes) == 1 and val.upper() == codes[0]
                    following_lines = [v.strip() for v in lines[line_idx + 1:line_idx + 5] if v.strip()]
                    next_line = following_lines[0] if following_lines else ""
                    next_line_is_description = bool(
                        exact_code_line and next_line
                        and not CODES.search(next_line)
                        and not SCHEDULE.search(next_line)
                        and re.search(r"[A-Z]{3,}", next_line, re.I)
                    )
                    # A block may put a role (e.g. CONTRACTOR) before the
                    # actual specification. Never equate the first trailing
                    # line with an authenticated material meaning.
                    candidate_description_lines = [
                        t for t in following_lines
                        if len(t.split()) >= 2
                        and bool(re.search(r"[A-Za-z]{4,}", t))
                        and not CODES.search(t)
                        and not SCHEDULE.search(t)
                    ]
                    ambiguous_multiline = len(following_lines) > 1
                    # Exercise the *actual* production schedule parser, not a
                    # hand-coded acronym dictionary. Parsing alone is never
                    # source-word authenticity or schedule-row ownership.
                    parsed_rows = []
                    if exact_code_line and following_lines:
                        combined = "\n".join([val, *following_lines])
                        for item in parse_schedule_text(
                            combined, page_id=n, page_label=f"page:{n}"
                        ):
                            parsed_code = str(item.get("code") or "").upper()
                            if parsed_code != codes[0]:
                                continue
                            entry = {
                                "status": "Confirmed",
                                "code": parsed_code,
                                "description": str(item.get("description") or ""),
                                "substrate": str(item.get("substrate") or ""),
                                "finish": str(item.get("finish") or ""),
                            }
                            parsed_rows.append({
                                "code": parsed_code,
                                "description": entry["description"],
                                "semantic_finish_candidate": semantic_finish_from_schedule_entry(entry),
                            })
                    proof = {
                        "production_parser_candidates": parsed_rows,
                        "first_parser_gate": (
                            "BARE_ALPHA_CODE_NOT_RECOGNISED"
                            if exact_code_line and following_lines and not parsed_rows
                            else "PARSER_CANDIDATE_ONLY" if parsed_rows
                            else "NO_COMPLETE_CODE_DESCRIPTION_ROW"
                        ),
                        "parser_is_not_authority": True,
                        "candidate_description_lines": candidate_description_lines,
                        "multiline_row_requires_independent_binding": ambiguous_multiline,
                        "following_native_lines": following_lines,
                        "next_native_line": next_line if next_line_is_description else None,
                        "requires_row_ownership_verification": True,
                        "code_followed_by_text_in_native_block": next_line_is_description,
                        "native_block_schedule_heading_lines": heading_lines,
                        "same_block_schedule_heading": bool(heading_lines),
                        "same_line_description_present": bool(description),
                        "source_definition_candidate_only": bool(heading_lines and description and not ambiguous_multiline),
                        "authenticated_definition": False,
                        "reason": "Text proximity is not authenticated definition authority",
                    }
                    report["matches"].append({**entry, "codes": codes, "proof": proof})
                if heading:report["schedule_headings"].append(entry)
    report["code_proof_summary"] = {
        code: {
            "occurrences": sum(code in row["codes"] for row in report["matches"]),
            "same_block_schedule_candidates": sum(
                code in row["codes"] and row["proof"]["source_definition_candidate_only"]
                for row in report["matches"]
            ),
            "definition_authority_evaluated": False,
        } for code in ("FPB", "WFPB", "IPF1", "GRID", "FT2", "FT3")
    }
    doc.close()
    Path("maryborough_b02_material_source_audit.json").write_text(json.dumps(report,indent=2,default=str))
    print("B02_SUMMARY",json.dumps({"sha256":report["source_sha256"],"pages":report["page_count"],"matches":len(report["matches"]),"schedule_headings":len(report["schedule_headings"]),"codes":dict(Counter(code for row in report["matches"] for code in row["codes"]))}))
    for group in ("schedule_headings","matches"):
        for entry in report[group][:90]: print("B02_SOURCE_ENTRY",group,json.dumps(entry,default=str))
