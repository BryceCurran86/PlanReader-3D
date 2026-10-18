"""Original Lot16 1215 SGW obs crossview label and native SGW legend.

A source-owned window-type LABEL does not imply complete physical opening
existence, cross-page physical SAME, structural host, whole frame or quantity.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import argparse
import json
import fitz

SOURCE_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
MARK_CENTERS={3:(641.7,434.58),5:(576.2,451.01)}


def native_phrase_pairs(page,expected):
    words=page.get_text("words");length=len(expected);matches=[]
    for idx in range(len(words)-length+1):
        seq=words[idx:idx+length]
        if ([str(w[4]).upper() for w in seq]!=[t.upper() for t in expected]
                or len({(w[5],w[6]) for w in seq})!=1
                or any(a[7]+1!=b[7] or a[2]>b[0] for a,b in zip(seq,seq[1:]))):
            continue
        matches.append((min(w[0] for w in seq),min(w[1] for w in seq),
                        max(w[2] for w in seq),max(w[3] for w in seq)))
    return tuple(matches)


def original_1215_semantic_label_receipt(payload):
    if type(payload) is not bytes or sha256(payload).hexdigest()!=SOURCE_SHA:
        raise ValueError("original SHA-verified Lot16 PDF required")
    doc=fitz.open(stream=payload,filetype="pdf")
    try:
        if len(doc)!=13:
            raise ValueError("original Lot16 pages changed")
        output=[]
        for page_number, center in MARK_CENTERS.items():
            page=doc[page_number-1]
            if page.rotation!=0: raise ValueError("original source rotation changed")
            pairs=native_phrase_pairs(page,("1215","SGW","obs"))
            if len(pairs)!=1: raise ValueError("unique native 1215 SGW obs source label unproved")
            bbox=pairs[0];xc=(bbox[0]+bbox[2])/2;yc=(bbox[1]+bbox[3])/2
            if abs(xc-center[0])>3 or abs(yc-center[1])>3:
                raise ValueError("1215 source-label ownership locality changed")
            output.append({"page_number":page_number,"bbox_pdf_pt":list(bbox),
                           "native_text":"1215 SGW obs"})
        words=doc[2].get_text("words")
        code=[w for w in words if str(w[4]).upper()=="SGW" and 30<w[0]<40 and 317<w[1]<321]
        definition=[w for w in words if str(w[4]).upper() in ("SLIDING","GLASS","WINDOW")
                    and 65<w[0]<150 and 317<w[1]<321]
        if (len(code)!=1 or len(definition)!=3
                or [w[4].upper() for w in definition]!=["SLIDING","GLASS","WINDOW"]):
            raise ValueError("source SGW window legend unresolved")
        if any(abs(w[1]-code[0][1])>0.5 for w in definition):
            raise ValueError("SGW definition not printed in same legend row")
        return {"status":"original_1215_sgw_crossview_legend_correspondence",
                "source_sha256":SOURCE_SHA,"native_mark_receipts":output,
                "original_legend":{"code":"SGW","definition":"SLIDING GLASS WINDOW",
                                   "semantic_kind":"window"},
                "original_code_semantics_proven":True,
                "cross_page_physical_same_proven":False,"unique_wall_host_proven":False,
                "opening_count_proven":False,"installed_metric_frame_proven":False,
                "signed_customer_quantity_promoted":False}
    finally:
        doc.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.pdf.resolve()==args.output.resolve():
        raise ValueError("source may not be overwritten")
    report=original_1215_semantic_label_receipt(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")


if __name__=="__main__":
    main()
