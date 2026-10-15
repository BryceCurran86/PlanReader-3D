"""Replay real F07 FLOOR_PLAN inside the SAME original G17/W4 source producer.

This is an isolated source witness only: no source, W4, host, metric, quantity,
customer, or opening count publication. An absent/ambiguous F07 result ABSTAINS.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports, is_authoritative_derived_viewport
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def classify_live_view(views, *, expected_page: int) -> dict:
    """Preserve the entire competing view census; never choose largest/first."""
    rows = [{
        "view_id": v.view_id,
        "page_number": v.page_number,
        "view_type": v.view_type,
        "status": v.status,
        "bounding_box": list(v.bounding_box) if v.bounding_box else None,
        "source_owned_plan_view_proven": bool(
            v.provenance.get("source_owned_plan_view_proven") is True),
        "authoritative": bool(is_authoritative_derived_viewport(v)),
    } for v in views]
    legitimate = [r for r in rows
                  if r["page_number"] == expected_page
                  and r["view_type"] == "floor_plan"
                  and r["status"] == "derived"
                  and r["source_owned_plan_view_proven"]
                  and r["authoritative"]]
    unsupported = [r for r in rows if r["page_number"] != expected_page]
    if unsupported:
        return {"status": "ABSTAIN", "reason": "foreign_page_view", "views": rows}
    if len(legitimate) != 1:
        return {"status": "ABSTAIN", "reason": "unique_source_floor_plan_view_unproven",
                "views": rows}
    return {"status": "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY",
            "reason": "cross_family_physical_instance_correspondence_unproven",
            "views": rows, "selected_view_id": legitimate[0]["view_id"],
            "selected_bbox_pt": legitimate[0]["bounding_box"]}



def audited_same_root_raw_view_overlay(
    *, original_unresolved_groups: tuple[dict, ...],
    closure_ids: tuple[str, ...], view_result: dict,
) -> dict:
    """Diagnostic spatial relation only, not physical-type/candidate closure.

    All raw groups MUST come from the actual selected-root producer accessor;
    a current F07 view cannot create an original G17 observation or count.
    """
    group_ids = [g["candidate_id"] for g in original_unresolved_groups]
    if len(group_ids) != len(set(group_ids)) or set(group_ids) != set(closure_ids):
        raise ValueError("incomplete or duplicated original raw candidate inventory")
    if (view_result.get("status") != "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY"
            or not view_result.get("selected_bbox_pt")):
        return {
            "status": "ABSTAIN_ORIGINAL_SOURCE_F07_UNPROVEN",
            "raw_unresolved_count": len(group_ids),
            "source_view_spatial_classifications": [],
            "typed_nonplan_proven": False,
            "physical_count_granted": False,
        }
    import math
    view = tuple(float(x) for x in view_result["selected_bbox_pt"])
    if (len(view) != 4 or not all(math.isfinite(x) for x in view)
            or view[2] <= view[0] or view[3] <= view[1]):
        raise ValueError("invalid producer-owned F07 view bbox")
    rows = []
    for group in sorted(original_unresolved_groups, key=lambda r:r["candidate_id"]):
        original = group["aperture_bbox_pt"]
        if original is None or len(original) != 4:
            raise ValueError("original candidate raw aperture unavailable")
        rect = tuple(float(x) for x in original)
        if (not all(math.isfinite(x) for x in rect)
                or rect[2] <= rect[0] or rect[3] <= rect[1]):
            raise ValueError("invalid original producer-owned G17 aperture")
        if rect[0] >= view[0] and rect[1] >= view[1] and rect[2] <= view[2] and rect[3] <= view[3]:
            relation = "GEOMETRICALLY_INSIDE_SAME_ROOT_F07"
        elif rect[2] < view[0] or rect[0] > view[2] or rect[3] < view[1] or rect[1] > view[3]:
            relation = "GEOMETRICALLY_DISJOINT_SAME_ROOT_F07"
        else:
            relation = "INTERSECTS_F07_UNPROVEN_ROLE"
        members = tuple(group["source_observation_ids"])
        if not members or len(members) != len(set(members)):
            raise ValueError("duplicate/empty original raw source observation members")
        rows.append({
            "raw_candidate_id": group["candidate_id"],
            "raw_aperture_bbox_pt": list(rect),
            "source_observation_ids": sorted(members),
            "source_view_geometric_relation_only": relation,
            "source_owned_nonplan_role_proven": False,
            "independent_physical_opening_proven": False,
        })
    return {
        "status": "UNPUBLISHED_SAME_ROOT_F07_G17_RAW_GEOMETRY_AUDIT",
        "raw_unresolved_count": len(group_ids),
        "source_view_spatial_classifications": rows,
        "typed_nonplan_proven": False,
        "physical_count_granted": False,
    }


def replay_original_live_f07_g17(original_pdf: bytes, *, page_id: str, expected_sha256: str) -> dict:
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required")
    digest = sha256(original_pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original source SHA256 mismatch")
    if type(page_id) is not str or not page_id.isdecimal() or int(page_id) < 1 or str(int(page_id)) != page_id:
        raise ValueError("canonical source page id required")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=original_pdf,
        source_locator="memory://same-root-original-f07-g17.pdf",
        page_ids=(int(page_id),),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(page_id,),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    before_receipts = _retention(composition, voids, verify_customer_rows=True)
    before_bytes = source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    if sha256(before_bytes).hexdigest() != digest:
        raise RuntimeError("source bytes mismatch before same-root F07 reader")
    before_pub = published
    views = segment_source_page_viewports(
        source,
        revision_id=published.revision.revision_id,
        page_id=page_id,
        physical_plan_view_shadow=True,
    )
    published_after = source.published_snapshot_for_revision(published.revision.revision_id)
    if published_after != before_pub:
        raise RuntimeError("source snapshot changed during same-root F07 view read")
    if sha256(source._producer._store.source_bytes_by_revision[published.revision.revision_id]).hexdigest() != digest:
        raise RuntimeError("original source bytes changed during F07 reader")
    if _retention(composition, voids, verify_customer_rows=True) != before_receipts:
        raise RuntimeError("original source/host/frame/signed output changed during F07 reader")
    view_result = classify_live_view(views, expected_page=int(page_id))
    physical = source.physical_opening_authority()
    evidence = tuple(sorted(
        (r for r in composition.opening_bindings if r.representative_observation_id),
        key=lambda r: r.opening_identity_id,
    ))
    if not evidence:
        raise ValueError("original physical opening source absent")
    first = evidence[0]
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=digest,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=first.representative_observation_id,
    )
    if physical.prove_existence(selector).status is not EvidenceResolutionStatus.CORROBORATED:
        raise ValueError("original source opening existence not authenticated")
    closure = physical.assess_raster_candidate_closure(selector)
    if closure.candidate_universe_complete:
        raise ValueError("source page opening candidate-universe unexpectedly complete")
    original_raw_groups = physical.audited_unresolved_source_candidate_groups(
        selector, family="raster")
    raw_spatial = audited_same_root_raw_view_overlay(
        original_unresolved_groups=original_raw_groups,
        closure_ids=tuple(closure.unresolved_candidate_ids),
        view_result=view_result,
    )
    if (source.published_snapshot_for_revision(published.revision.revision_id) != before_pub
            or _retention(composition, voids, verify_customer_rows=True) != before_receipts):
        raise RuntimeError("raw geometry audit modified original published source/customer receipts")
    return {
        "status": "UNPUBLISHED_ORIGINAL_SAME_ROOT_F07_G17_SOURCE_AUDIT",
        "source_sha256": digest,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": page_id,
        "view_result": view_result,
        "original_unresolved_raw_same_root_spatial_audit": raw_spatial,
        "source_snapshot_preserved": True,
        "source_bytes_preserved": True,
        "original_customer_receipts_preserved": True,
        "original_physical_count": len(before_receipts["canonical"]),
        "original_hosted_count": sum(bool(x["record_id"]) for x in before_receipts["hosts"]),
        "original_framed_count": sum(bool(x["record_id"]) for x in before_receipts["frames"]),
        "original_signed_quantity_count": len(before_receipts["quantities"]),
        "original_customer_row_count": len(before_receipts["customer_rows"]),
        "original_sealed_fingerprint": before_receipts["sealed_run"]["fingerprint"],
        "raw_candidate_count": closure.raw_candidate_count,
        "raw_unresolved_count": len(closure.unresolved_candidate_ids),
        "candidate_universe_complete": False,
        "authority_grants": {k: False for k in (
            "cross_family_physical_ownership", "typed_nonplan", "opening_count",
            "host", "frame", "scale", "metric", "quantity", "customer")},
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--page-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = replay_original_live_f07_g17(
        args.pdf.read_bytes(), page_id=args.page_id, expected_sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print({"view_stage": result["view_result"]["status"],
           "view_first_gate": result["view_result"]["reason"],
           "original_signed_areas": result["original_signed_quantity_count"],
           "source_snapshot_preserved": result["source_snapshot_preserved"]})


if __name__ == "__main__":
    main()
