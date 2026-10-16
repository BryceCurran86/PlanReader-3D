"""Prove shared original G17 faces and independent two-ended source closure.

Exact original source IDs and TWO original end caps may nominate a physical
short pier. They NEVER establish W4 structural role, host equivalence, opening
count or width/height. All competing ends and opening owners stay in output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import itertools
import json
import math
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention

STATUS="original_g17_two_opening_shared_faces_dual_end_source_only"
TOL=1e-6


def _geometry(obs):
    p=obs.get("geometry_pdf_pts")
    if not isinstance(p,(list,tuple)) or len(p)!=4 or any(
        type(x) not in (int,float) or not math.isfinite(x) for x in p):
        raise ValueError("invalid exact original source geometry")
    return tuple(float(x) for x in p)


def _axis_face(obs):
    p=_geometry(obs)
    if obs["kind"]!="raster_wall_band_face":
        return None
    if abs(p[1]-p[3])<=TOL and abs(p[2]-p[0])>TOL:
        return ("horizontal",min(p[0],p[2]),max(p[0],p[2]),p[1])
    if abs(p[0]-p[2])<=TOL and abs(p[3]-p[1])>TOL:
        return ("vertical",min(p[1],p[3]),max(p[1],p[3]),p[0])
    return None


def _matching_end(obs,*,axis,endpoint,offsets):
    if obs["kind"]!="raster_wall_band_end":
        return False
    x,y,u,v=_geometry(obs)
    a,b=sorted(offsets)
    if axis=="horizontal":
        return abs(x-u)<=TOL and abs(x-endpoint)<=TOL and abs(min(y,v)-a)<=TOL and abs(max(y,v)-b)<=TOL
    return abs(y-v)<=TOL and abs(y-endpoint)<=TOL and abs(min(x,u)-a)<=TOL and abs(max(x,u)-b)<=TOL


def audit_shared_original_g17_dual_end_piers(openings):
    """Audit every physical pair, preserving all competing face/end IDs.

    Input must come from ONE current original producer; this pure function
    does not and cannot authenticate serialized input or publish a wall.
    """
    if not isinstance(openings,dict) or len(openings)!=len(set(openings)):
        raise ValueError("invalid original physical opening inventory")
    owners=defaultdict(set)
    for physical_id, observations in openings.items():
        for oid, observation in observations.items():
            if observation.get("kind")=="raster_wall_band_face":
                owners[oid].add(physical_id)
    rows=[]
    for a,b in itertools.combinations(sorted(openings),2):
        oa,ob=openings[a],openings[b]
        if not isinstance(oa,dict) or not isinstance(ob,dict):
            raise ValueError("invalid original G17 observation scopes")
        for inventory in (oa,ob):
            if any(not isinstance(k,str) or not k or not isinstance(v,dict)
                   or v.get("id")!=k or not isinstance(v.get("parents"),(tuple,list))
                   or not v["parents"] or len(set(v["parents"]))!=len(v["parents"])
                   for k,v in inventory.items()):
                raise ValueError("invalid original source parent address")
        common=sorted(set(oa)&set(ob))
        if not common:
            continue
        shared_faces=[cid for cid in common
                      if oa[cid]["kind"]=="raster_wall_band_face"
                      and ob[cid]["kind"]=="raster_wall_band_face"]
        if len(shared_faces)!=2:
            rows.append({
                "opening_ids":[a,b],"shared_original_g17_observation_ids":common,
                "shared_face_ids":shared_faces,"reason":"shared_two_face_identity_incomplete",
                "source_closed_pier_candidate":False,"wall_host_granted":False})
            continue
        faces=[_axis_face(oa[cid]) for cid in shared_faces]
        matching=(
            all(f is not None for f in faces)
            and faces[0][0]==faces[1][0]
            and abs(faces[0][1]-faces[1][1])<=TOL
            and abs(faces[0][2]-faces[1][2])<=TOL
            and abs(faces[0][3]-faces[1][3])>TOL
            and all(_geometry(oa[cid])==_geometry(ob[cid]) for cid in shared_faces)
            and all(tuple(oa[cid]["parents"])==tuple(ob[cid]["parents"]) for cid in shared_faces)
        )
        if not matching or any(owners[cid]!={a,b} for cid in shared_faces):
            reason=("shared_source_faces_geometry_or_parent_conflict" if not matching
                    else "competing_original_shared_face_owner")
            rows.append({
                "opening_ids":[a,b],"shared_original_g17_observation_ids":common,
                "shared_face_ids":shared_faces,"reason":reason,
                "source_closed_pier_candidate":False,"wall_host_granted":False})
            continue
        axis,lo,hi=faces[0][:3]
        offsets=[faces[0][3],faces[1][3]]
        ends={}
        for opening_id,inventory in ((a,oa),(b,ob)):
            ends[opening_id]={
                "start":sorted(k for k,v in inventory.items() if k not in common
                               and _matching_end(v,axis=axis,endpoint=lo,offsets=offsets)),
                "finish":sorted(k for k,v in inventory.items() if k not in common
                               and _matching_end(v,axis=axis,endpoint=hi,offsets=offsets)),
            }
        start=[(who,x) for who in (a,b) for x in ends[who]["start"]]
        finish=[(who,x) for who in (a,b) for x in ends[who]["finish"]]
        unique=(len(start)==1 and len(finish)==1 and start[0][0]!=finish[0][0]
                and start[0][1]!=finish[0][1])
        extent={"axis":axis,"original_axis_span_pt":[lo,hi],
                "original_cross_offsets_pt":sorted(offsets)}
        rows.append({
            "opening_ids":[a,b],"shared_original_g17_observation_ids":common,
            "shared_face_ids":sorted(shared_faces),
            "original_face_source_parents":{
                cid:sorted(oa[cid]["parents"]) for cid in sorted(shared_faces)},
            "all_original_competing_end_candidates":ends,
            "source_closed_pier_geometry_candidate":extent,
            "source_closed_pier_candidate":bool(unique),
            "source_closed_source_observation_ids":(
                sorted([*shared_faces,start[0][1],finish[0][1]]) if unique else []),
            "reason":("complete_own_source_two_end_pier_geometry"
                      if unique else "competing_or_missing_original_two_end_caps"),
            "original_ink_verified_by_this_function":False,
            "physical_structural_wall_role_granted":False,
            "cross_resolution_equivalence_granted":False,
            "wall_host_granted":False,
            "opening_count_granted":False,
            "metric_quantity_granted":False,
        })
    return {
        "status":STATUS,"source_sharing_pairs":rows,
        "original_producer_authentication_performed_by_pure_function":False,
        "new_source_derived_W4_host_granted":False,
        "cross_resolution_equivalence_granted":False,
        "metric_width_height_granted":False,
        "opening_count_granted":False,
    }


def source_original_dual_end_replay(pdf:bytes,expected_sha256:str):
    if type(pdf)!=bytes or sha256(pdf).hexdigest()!=expected_sha256:
        raise ValueError("invalid original architectural source SHA256")
    src=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub=src.ingest_native_pdf_bytes(
        document_id="live-source:"+expected_sha256[:32],
        source_bytes=pdf,
        source_locator="memory://gptmax-original-shared-g17-face-ends.pdf",
        page_ids=(3,))
    c=compose_live_wall_opening_authority(
        source_visibility_producer=src,revision_id=pub.revision.revision_id,page_ids=("3",))
    v=compose_live_physical_opening_voids(
        source_visibility_producer=src,wall_opening_composition=c)
    before=_retention(c,v,verify_customer_rows=True)
    snapshot=src.published_snapshot_for_revision(pub.revision.revision_id)
    if (len(c.opening_bindings)!=21
            or sum(bool(t.record_id) for t in c.opening_bindings)!=15
            or sum(bool(t.record_id) for t in c.host_frames)!=9
            or len(before["quantities"])!=8 or len(before["customer_rows"])!=8):
        raise RuntimeError("original source producer checkpoint moved")
    visibility=src.authority()
    physical=src.physical_opening_authority()
    inventoried={}
    for trace in c.opening_bindings:
        selector=ObservationSelector(
            document_id=snapshot.revision.document_id,
            revision_id=snapshot.revision.revision_id,
            source_sha256=expected_sha256,
            snapshot_id=snapshot.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        result=physical.prove_existence(selector)
        opening=result.existence_record
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.proposition!=PHYSICAL_OPENING_EXISTS
                or opening is None or opening.record_id!=trace.opening_identity_id):
            raise RuntimeError("opening physical existence not independently source owned")
        obs={}
        for sid in sorted(opening.source_observation_ids):
            receipt=visibility.resolve_raster_opening_primitive(
                ObservationSelector(
                    document_id=selector.document_id,revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,snapshot_id=selector.snapshot_id,
                    observation_id=sid))
            o=receipt.observation
            if (receipt.status is not EvidenceResolutionStatus.CORROBORATED
                    or o is None or o.page_id!="3" or not o.derivation_parent_ids):
                raise RuntimeError("missing producer-authenticated source observation")
            obs[sid]={"id":sid,"kind":o.observation_kind,
                      "geometry_pdf_pts":list(o.geometry),
                      "parents":sorted(o.derivation_parent_ids)}
        inventoried[opening.record_id]=obs
    out=audit_shared_original_g17_dual_end_piers(inventoried)
    if (src.published_snapshot_for_revision(pub.revision.revision_id)!=snapshot
            or sha256(src._producer._store.source_bytes_by_revision[
                pub.revision.revision_id]).hexdigest()!=expected_sha256
            or _retention(c,v,verify_customer_rows=True)!=before):
        raise RuntimeError("existing signed quantity/customer or original snapshot changed")
    out.update({
        "source_sha256":expected_sha256,
        "source_snapshot_id":snapshot.snapshot.snapshot_id,
        "source_revision_id":snapshot.revision.revision_id,
        "decision_scope_id":"wall-source:page-3",
        "original_source_producer_replayed_and_records_proven":True,
        "original_source_snapshot_and_customer_receipts_unchanged":True,
        "old_physical_count":21,"old_host_count":15,"old_frame_count":9,
        "old_signed_area_count":8,"old_customer_verified_count":8,
    })
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    result=source_original_dual_end_replay(args.pdf.read_bytes(),args.sha256)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,
                                      allow_nan=False)+"\n",encoding="utf8")
    for pair in result["source_sharing_pairs"]:
        print(*(p[-8:] for p in pair["opening_ids"]),
              pair["reason"],pair["source_closed_pier_candidate"],
              pair.get("source_closed_source_observation_ids"))

if __name__=="__main__":
    main()
