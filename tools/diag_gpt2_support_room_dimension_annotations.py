"""Native room-label/dimension annotation provenance; strictly candidate only.

Checks producer-native block/line adjacency for figured dimension candidates
that are ALREADY vector witness bound, without trusting raw PDF text,
inventing physical room ownership, reusing cross-view coordinates or
publishing a metric area. A strict native relation is NOT a source receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections import Counter
from typing import Any
import fitz

from pb_figured_dimension_evidence import extract_dimension_evidence_bundle

SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
TARGETS=("FREEZER","PWD","AIRLOCK","LAUNDRY","SALES")
PAGES=(11,14)

def _native_annotation_relation(label:dict[str,Any],dimension:dict[str,Any]) -> str|None:
    """Require source-native block/line identity, NEVER nearest-neighbour."""
    if dimension["word_no"]!=0:
        return None
    if (dimension["block_no"]==label["block_no"] and
            dimension["line_no"]==label["line_no"]+1):
        return "consecutive_same_native_block"
    if (dimension["block_no"]!=label["block_no"]+1 or
            dimension["line_no"]!=0 or label["line_no"]!=0):
        return None
    lx0,ly0,lx1,ly1=label["bbox"]
    dx0,dy0,dx1,dy1=dimension["bbox"]
    if dimension["orientation"]=="horizontal" and min(lx1,dx1)>max(lx0,dx0):
        return "adjacent_native_blocks_with_axis_overlap"
    if dimension["orientation"]=="vertical" and min(ly1,dy1)>max(ly0,dy0):
        return "adjacent_native_blocks_with_axis_overlap"
    return None


def scan_page(page,page_number:int)->dict[str,Any]:
    source_words=tuple(page.get_text("words") or ())
    grouped={}
    for word in source_words:
        if len(word)<8:
            continue
        try:
            block,line,index=(int(word[i]) for i in (5,6,7))
        except (TypeError,ValueError):
            continue
        grouped.setdefault((block,line),[]).append(word)
    native_labels={name:[] for name in TARGETS}
    for (block,line),words in grouped.items():
        ordered=sorted(words,key=lambda w:int(w[7]))
        full_text=" ".join(str(w[4]).strip() for w in ordered)
        key=" ".join(full_text.upper().split())
        if key not in native_labels:
            continue
        bbox=(
            min(float(w[0]) for w in ordered),
            min(float(w[1]) for w in ordered),
            max(float(w[2]) for w in ordered),
            max(float(w[3]) for w in ordered),
        )
        native_labels[key].append({"block_no":block,"line_no":line,
                                   "bbox":bbox,"source_text":full_text})
    bundle=extract_dimension_evidence_bundle(page,page_num=page_number)
    observed={o.dimension_id:o for o in bundle.observations}
    bindings={b.observation_id:b for b in bundle.bindings}
    bound=[]
    prefix=f"native_dim_p{page_number}_"
    for observation_id,b in bindings.items():
        if str(b.status)!="witness_bound" or b.endpoints is None:
            continue
        obs=observed.get(observation_id)
        if obs is None or not observation_id.startswith(prefix) or obs.bbox is None:
            continue
        try:
            index=int(observation_id[len(prefix):])
            word=source_words[index]
            native_bbox=tuple(float(v) for v in word[:4])
            obs_bbox=tuple(float(v) for v in obs.bbox)
        except (ValueError,IndexError,TypeError):
            continue
        if len(word)<8 or any(abs(x-y)>1e-4 for x,y in zip(native_bbox,obs_bbox)):
            continue
        if str(word[4]).strip()!=str(obs.raw_text).strip():
            continue
        bound.append({
            "block_no":int(word[5]),"line_no":int(word[6]),"word_no":int(word[7]),
            "bbox":native_bbox,"orientation":str(obs.orientation),
            "dimension_observation_id":observation_id,
            "source_dim_text":obs.raw_text,
            "source_dim_unit":obs.unit,
            "source_value":obs.value,
            "witness_line_ids":list(b.witness_line_ids),
            "dimension_line_id":b.dimension_line_id,
        })
    targets={}
    for name in TARGETS:
        relations=[]
        for line in native_labels[name]:
            for dim in bound:
                relation=_native_annotation_relation(line,dim)
                if relation is None:
                    continue
                relations.append({
                    "source_label_block_no":line["block_no"],
                    "source_label_line_no":line["line_no"],
                    "native_relation":relation,
                    "dimension_observation_id":dim["dimension_observation_id"],
                    "source_figured_dimension_text":dim["source_dim_text"],
                    "source_figured_dimension_value":dim["source_value"],
                    "source_dimension_unit":dim["source_dim_unit"],
                    "orientation":dim["orientation"],
                    "witness_line_ids":dim["witness_line_ids"],
                    "dimension_line_id":dim["dimension_line_id"],
                    "source_text_trusted":False,
                    "physical_room_owner_proven":False,
                })
        orientations={r["orientation"] for r in relations}
        targets[name]={
            "native_exact_whole_line_label_count":len(native_labels[name]),
            "raw_native_witness_bound_annotation_candidate_count":len(relations),
            "orientation_counts":dict(Counter(r["orientation"] for r in relations)),
            "both_axes_candidate_only":("horizontal" in orientations and "vertical" in orientations),
            "source_raw_annotation_candidates":relations,
            "first_gate":"source_text_and_orthogonal_wall_owner_unproven" if relations else "native_line_annotation_relation_unavailable",
            "metric_area_authorized":False,
        }
    return {"source_page":page_number,
            "native_figured_dimension_observation_count":len(bundle.observations),
            "native_vector_witness_bound_count":sum(str(b.status)=="witness_bound" for b in bundle.bindings),
            "native_bbox_exact_bound_count":len(bound),
            "room_targets":targets,
            "customer_quantity_count":0}


def audit(source_bytes:bytes)->dict[str,Any]:
    digest=hashlib.sha256(source_bytes).hexdigest()
    if digest!=SHA:
        raise ValueError("source_sha_mismatch")
    doc=fitz.open(stream=source_bytes,filetype="pdf")
    try:
        if doc.page_count!=31:
            raise ValueError("source_page_count_mismatch")
        results=[scan_page(doc.load_page(p-1),p) for p in PAGES]
    finally:
        doc.close()
    return {"source_sha256":digest,"scoped_pages":PAGES,
            "pages":results,"source_text_authentication_status":"NOT_CHECKED_CANDIDATES_ONLY",
            "room_area_quantity_claim_count":0}

if __name__=="__main__":
    raw=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf").read_bytes()
    print("GPT2_SUPPORT_DIMENSION_NATIVE_ANNOTATION_FIRST_GATE",
          json.dumps(audit(raw),sort_keys=True,default=str))
