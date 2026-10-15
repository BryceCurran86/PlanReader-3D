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
    return {
        "status": "UNPUBLISHED_ORIGINAL_SAME_ROOT_F07_G17_SOURCE_AUDIT",
        "source_sha256": digest,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": page_id,
        "view_result": view_result,
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
