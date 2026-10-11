"""Original foreground/W2/W3/W4 common wall candidates on both G17 opening flanks.

Purely diagnostic. W4 generated from source-positive pixels in full-page
shadow scope has NO certified physical wall or host authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS


def _unique(rows, key, label, cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS):
    if not isinstance(rows, list) or len(rows)>cap:
        raise ValueError("invalid or unbounded "+label)
    result={}
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid "+label+" row")
        value=row.get(key)
        if not isinstance(value,str) or not value.strip() or value in result:
            raise ValueError("missing or duplicate "+label+" ID")
        result[value]=row
    return result


def _finite_xy(pt):
    if (not isinstance(pt,(tuple,list)) or len(pt)!=2
            or any(type(x) not in (float,int) or not math.isfinite(x) for x in pt)):
        raise ValueError("invalid source W4 point")
    return tuple(map(float,pt))


def original_common_w4_candidates(source_bytes, original_report, flank_report, graph_report,
                                   *, expected_source_sha):
    if type(source_bytes) is not bytes or hashlib.sha256(source_bytes).hexdigest()!=expected_source_sha:
        raise ValueError("original source PDF SHA invalid")
    if not all(isinstance(x,dict) for x in (original_report,flank_report,graph_report)):
        raise ValueError("unavailable complete original source reports")
    for name, report in (("G17",original_report),("flank",flank_report),
                         ("foreground",graph_report)):
        if report.get("source_sha256")!=expected_source_sha or report.get("host_publication_allowed") is not False:
            raise ValueError(name+" source or publication mismatch")
        if report.get("benchmark_accuracy") is not None:
            raise ValueError(name+" benchmark result in source-only diagnostic")
    if len({r.get("page_id") for r in (original_report,flank_report,graph_report)})!=1:
        raise ValueError("different source page scope")
    if (flank_report.get("source_pdf_byte_sha_verified") is not True
            or flank_report.get("source_receipts_freshly_reauthenticated") is not False
            or flank_report.get("physical_equivalence_proven") is not False
            or graph_report.get("ordinary_source_snapshot_unchanged") is not True
            or graph_report.get("original_source_render_reauthenticated") is not True
            or graph_report.get("ordinary_visibility_rejects_shadow_kind") is not True
            or graph_report.get("physical_equivalence_proven") is not False
            or graph_report.get("opening_count_publication_allowed") is not False
            or graph_report.get("metric_quantity_publication_allowed") is not False
            or graph_report.get("experimental_w2_w4") is None):
        raise ValueError("source W2 shadow physical authority incorrectly promoted")
    graph=graph_report["experimental_w2_w4"]
    if graph.get("host_publication_allowed") is not False or graph.get("physical_equivalence_proven") is not False:
        raise ValueError("experimental graph claims physical wall equivalence")
    expected=graph.get("input_source_count")
    if type(expected) is not int or expected<0 or expected>MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("original source primitive cap overflow")
    source_rows=_unique(graph.get("source_parent_census"),"source_observation_id","W2 source")
    if len(source_rows)!=expected:
        raise ValueError("truncated original W2 input source parent inventory")
    # W2 may yield many derived edges. The 20k safety cap applies only to
    # incoming source primitives, not subdivided W2 graph edges.
    edges=_unique(graph.get("all_w2_edges"),"edge_id","W2 derived",cap=16*MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS)
    walls=_unique(graph.get("all_experimental_w4_candidates"),"candidate_id","W4 derived",cap=16*MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS)
    for eid,edge in edges.items():
        parents=edge.get("source_observation_ids")
        if (not isinstance(parents,list) or not parents
                or len(set(parents))!=len(parents)
                or any(pid not in source_rows for pid in parents)):
            raise ValueError("unowned surviving or removed original W2")
        owners=edge.get("experimental_w4_candidate_ids")
        if (not isinstance(owners,list) or len(set(owners))!=len(owners)
                or any(w not in walls for w in owners)
                or (edge.get("w3_removed") is True and owners)):
            raise ValueError("unverifiable W2→W3→W4 source ownership")
    for wall_id,wall in walls.items():
        parents=wall.get("w2_edge_ids")
        if (not isinstance(parents,list) or len(parents)!=len(set(parents))
                or any(eid not in edges
                       or wall_id not in edges[eid]["experimental_w4_candidate_ids"]
                       for eid in parents)):
            raise ValueError("unverifiable W4→W2 physical graph parents")
        points=wall.get("centerline_pt")
        if (not isinstance(points,list) or len(points)<2 or len(points)>MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS):
            raise ValueError("invalid original W4 centerline")
        for pt in points: _finite_xy(pt)
    original=_unique(original_report.get("opening_rows"),"opening_identity_id","G17 original")
    flanks=_unique(flank_report.get("opening_rows"),"opening_identity_id","source flanks")
    if set(flanks)!=set(original) or len(original)!=7:
        raise ValueError("unproven G17/flank source case census")
    output=[]
    for oid,row in sorted(flanks.items()):
        parts=row.get("flanks")
        if not isinstance(parts,list) or len(parts)!=2 or {x.get("role") for x in parts}!={"left","right"}:
            raise ValueError("incomplete original G17 flank pair")
        two={}
        for part in parts:
            seen=set()
            w2=set()
            w4=set()
            for source in part.get("pixel_run_candidates",[]):
                sid=source.get("source_observation_id")
                if (not isinstance(sid,str) or sid in seen or sid not in source_rows
                        or any(source.get(flag) is not False for flag in (
                            "host_publication_allowed","visible_wall_authority_proven",
                            "physical_wall_equivalence_proven"))):
                    raise ValueError("invalid original positive ink receipt")
                seen.add(sid)
                census=source_rows[sid]
                for eid in census.get("w2_edge_ids",[]):
                    edge=edges.get(eid)
                    if edge is None or sid not in edge["source_observation_ids"]:
                        raise ValueError("original source parent W2 membership mismatch")
                    w2.add(eid)
                    if edge.get("w3_retained") is True:
                        w4.update(edge["experimental_w4_candidate_ids"])
            two[part["role"]]={"source_run_count":len(seen),"w2_source_edge_count":len(w2),
                                 "experimental_w4_candidate_ids":sorted(w4)}
        common=sorted(set(two["left"]["experimental_w4_candidate_ids"])
                      &set(two["right"]["experimental_w4_candidate_ids"]))
        basis=original[oid].get("original_aperture_coordinate_basis")
        if not isinstance(basis,dict):
            raise ValueError("original G17 aperture coordinate basis missing")
        origin,axis,normal=(_finite_xy(basis.get(k)) for k in ("origin","axis","normal"))
        length=basis.get("length")
        if type(length) not in (int,float) or not math.isfinite(length) or length<=0:
            raise ValueError("invalid original aperture geometry")
        centerline=[]
        for wall_id in common:
            points=[_finite_xy(pt) for pt in walls[wall_id]["centerline_pt"]]
            projected=[(pt[0]-origin[0])*axis[0]+(pt[1]-origin[1])*axis[1] for pt in points]
            normal_offsets=[(pt[0]-origin[0])*normal[0]+(pt[1]-origin[1])*normal[1] for pt in points]
            centerline.append({
                "candidate_id":wall_id,
                "original_w4_centerline_pt":[list(pt) for pt in points],
                "w4_centerline_axis_spans_aperture":min(projected)<=0 and max(projected)>=length,
                "minimum_source_centerline_normal_offset_pt":min(map(abs,normal_offsets)),
                "physical_w4_wall_role_proven":False,
                "source_viewport_authenticity_proven":False,
                "opening_host_publication_allowed":False})
        output.append({
            "opening_identity_id":oid,"flanks":two,
            "shared_experimental_w4_candidates":centerline,
            "first_unproved_authority":"SOURCE_VISIBLE_PHYSICAL_WALL_EQUIVALENCE",
            "host_publication_allowed":False})
    return {"source_sha256":expected_source_sha,"page_id":flank_report["page_id"],
        "input_source_count":expected,"opening_rows":output,
        "original_source_bytes_verified":True,
        "original_source_visible_structural_wall_role_proven":False,
        "source_universe_completeness_proven":False,
        "physical_equivalence_proven":False,"host_publication_allowed":False,
        "opening_count_publication_allowed":False,"metric_quantity_publication_allowed":False,
        "benchmark_accuracy":None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--original-g17-report",type=Path,required=True)
    parser.add_argument("--source-flank-report",type=Path,required=True)
    parser.add_argument("--full-w2-w4-report",type=Path,required=True)
    parser.add_argument("--expected-source-sha",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=original_common_w4_candidates(args.pdf.read_bytes(),
        json.loads(args.original_g17_report.read_text()),
        json.loads(args.source_flank_report.read_text()),
        json.loads(args.full_w2_w4_report.read_text()),
        expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"input_source_count":result["input_source_count"],
        "shared_w4":[len(row["shared_experimental_w4_candidates"])
                     for row in result["opening_rows"]],
        "host_publication_allowed":False}))


if __name__=="__main__":
    main()
