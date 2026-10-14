"""Review W3-closed original G17 jambs with strict source ancestry, not host grants.

Only two *independently* source-authenticated face/end flanks that retain all
three original W2 edges and their W3 inner L corners can form a source
ribbon. Outer NEAR_JUNCTION_REVIEW remains an explicit unresolved wall role.
No W4/host/measurement/canonical publication is possible from this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from tools.diag_gptmax_g17_source_only_flanks import source_only_closed_flanks

_EPS=1e-6


def _edge(value: object) -> tuple[tuple[float,float],tuple[float,float]]:
    if not isinstance(value,(list,tuple)) or len(value)!=4 or any(
        type(v) not in (float,int) or not math.isfinite(v) for v in value
    ):
        raise ValueError("unverifiable original source line")
    a,b=(float(value[0]),float(value[1])),(float(value[2]),float(value[3]))
    if a==b:
        raise ValueError("source edge has zero length")
    return tuple(sorted((a,b)))


def _flank_proof(
    receipt: Mapping[str,Any], flank: Mapping[str,Any], w2: Mapping[str,Any],
) -> dict[str,Any]:
    ids=flank.get("source_observation_ids")
    if not isinstance(ids,list) or len(ids)!=3 or len(set(ids))!=3:
        raise ValueError("original face/end receipt incomplete")
    raw=receipt.get("source_g17_observations")
    if not isinstance(raw,list) or len({r.get("observation_id") for r in raw})!=len(raw):
        raise ValueError("ambiguous original source observation universe")
    named={r["observation_id"]:r for r in raw}
    if not set(ids)<=set(named):
        raise ValueError("foreign G17 observation in W3 scope")
    parents=[]
    source_edges=[]
    kind_count=Counter()
    for oid in ids:
        r=named[oid]
        kind_count[r.get("observation_kind")]+=1
        ap=r.get("authenticated_source_parents")
        if (not isinstance(ap,list) or len(ap)!=1 or
                not isinstance(ap[0],Mapping) or
                not isinstance(ap[0].get("observation_id"),str)):
            raise ValueError("original G17 source primitive parent not unique")
        parents.append(ap[0]["observation_id"])
        source_edges.append(_edge(r.get("geometry_pdf_pts")))
    if kind_count!={"raster_wall_band_face":2,"raster_wall_band_end":1}:
        raise ValueError("not exactly two original faces plus inner cap")
    if len(set(parents))!=3:
        raise ValueError("original parent source reused across distinct edges")
    if (sorted(ids)!=sorted(w2.get("source_observation_ids",()))
        or sorted(parents)!=sorted(w2.get("source_parent_observation_ids",()))):
        raise ValueError("W2 source parent/observation address changed")
    default=w2.get("default_w2_w3_w4")
    exact=w2.get("exact_coordinate_w2_w3_w4")
    if not isinstance(default,Mapping) or not isinstance(exact,Mapping):
        return {"retained":False,"first_failure":"source_positive_w2_graph_unavailable",
                "original_source_ids":sorted(ids),"original_parent_ids":sorted(parents)}
    graphs=(default,exact)
    for graph in graphs:
        if (graph.get("structural_wall_role_granted") is not False
            or graph.get("canonical_w4_wall_id_granted") is not False
            or graph.get("host_binding_granted") is not False):
            raise ValueError("shadow graph attempted W4/host grant")
        if (sorted(graph.get("source_observation_ids",()))!=sorted(ids)
            or sorted(graph.get("source_parent_observation_ids",()))!=sorted(parents)):
            raise ValueError("shadow W2 original source parent lost")
    # Geometry retains actual original lines, not just matching edge counts
    geometries=[]
    for graph in graphs:
        try:
            geometries.append(sorted(_edge(v) for v in graph["w2_surviving_edge_geometry_pt"]))
        except (KeyError,TypeError):
            raise ValueError("original W2 surviving geometry unavailable") from None
    originals=sorted(source_edges)
    complete=all(
        graph.get("w2_surviving_edges")==3
        and graph.get("w2_snap_collapsed_fragments")==0
        and graph.get("w2_excluded_source_segments")==0
        and Counter(graph.get("w3_junction_types",())).get("l_corner",0)==2
        and len(graph.get("w4_shadow_candidate_source_edges",()))==3
        and sorted(graph.get("w4_shadow_candidate_source_edges",()))==
            sorted(graph.get("w2_surviving_source_fragment_ids",()))
        for graph in graphs
    ) and all(g==originals for g in geometries)
    return {
        "retained":complete,
        "first_failure":None if complete else "original_w2_w3_source_jamb_not_retained",
        "original_source_ids":sorted(ids),
        "original_parent_ids":sorted(parents),
        "physical_structural_wall_role_proven":False,
        "original_w3_outer_near_miss_unwaived":True,
        "canonical_w4_owner_proven":False,
    }


def source_owned_g17_jamb_pair_review(
    original_pdf:bytes, source_report:Mapping[str,Any],
    w2_report:Mapping[str,Any], *, page_id:str,
)->dict[str,Any]:
    if type(original_pdf) is not bytes or not original_pdf:
        raise ValueError("source original PDF bytes required")
    sha=hashlib.sha256(original_pdf).hexdigest()
    if (source_report.get("source_sha256")!=sha
        or w2_report.get("source_sha256")!=sha
        or w2_report.get("page_id")!=page_id
        or source_report.get("primitive_safety_cap")!=20000
        or w2_report.get("global_w4_or_snapshot_modified") is not False
        or w2_report.get("physical_wall_or_opening_host_granted") is not False):
        raise ValueError("source SHA/snapshot/cap or upstream authority contradicted")
    original=source_report.get("unhosted_raster_flank_source_receipts")
    graph=w2_report.get("source_flank_w2_w4_shadows")
    if not isinstance(original,list) or not isinstance(graph,list) or not original:
        raise ValueError("source G17 original W2 receipt missing")
    ids=[r.get("physical_opening_id") for r in original]
    gids=[r.get("physical_opening_id") for r in graph]
    if len(set(ids))!=len(ids) or len(set(gids))!=len(gids) or set(ids)!=set(gids):
        raise ValueError("source G17 physical universe incomplete/duplicated")
    by_graph={r["physical_opening_id"]:r for r in graph}
    results=[]
    for record in sorted(original,key=lambda r:r["physical_opening_id"]):
        if (record.get("source_sha256")!=sha
                or record.get("snapshot_id")!=source_report.get("snapshot_id")
                or record.get("page_id")!=page_id):
            raise ValueError("G17 observation source/revision page mismatched")
        source_flanks=source_only_closed_flanks(record)
        if not source_flanks["closed_source_flank_nomination"]:
            raise ValueError("original G17 face/end topology unclosed")
        probes=by_graph[record["physical_opening_id"]].get("flanks")
        if not isinstance(probes,list) or len(probes)!=2:
            raise ValueError("incomplete W2 source-flank scope")
        lookup={tuple(sorted(x.get("source_observation_ids",()))):x for x in probes}
        if len(lookup)!=2:
            raise ValueError("ambiguous W2 source side ownership")
        statuses=[]
        for source_flank in source_flanks["source_flank_boxes"]:
            key=tuple(sorted(source_flank["source_observation_ids"]))
            w=lookup.get(key)
            if w is None:
                raise ValueError("source G17→W2 flank parent mapping missing")
            if w.get("source_ink_shadow_eligible") is not True:
                statuses.append({"side":source_flank["side_in_original_source_order"],
                                 "retained":False,
                                 "first_failure":w.get("source_ink_first_failure") or "source_ink_unavailable"})
                continue
            proof=_flank_proof(record,source_flank,w)
            proof["side"]=source_flank["side_in_original_source_order"]
            statuses.append(proof)
        both=all(x["retained"] is True for x in statuses)
        results.append({
            "physical_opening_id":record["physical_opening_id"],
            "both_original_flanks_w2_w3_source_closed":both,
            "flank_source_proofs":statuses,
            "canonical_w4_physical_equivalence_granted":False,
            "opening_host_granted":False,
            "opening_height_or_area_granted":False,
        })
    return {
        "source_sha256":sha,"page_id":page_id,
        "original_g17_physical_opening_count":len(results),
        "source_closed_two_flank_candidates":sum(x["both_original_flanks_w2_w3_source_closed"] for x in results),
        "opening_source_ribbon_review":results,
        "published_source_snapshot_modified":False,
        "physical_w4_or_host_granted":False,
        "opening_area_or_count_granted":False,
        "customer_row_granted":False,
        "benchmark_score_granted":False,
    }


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--source-report",type=Path,required=True)
    p.add_argument("--w2-shadow-report",type=Path,required=True)
    p.add_argument("--page-id",default="3")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=source_owned_g17_jamb_pair_review(
        args.pdf.read_bytes(),json.loads(args.source_report.read_text()),
        json.loads(args.w2_shadow_report.read_text()),page_id=args.page_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"source_closed_two_flanks":report["source_closed_two_flank_candidates"],
                      "new_physical_hosts":0,"new_metric_areas":0},sort_keys=True))


if __name__=="__main__":
    main()
