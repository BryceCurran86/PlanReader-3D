"""Original-source viewport audit for native G17 opening hypotheses.

Only positively authenticated drawn non-plan frames can oppose floor-plan
promotion. A title block, dimension annotation, nearest window or missing
viewport alone cannot delete an opening or manufacture a physical host.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_opening_viewport_scope_shadow import (
    IN_AUTHENTICATED_FLOOR_PLAN, IN_AUTHENTICATED_NON_PLAN,
    EVIDENCE_DIRECTION_AGAINST_PROMOTION, EVIDENCE_DIRECTION_SCOPE_ONLY,
    assess_opening_candidate_viewport_scope,
)
from pb_source_visibility_authority import (
    SourceVisibilityProducer, NATIVE_PDF_VISIBLE_SEGMENT, RASTER_PDF_VISIBLE_SEGMENT,
)
from pb_source_observation_authority import ObservationSelector
from pb_migration_contracts import EvidenceResolutionStatus


def audit_native_candidate_viewports(bindings, report):
    """Retain every possible G17 candidate, never select first/nearest view."""
    if not isinstance(bindings, (list, tuple)):
        raise TypeError("opening binding census unavailable")
    candidate_by_source = {}
    seen_candidates = set()
    for candidate in report.candidate_scopes:
        cid = candidate.candidate_id
        if not isinstance(cid, str) or not cid or cid in seen_candidates:
            raise ValueError("duplicated/foreign G17 candidate address")
        seen_candidates.add(cid)
        for sid in candidate.source_observation_ids:
            if not isinstance(sid, str) or not sid.strip():
                raise ValueError("invalid candidate source provenance")
            candidate_by_source.setdefault(sid, []).append(candidate)
    seen = set()
    rows = []
    for binding in bindings:
        oid = getattr(binding, "opening_identity_id", None)
        representative = getattr(binding, "representative_observation_id", None)
        if (not isinstance(oid, str) or not oid.strip() or oid in seen
                or not isinstance(representative, str) or not representative.strip()):
            raise ValueError("missing/duplicated source physical identity")
        seen.add(oid)
        matched = candidate_by_source.get(representative, ())
        matched = sorted(matched, key=lambda x:x.candidate_id)
        if not matched:
            verdict = "SOURCE_CANDIDATE_VIEWPORT_MEMBERSHIP_UNPROVEN"
        elif (all(c.existence_corroborated
                  and c.scope == IN_AUTHENTICATED_NON_PLAN
                  and c.evidence_direction == EVIDENCE_DIRECTION_AGAINST_PROMOTION
                  and c.boundary_source == "vector_frame" for c in matched)):
            verdict = "AUTHENTICATED_DRAWN_NONPLAN_VIEW_TYPED_OPPOSITION"
        elif (any(c.existence_corroborated
                  and c.scope == IN_AUTHENTICATED_FLOOR_PLAN
                  and c.evidence_direction == EVIDENCE_DIRECTION_SCOPE_ONLY
                  for c in matched)):
            verdict = "FLOORPLAN_SOURCE_SCOPE_ONLY"
        else:
            verdict = "VIEWPORT_OR_SOURCE_CANDIDATE_AMBIGUOUS"
        rows.append({
            "opening_identity_id":oid,
            "representative_source_observation_id":representative,
            "host_wall_id":getattr(binding, "host_wall_id", None),
            "source_host_reason_codes":list(getattr(binding, "reason_codes", ())),
            "candidate_viewport_ids":[c.candidate_id for c in matched],
            "all_viewport_scope_alternatives":[{
                "candidate_id":c.candidate_id, "scope":c.scope,
                "view_id":c.view_id, "view_type":c.view_type,
                "structural_pattern":c.structural_pattern,
                "auth_boundary":c.boundary_source,
                "evidence_direction":c.evidence_direction,
                "existence_corroborated":bool(c.existence_corroborated),
            } for c in matched],
            "first_unproved_or_opposing_scope":verdict,
            "original_existence_retracted":False,
            "physical_host_publication_allowed":False,
            "opening_count_publication_allowed":False,
        })
    return rows


def original_native_viewport_scope(source_bytes:bytes, *, expected_source_sha:str,
                                   page_id:str) -> dict:
    if type(source_bytes) is not bytes:
        raise TypeError("source PDF must be immutable bytes")
    if (not isinstance(expected_source_sha,str)
            or re.fullmatch(r"[0-9a-f]{64}",expected_source_sha) is None
            or sha256(source_bytes).hexdigest() != expected_source_sha):
        raise ValueError("original PDF source SHA mismatch")
    if (not isinstance(page_id,str) or not page_id.isascii() or not page_id.isdigit()
            or int(page_id)<1 or str(int(page_id))!=page_id):
        raise ValueError("invalid canonical source page scope")
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{expected_source_sha[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(page_id,))
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(page_id,))
    scoped=assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_id=page_id)
    updated=source.published_snapshot_for_revision(published.revision.revision_id)
    if updated is None or updated.revision.source_sha256 != expected_source_sha:
        raise ValueError("source viewport snapshot lineage unavailable")
    bindings=tuple(composition.opening_bindings)
    frames=tuple(composition.host_frames)
    rows=audit_native_candidate_viewports(bindings, scoped)
    total_hosts=sum(bool(row.host_wall_id) for row in bindings)
    total_frames=sum(bool(row.record_id) for row in frames)
    return {
       "source_sha256":expected_source_sha,"page_id":page_id,
       "revision_id":updated.revision.revision_id,
       "snapshot_id":updated.snapshot.snapshot_id,
       "opening_existence_count":len(bindings),
       "original_authenticated_host_count":total_hosts,
       "original_authenticated_frame_count":total_frames,
       "candidate_viewport_scope_status":scoped.status.value,
       "candidate_viewport_scope_reason_codes":list(scoped.reason_codes),
       "authenticated_viewports":[asdict(v) for v in scoped.authenticated_viewports],
       "unauthenticated_viewport_count":scoped.unauthenticated_viewport_count,
       "source_opening_rows":rows,
       "source_universe_completeness_proven":False,
       "original_source_existence_retraction_allowed":False,
       "host_publication_allowed":False,
       "opening_count_publication_allowed":False,
       "metric_quantity_publication_allowed":False,
       "benchmark_accuracy":None,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--expected-source-sha",required=True)
    parser.add_argument("--page-id",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=original_native_viewport_scope(args.pdf.read_bytes(),
        expected_source_sha=args.expected_source_sha,page_id=args.page_id)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"openings":report["opening_existence_count"],
        "source_hosts":report["original_authenticated_host_count"],
        "typed_nonplan_oppositions":sum(
            r["first_unproved_or_opposing_scope"]=="AUTHENTICATED_DRAWN_NONPLAN_VIEW_TYPED_OPPOSITION"
            for r in report["source_opening_rows"]),"host_publication":False}))


if __name__=="__main__":
    main()
