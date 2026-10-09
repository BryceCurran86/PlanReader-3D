"""Read-only audit of actual PDF material codes and schedule ownership."""
from collections import Counter
from pathlib import Path
import hashlib, json, re
import fitz
from pb_viewport_segmentation import segment_page_viewports
SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
CODES=re.compile(r"(?<![A-Z0-9])(?:FPB|WFPB|IPF1|GRID)(?![A-Z0-9])",re.I)
SCHEDULE=re.compile(r"(?:FINISH|MATERIAL|CEILING|FLOOR|LINING).{0,40}(?:SCHEDULE|LEGEND)|(?:SCHEDULE|LEGEND).{0,40}(?:FINISH|MATERIAL|CEILING|FLOOR|LINING)",re.I)
if __name__=="__main__":
    payload=SOURCE.read_bytes()
    doc=fitz.open(stream=payload,filetype="pdf")
    report={"source_sha256":hashlib.sha256(payload).hexdigest(),"page_count":len(doc),"matches":[],"schedule_headings":[]}
    for n,page in enumerate(doc,1):
        views=segment_page_viewports(page,page_number=n)
        for block_idx,block in enumerate(page.get_text("dict").get("blocks",[])):
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
                if codes:report["matches"].append({**entry,"codes":codes})
                if heading:report["schedule_headings"].append(entry)
    doc.close()
    Path("maryborough_b02_material_source_audit.json").write_text(json.dumps(report,indent=2,default=str))
    print("B02_SUMMARY",json.dumps({"sha256":report["source_sha256"],"pages":report["page_count"],"matches":len(report["matches"]),"schedule_headings":len(report["schedule_headings"]),"codes":dict(Counter(code for row in report["matches"] for code in row["codes"]))}))
    for group in ("schedule_headings","matches"):
        for entry in report[group][:90]: print("B02_SOURCE_ENTRY",group,json.dumps(entry,default=str))
