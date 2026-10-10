"""Read-only exact source-host candidate parity ledger across snapshot changes.

Compares original production source reports with the *same* source PDF SHA,
physical page scope, and primitive cap. A candidate's **positive W4 hybrid
path/primitive ancestry** and full native source-edge geometry are compared,
not its unstable split-edge sequence numbers, global SourceVisibility snapshot
ID, display labels, proximity, or number of hosts.

This never marks host/frame receipt rekeys as accepted, publishes any opening,
or establishes physical wall equivalence. Changed W4 members, source geometry,
frame geometry, source status, or lost receipts remain explicit REVIEW.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def _unique(rows, label, key):
    if not isinstance(rows, list):
        raise ValueError(f"{label}: source array missing")
    out={}
    for r in rows:
        if not isinstance(r,dict):
            raise ValueError(f"{label}: invalid source record")
        k=r.get(key)
        if not isinstance(k,str) or not k or k in out:
            raise ValueError(f"{label}: invalid or repeated source owner")
        out[k]=r
    return out


def _source_views(report):
    if not isinstance(report,dict):
        raise ValueError("source report missing")
    sha=report.get("source_sha256")
    pages=report.get("selected_geometry_page_ids")
    if (not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha)
            or not isinstance(pages,list) or not pages
            or len(set(map(str,pages)))!=len(pages)
            or any(not str(p).isdigit() for p in pages)
            or report.get("primitive_safety_cap") != 20_000):
        raise ValueError("missing original source SHA/pages or changed cap")
    physical=_unique(report.get("opening_bindings"),"physical openings","opening_identity_id")
    frames=_unique(report.get("host_frames"),"source frames","opening_identity_id")
    if set(frames)!=set(physical):
        raise ValueError("physical opening/frame source scope differs")
    source_scopes=report.get("source_owned_wall_scope_results")
    if not isinstance(source_scopes,list) or not source_scopes:
        raise ValueError("missing W4 producer-owned source evidence")
    walls={}
    for scope in source_scopes:
        if (not isinstance(scope,dict) or scope.get("source_sha256")!=sha
                or str(scope.get("page_id")) not in set(map(str,pages))
                or scope.get("status")!="corroborated"
                or scope.get("scope_complete") is not True):
            raise ValueError("non-authenticated W4 source page scope")
        for k,r in _unique(scope.get("records"),"W4 candidates","wall_candidate_id").items():
            if k in walls:
                raise ValueError("duplicate W4 physical candidate owner across pages")
            walls[k]=r
    evidence=_unique(
        report.get("resolved_host_frame_evidence"),
        "source whole-wall frames","opening_identity_id",
    )
    for oid in evidence:
        if oid not in physical or not frames[oid].get("record_id"):
            raise ValueError("source whole-wall geometry without authenticated frame receipt")
    # The three independently serialized authority views must agree for each
    # positively framed opening. Unframed openings may legitimately have a
    # corroborated host and an ABSTAIN frame with no host_wall_id.
    for oid, frame in frames.items():
        if not frame.get("record_id"):
            continue
        host=physical[oid]
        receipt=evidence.get(oid)
        if not host.get("host_wall_id") or not host.get("record_id") or receipt is None:
            raise ValueError("authenticated frame lacks source-owned host or geometry")
        if (frame.get("host_wall_id") != host["host_wall_id"]
                or receipt.get("host_wall_id") != host["host_wall_id"]
                or receipt.get("host_binding_record_id") != host["record_id"]
                or receipt.get("record_id") != frame["record_id"]):
            raise ValueError("inconsistent physical opening host/frame receipt lineage")
        members=frame.get("whole_wall_candidate_ids")
        if members is not None and (
                not isinstance(members,list)
                or members != receipt.get("whole_wall_candidate_ids")
                or members != host.get("member_wall_candidate_ids")):
            raise ValueError("inconsistent framed whole-wall candidate membership")
        selector=receipt.get("selector")
        if not isinstance(selector,dict):
            raise ValueError("framed receipt missing producer source selector")
        expected={
            "opening_identity_id":oid,
            "page_id":str(host.get("page_id")),
            "source_sha256":sha,
            "snapshot_id":report.get("snapshot_id"),
        }
        for key,value in expected.items():
            if key in selector and value is not None and str(selector[key]) != str(value):
                raise ValueError("framed source selector disagrees with opening source owner")
    return sha,tuple(map(str,pages)),physical,frames,walls,evidence


def _positive_candidate_signature(r):
    """Ignore ONLY generated split-edge/node addresses, not source geometry."""
    if not isinstance(r,dict):
        return None
    identity=r.get("physical_identity")
    wall=r.get("wall_candidate")
    fragments=r.get("source_edge_fragments")
    if (not isinstance(identity,dict) or not isinstance(wall,dict)
            or not isinstance(fragments,list) or not fragments
            or identity.get("status")!="corroborated"
            or identity.get("blocking_reasons")
            or not str(identity.get("candidate_identity_id") or "").startswith("wall2_")):
        return None
    primitive_ids=identity.get("source_primitive_ids")
    path=identity.get("path_fingerprint")
    if (not isinstance(primitive_ids,list) or not primitive_ids
            or any(not isinstance(v,str) or not v for v in primitive_ids)
            or not isinstance(path,list) or len(path)<2):
        return None
    try:
        # JSON-safe immutable equality. This includes actual original page
        # coordinates and complete positive source ancestry, but no split-N
        # address or changing junction ID.
        edges=sorted((
            json.dumps({
                "geometry":f["geometry"],
                "source_primitive_ids":f["source_primitive_ids"],
            },sort_keys=True,separators=(",",":"))
            for f in fragments
        ))
        core={
            "v2_id":identity["candidate_identity_id"],
            "path":path,
            "primitive_ids":primitive_ids,
            "physical_status":identity["status"],
            "wall_centerline":wall["centerline_pts"],
            "wall_representation":wall["representation"],
            "wall_status":wall["status"],
            "wall_reasons":wall["reason_codes"],
            "source_edges":edges,
        }
        return json.dumps(core,sort_keys=True,separators=(",",":"))
    except (KeyError,TypeError,ValueError):
        return None


def _frame_geometry_signature(frame):
    if not isinstance(frame,dict):
        return None
    # These identifiers are tied to producer snapshot/host record; their
    # removal here does NOT authorize or manufacture replacement receipts.
    ephemeral={
        "selector","record_id","whole_wall_frame_id",
        "host_wall_id","host_binding_record_id",
    }
    core={k:v for k,v in frame.items() if k not in ephemeral}
    return json.dumps(core,sort_keys=True,separators=(",",":"))


def compare_source_host_rekeys(baseline,candidate):
    asha,ap,ab,af,aw,ae=_source_views(baseline)
    bsha,bp,bb,bf,bw,be=_source_views(candidate)
    if asha!=bsha or ap!=bp:
        raise ValueError("source file or page scope does not match")
    if not set(ab).issubset(bb):
        raise ValueError("original physical opening identity disappeared")
    counts=Counter()
    rows=[]
    for oid in sorted(ab):
        old,new=ab[oid],bb[oid]
        if not old.get("host_wall_id"):
            continue
        why=[]
        if not new.get("host_wall_id") or not new.get("record_id"):
            why.append("ORIGINAL_HOST_PROOF_LOST")
        elif old.get("page_id")!=new.get("page_id"):
            why.append("HOST_PAGE_OWNERSHIP_CHANGED")
        else:
            before=old.get("member_wall_candidate_ids")
            after=new.get("member_wall_candidate_ids")
            if not isinstance(before,list) or not before:
                raise ValueError("original hosted opening missing W4 membership")
            if before!=after:
                why.append("W4_MEMBER_CANDIDATE_IDENTITY_CHANGED")
            else:
                for w in before:
                    signature_a=_positive_candidate_signature(aw.get(w))
                    signature_b=_positive_candidate_signature(bw.get(w))
                    if signature_a is None or signature_b is None:
                        why.append("W4_POSITIVE_SOURCE_PROOF_UNAVAILABLE")
                        break
                    if signature_a!=signature_b:
                        why.append("W4_SOURCE_PATH_OR_ANCESTRY_CHANGED")
                        break
        oldframe,newframe=af[oid],bf[oid]
        if oldframe.get("record_id"):
            if not newframe.get("record_id"):
                why.append("ORIGINAL_FRAME_PROOF_LOST")
            else:
                old_geom=ae.get(oid)
                new_geom=be.get(oid)
                if old_geom is None or new_geom is None:
                    why.append("FRAME_SOURCE_GEOMETRY_UNAVAILABLE")
                elif _frame_geometry_signature(old_geom)!=_frame_geometry_signature(new_geom):
                    why.append("FRAME_SOURCE_GEOMETRY_CHANGED")
        elif newframe.get("record_id"):
            why.append("NEW_FRAME_REQUIRES_SEPARATE_PROOF")
        if old.get("reason_codes")!=new.get("reason_codes"):
            why.append("HOST_AUTHORITY_REASON_CHANGED")
        if oldframe.get("reason_codes")!=newframe.get("reason_codes"):
            why.append("FRAME_AUTHORITY_REASON_CHANGED")
        if why:
            state="ORIGINAL_SOURCE_PROOF_CHANGED_OR_LOST"
        elif (old.get("host_wall_id")==new.get("host_wall_id")
              and old.get("record_id")==new.get("record_id")
              and oldframe.get("record_id")==newframe.get("record_id")):
            state="EXACT_PRIOR_RECEIPTS_RETAINED"
        else:
            state="UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY"
            why=["PRIOR_RECEIPT_IDENTITY_REKEY_UNAPPROVED"]
        counts[state]+=1
        rows.append({
            "physical_opening_id":oid,
            "source_comparison_status":state,
            "reason_codes":sorted(set(why)),
            "old_host_wall_id":old.get("host_wall_id"),
            "candidate_host_wall_id":new.get("host_wall_id"),
            "old_host_receipt":old.get("record_id"),
            "candidate_host_receipt":new.get("record_id"),
            "old_source_frame_receipt":oldframe.get("record_id"),
            "candidate_source_frame_receipt":newframe.get("record_id"),
            "commercial_publication_permission":"NOT_ESTABLISHED",
        })
    return {
        "source_sha256":asha,
        "source_pages":list(ap),
        "prior_authenticated_host_count":sum(bool(r.get("host_wall_id")) for r in ab.values()),
        "candidate_authenticated_host_count":sum(bool(r.get("host_wall_id")) for r in bb.values()),
        "rekey_classification_counts":dict(sorted(counts.items())),
        "source_comparison_rows":rows,
        # This report NEVER becomes a replacement for the strict source
        # opening host/frame identity retention gate.
        "official_host_receipt_identity_acceptance":False,
        "opening_count_or_metric_publication_allowed":False,
        "benchmark_accuracy":None,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=compare_source_host_rekeys(
        json.loads(a.baseline.read_text()),
        json.loads(a.candidate.read_text()),
    )
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result["rekey_classification_counts"],sort_keys=True))


if __name__=="__main__":
    main()
