"""Six Lot16 missing hosts: fresh original-G17 isolated W2/W3/W4 source proof.

This deliberately calls the EXISTING opening-local producer against the
original SHA-authenticated selected source root. Its wall candidates are
source-role candidates ONLY: never a canonical W4/host/frame/area/count.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention

SOURCE_ONLY="gptmax_original_six_g17_local_w4_source_role_abstain"


def summarize_local_source_shadow(shadow, opening_id):
    """Preserve each original face, W2 snap event and W4 candidate. No grant."""
    if shadow.physical_opening_id != opening_id:
        raise ValueError("source shadow returned a different physical opening")
    if shadow.status is not EvidenceResolutionStatus.ABSTAINED:
        raise ValueError("source-only graph illegally promoted a structural wall")
    if (shadow.scope_complete or shadow.physical_wall_role_granted
            or shadow.opening_host_granted or shadow.metric_quantity_granted):
        raise ValueError("nonpublishing G17 source shadow granted an authority")
    if len(shadow.flanks) != 2:
        raise ValueError("source-own complete left/right G17 flanks unavailable")
    rows=[]
    observations=set()
    for flank in shadow.flanks:
        ids=tuple(flank.source_observation_ids)
        if len(ids)!=3 or len(set(ids))!=3 or observations.intersection(ids):
            raise ValueError("duplicate or incomplete original flank observation")
        observations.update(ids)
        parents=tuple(flank.source_parent_ids)
        if len(parents)!=3 or len(set(parents))!=3:
            raise ValueError("source face/end parents incomplete")
        if flank.default_snap_collapsed_count < 0:
            raise ValueError("invalid W2 source collapse count")
        scoped={}
        for level, records in (
            ("normal_2_5pt_w2_snap",flank.default_records),
            ("independent_zero_snap_counterfactual",flank.exact_coordinate_records),
        ):
            candidate_rows=[]
            seen=set()
            for record in records:
                candidate_id=record.wall_candidate_id
                if not candidate_id or candidate_id in seen:
                    raise ValueError("duplicate source-local wall candidate")
                seen.add(candidate_id)
                identity=record.physical_identity
                sources=tuple(identity.source_primitive_ids)
                if (not identity.usable or not identity.candidate_identity_id
                    or not sources or not all(x.startswith("raster_opening_primitive:")
                                               for x in sources)):
                    raise ValueError("source-local W4 lacked original G17 ancestry")
                candidate_rows.append({
                    "source_local_w4_id":candidate_id,
                    "source_local_candidate_identity_id":identity.candidate_identity_id,
                    "all_source_primitive_ancestry_ids":sorted(sources),
                    "original_w2_edge_ids":list(sorted(identity.edge_ids)),
                    "source_local_structural_role_proven":False,
                    "source_local_physical_equivalence_proven":False,
                    "source_local_opening_host_proven":False,
                })
            scoped[level]=sorted(candidate_rows,key=lambda x:x["source_local_w4_id"])
        if not flank.source_ink_supported and any(scoped.values()):
            raise ValueError("non-solid original ink created a W4 candidate")
        rows.append({
            "original_g17_source_observation_ids":sorted(ids),
            "original_g17_source_parent_ids":sorted(parents),
            "original_300dpi_source_paint_supported":bool(flank.source_ink_supported),
            "original_ink_reason_codes":list(flank.reason_codes),
            "original_default_2_5pt_w2_snap_collapsed_count":flank.default_snap_collapsed_count,
            "original_default_w3_junction_types":list(flank.default_junction_types),
            "original_exact_w3_junction_types":list(flank.exact_junction_types),
            **scoped,
            "physical_wall_role_proven":False,
            "host_binding_granted":False,
        })
    return {
        "physical_opening_id":opening_id,
        "opening_local_original_source_flanks":sorted(rows,
            key=lambda x:tuple(x["original_g17_source_observation_ids"])),
        "real_original_candidate_scope_complete":False,
        "all_W4_competing_wall_ids_preserved":True,
        "physical_equivalence_granted":False,
        "new_host_granted":False,
        "new_frame_granted":False,
        "new_metric_quantity_granted":False,
        "opening_count_granted":False,
    }


def original_unhosted_source_role_replay(pdf:bytes,*,expected_sha256:str,page_id:str="3"):
    if type(pdf) is not bytes or not pdf or sha256(pdf).hexdigest()!=expected_sha256:
        raise ValueError("original architectural PDF hash mismatch")
    if page_id!="3":
        raise ValueError("this verification checks the original selected-page root only")
    src=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub=src.ingest_native_pdf_bytes(
        document_id=f"live-source:{expected_sha256[:32]}",source_bytes=pdf,
        source_locator="memory://original-selected-g17-six-shadow.pdf",
        page_ids=(3,))
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=src,revision_id=pub.revision.revision_id,
        page_ids=(page_id,))
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=src,wall_opening_composition=comp)
    selected=src.published_snapshot_for_revision(pub.revision.revision_id)
    old=_retention(comp,voids,verify_customer_rows=True)
    if (len(comp.opening_bindings)!=21
        or sum(bool(v.record_id) for v in comp.opening_bindings)!=15
        or sum(bool(v.record_id) for v in comp.host_frames)!=9
        or len(old["quantities"])!=8 or len(old["customer_rows"])!=8):
        raise RuntimeError("genuine original producer baseline changed; inspect first")
    missing=sorted((b for b in comp.opening_bindings if b.record_id is None),
                   key=lambda x:x.opening_identity_id)
    if len(missing)!=6:
        raise RuntimeError("source host universe changed")
    rows=[]
    for trace in missing:
        selector=ObservationSelector(
            document_id=selected.revision.document_id,
            revision_id=selected.revision.revision_id,
            source_sha256=expected_sha256,
            snapshot_id=selected.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        fresh=build_opening_local_g17_wall_shadow(src,selector)
        row=summarize_local_source_shadow(fresh,trace.opening_identity_id)
        row["original_host_first_failures"]=list(trace.reason_codes)
        row["original_source_representative_observation_id"]=trace.representative_observation_id
        row["source_snapshot_id"]=selected.snapshot.snapshot_id
        row["source_decision_scope_id"]="wall-source:page-3"
        rows.append(row)
    if (src.published_snapshot_for_revision(pub.revision.revision_id)!=selected
        or sha256(src._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest()!=expected_sha256
        or _retention(comp,voids,verify_customer_rows=True)!=old):
        raise RuntimeError("original source snapshot or eight customer receipts mutated")
    return {
        "status":SOURCE_ONLY,
        "source_sha256":expected_sha256,
        "source_revision_id":pub.revision.revision_id,
        "source_snapshot_id":selected.snapshot.snapshot_id,
        "source_decision_scope_id":"wall-source:page-3",
        "original_physical_openings":len(comp.opening_bindings),
        "original_authenticated_hosts":15,
        "original_complete_frames":9,
        "original_signed_area_count":len(old["quantities"]),
        "original_customer_verification_count":len(old["customer_rows"]),
        "unhosted_source_cases":rows,
        "original_source_snapshot_and_customer_rows_unchanged":True,
        "all_source_candidates_not_physical_roles":True,
        "cross_resolution_physical_equivalence_granted":False,
        "new_host_granted":False,"new_frame_granted":False,
        "metric_width_height_granted":False,"opening_count_granted":False,
        "new_firm_quantity_granted":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    r=original_unhosted_source_role_replay(a.pdf.read_bytes(),expected_sha256=a.sha256)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print("actual original",r["original_physical_openings"],r["original_authenticated_hosts"],
          r["original_complete_frames"],r["original_signed_area_count"])
    for row in r["unhosted_source_cases"]:
        print(row["physical_opening_id"],[
            (v["original_300dpi_source_paint_supported"],
             len(v["normal_2_5pt_w2_snap"]),
             len(v["independent_zero_snap_counterfactual"]))
            for v in row["opening_local_original_source_flanks"]])

if __name__=="__main__":
    main()
