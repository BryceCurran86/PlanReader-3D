"""Actual original six unhosted Lot16 144/300 DPI source-paint comparison.

Uses existing G17 source selectors, isolated G17 wall candidates and ordinary
page-wide W4; lattice matches NEVER create physical wall, host or quantities.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_dual_dpi_source_correspondence_shadow import g17_144_300_source_correspondence_shadow
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED, PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention

STATUS="original_unhosted_g17_144_300_source_cross_resolution_shadow"


def validate_144_correspondence(data):
    if not isinstance(data,dict):
        raise ValueError("source comparison missing")
    if any(data.get(x) is not False for x in (
        "physical_wall_role_granted","cross_source_equivalence_granted",
        "host_granted","metric_quantity_granted","complete_wall_universe_proven")):
        raise ValueError("source data illegally grants wall or quantity authority")
    rows=data.get("openings")
    if not isinstance(rows,list) or len(rows)!=6:
        raise ValueError("six source-opening scopes required")
    identities=set()
    summary=[]
    for row in rows:
        ident=row.get("physical_opening_id")
        if not isinstance(ident,str) or not ident or ident in identities:
            raise ValueError("missing or duplicate original opening identity")
        identities.add(ident)
        if row.get("host_granted") is not False or row.get("metric_quantity_granted") is not False:
            raise ValueError("source-only G17 opening illegally promoted")
        flanks=row.get("flanks")
        if not isinstance(flanks,list) or len(flanks)!=2:
            raise ValueError("incomplete original G17 flanks")
        totals={"original_300dpi_paint_supported_flanks":0,
                "original_144dpi_paint_matched_edges":0,
                "original_144dpi_paint_disagreed_edges":0,
                "ordinary_W4_lattice_candidates":0}
        for flank in flanks:
            supported=flank.get("source_ink_supported")
            if type(supported) is not bool:
                raise ValueError("invalid original source paint status")
            totals["original_300dpi_paint_supported_flanks"]+=int(supported)
            if not supported and flank.get("source_edges"):
                raise ValueError("unsupported 300dpi flank created wall candidates")
            seen=set()
            for edge in flank.get("source_edges",[]):
                edgeid=edge.get("g17_edge_id")
                if not isinstance(edgeid,str) or not edgeid or edgeid in seen:
                    raise ValueError("G17 original W2 edge identity ambiguous")
                seen.add(edgeid)
                if (edge.get("w4_cross_source_equivalence_proven") is not False
                        or edge.get("structural_wall_role_proven") is not False):
                    raise ValueError("144dpi raster match incorrectly grants W4 role")
                profile=edge.get("144_pixel_source_profile",{})
                match=profile.get("original_144_solid_and_unchanged") is True
                totals["original_144dpi_paint_matched_edges"]+=int(match)
                totals["original_144dpi_paint_disagreed_edges"]+=int(
                    not match and profile.get("status")=="evaluated")
                competitors=edge.get("144_w4_lattice_candidates")
                if not isinstance(competitors,list):
                    raise ValueError("competing W4 inventory missing")
                ids=[(v["wall_candidate_id"],v["edge_id"],v["candidate_identity_id"])
                     for v in competitors]
                if len(ids)!=len(set(ids)):
                    raise ValueError("duplicate same original W4 competitor")
                totals["ordinary_W4_lattice_candidates"]+=len(competitors)
        summary.append({"physical_opening_id":ident,**totals,
                        "structural_role_proven":False,
                        "144_to_300_physical_wall_equivalence_proven":False,
                        "host_or_metric_granted":False})
    return sorted(summary,key=lambda r:r["physical_opening_id"])


def original_six_crossresolution_source(pdf:bytes,*,source_sha256:str):
    if type(pdf) is not bytes or not pdf or sha256(pdf).hexdigest()!=source_sha256:
        raise ValueError("original immutable source bytes SHA mismatch")
    src=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub=src.ingest_native_pdf_bytes(
        document_id="live-source:"+source_sha256[:32],source_bytes=pdf,
        source_locator="memory://gptmax-original-six-144-300-source.pdf",
        page_ids=(3,))
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=src,revision_id=pub.revision.revision_id,page_ids=("3",))
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=src,wall_opening_composition=comp)
    selected=src.published_snapshot_for_revision(pub.revision.revision_id)
    old=_retention(comp,voids,verify_customer_rows=True)
    if (len(comp.opening_bindings)!=21 or sum(bool(x.record_id) for x in comp.opening_bindings)!=15
            or sum(bool(f.record_id) for f in comp.host_frames)!=9 or
            len(old["quantities"])!=len(old["customer_rows"])!=8):
        raise RuntimeError("original signed source and customer baseline changed")
    root={key:getattr(selected.revision,key) for key in ("document_id","revision_id","source_sha256")}
    scope=comp.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(**root,snapshot_id=selected.snapshot.snapshot_id,
                                      page_id="3",decision_scope_id="wall-source:page-3"))
    if (scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope.scope_complete or scope.proposition != PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
            or scope.equivalence is None):
        raise RuntimeError("original ordinary 144dpi W4 wall scope unavailable")
    missing=sorted((row for row in comp.opening_bindings if row.record_id is None),
                   key=lambda item:item.opening_identity_id)
    if len(missing)!=6:raise RuntimeError("unhosted source-opening inventory changed")
    shadows=[]
    for trace in missing:
        selector=ObservationSelector(
            document_id=selected.revision.document_id,revision_id=selected.revision.revision_id,
            source_sha256=source_sha256,snapshot_id=selected.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        sh=build_opening_local_g17_wall_shadow(src,selector)
        if (sh.physical_opening_id!=trace.opening_identity_id
                or sh.opening_host_granted or sh.physical_wall_role_granted
                or len(sh.flanks)!=2):
            raise RuntimeError("source G17 shadow lost own original identity")
        shadows.append(sh)
    evidence=g17_144_300_source_correspondence_shadow(
        src,selected,page_id="3",opening_shadows=shadows,
        ordinary_w4_records=scope.records)
    rows=validate_144_correspondence(evidence)
    if (src.published_snapshot_for_revision(pub.revision.revision_id)!=selected
        or sha256(src._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest()!=source_sha256
        or _retention(comp,voids,verify_customer_rows=True)!=old):
        raise RuntimeError("source-original/canonical/signed customer evidence mutated")
    return {
        "status":STATUS,"source_sha256":source_sha256,
        "source_revision_id":selected.revision.revision_id,
        "source_snapshot_id":selected.snapshot.snapshot_id,
        "decision_scope_id":"wall-source:page-3",
        "original_physical_openings":21,"original_authenticated_hosts":15,
        "original_complete_frames":9,"original_signed_area_count":8,
        "original_customer_verified_count":8,
        "all_six_original_cross_resolution_rows":rows,
        "complete_original_source_pixel_and_w4_competitor_evidence":evidence,
        "original_w4_candidates_examined":len(scope.records),
        "original_source_signed_customer_evidence_unchanged":True,
        "physical_wall_role_granted":False,
        "host_granted":False,"frame_granted":False,
        "ordered_dimensions_granted":False,"opening_count_granted":False,
        "new_firm_quantity_granted":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    result=original_six_crossresolution_source(a.pdf.read_bytes(),source_sha256=a.sha256)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    for row in result["all_six_original_cross_resolution_rows"]:
        print(row)

if __name__=="__main__":
    main()
