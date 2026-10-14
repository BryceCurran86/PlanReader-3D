"""Read-only original-source F.07 -> W4 -> SourceRoomFace first-failure census.

This diagnostic accepts a source PDF file and 1-based page address ONLY.
It does not select room or finish owners, publish quantities, modify the source
producer, change GRID roles, or read the frozen benchmark.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _face_report(wall, face):
    """Preserve producer status and evidence; never promote an abstained ring."""
    w4_owner = (
        wall.document_id, wall.revision_id, wall.source_sha256,
        wall.snapshot_id, wall.page_id, wall.decision_scope_id,
    )
    face_owner = (
        face.document_id, face.revision_id, face.source_sha256,
        face.snapshot_id, face.page_id, face.decision_scope_id,
    )
    if w4_owner != face_owner:
        raise ValueError("source_face_cross_revision_or_scope_mismatch")
    positive = face.status is EvidenceResolutionStatus.CORROBORATED
    records = tuple(asdict(x) for x in face.records)
    rejected = tuple(asdict(x) for x in face.abstained_faces)
    evaluation = face.ownership_evaluation
    return {
        "source_sha256": wall.source_sha256,
        "revision_id": wall.revision_id,
        "snapshot_id": wall.snapshot_id,
        "page_id": wall.page_id,
        "decision_scope_id": wall.decision_scope_id,
        "viewport_id": wall.viewport_id,
        "viewport_view_type": wall.viewport_view_type,
        "viewport_bbox_pdf_pts": wall.viewport_bbox,
        "w4_status": wall.status.value,
        "w4_scope_complete": bool(wall.scope_complete),
        "w4_reason_codes": wall.reason_codes,
        "w4_candidate_count": len(wall.records),
        "source_room_face_status": face.status.value,
        "source_room_face_scope_complete": bool(face.scope_complete),
        "source_room_face_universe_complete": bool(face.face_universe_complete),
        "source_room_face_reason_codes": face.reason_codes,
        "source_room_face_record_count": len(records),
        "source_room_face_abstained_count": len(rejected),
        "source_room_face_records": records,
        "source_room_face_abstentions": rejected,
        "shadow_edge_owner_status": evaluation.status,
        "shadow_competing_edge_count": evaluation.competing_edge_count,
        "shadow_unowned_edge_count": evaluation.unowned_edge_count,
        "shadow_unresolved_face_ids": evaluation.unresolved_face_ids,
        "shadow_competing_wall_ids": evaluation.competing_wall_ids,
        # An incomplete room face scope is NOT a commercial floor or finish.
        "unique_physical_room_label_claim_granted": False,
        "physical_cross_sheet_equivalence_granted": False,
        "ft3_definition_claim_granted": False,
        "metric_quantity_claim_granted": False,
        "customer_row_claim_granted": False,
        "benchmark_match_claim_granted": False,
    }


def replay(source_bytes: bytes, *, page_number: int):
    """Run exact immutable source-authorized W4, then original SourceRoomFace."""
    if type(page_number) is not int or page_number < 1:
        raise ValueError("source_page_number_invalid")
    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://source-owned-face-original.pdf",
        page_ids=(str(page_number),),
    )
    before = source.published_snapshot_for_revision(published.revision.revision_id)
    walls = PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
        source, page_ids=(str(page_number),)
    ).authority()
    assert source.published_snapshot_for_revision(published.revision.revision_id) == before
    faces = build_source_room_face_authority(walls)
    assert source.published_snapshot_for_revision(published.revision.revision_id) == before
    selectors = walls.selectors_for_authenticated_viewports(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=sha,
        snapshot_id=before.snapshot.snapshot_id,
        page_id=str(page_number),
    )
    results = []
    for selector in selectors:
        wall = walls.resolve_scope(selector)
        if wall.scope_kind != "viewport":
            raise RuntimeError("source_plan_w4_scope_not_a_viewport")
        face = faces.resolve_scope(SourceRoomFaceSelector(
            document_id=wall.document_id,
            revision_id=wall.revision_id,
            source_sha256=wall.source_sha256,
            snapshot_id=wall.snapshot_id,
            page_id=wall.page_id,
            decision_scope_id=wall.decision_scope_id,
        ))
        results.append(_face_report(wall, face))
    return {
        "source_sha256": sha,
        "source_page": page_number,
        "source_snapshot_preserved": (
            source.published_snapshot_for_revision(published.revision.revision_id)
            == before
        ),
        "source_owned_w4_scope_count": len(results),
        "scopes": results,
        "new_commercial_quantities": [],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    source_bytes = args.pdf.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != args.sha:
        raise RuntimeError("immutable_original_pdf_sha_mismatch")
    report = replay(source_bytes, page_number=args.page)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({
        "source_sha_verified":True,
        "source_page":args.page,
        "source_owned_w4_scopes":len(report["scopes"]),
        "source_snapshot_preserved":report["source_snapshot_preserved"],
        "faces": [{
            k:row[k] for k in (
                "w4_candidate_count",
                "w4_scope_complete",
                "w4_reason_codes",
                "source_room_face_record_count",
                "source_room_face_abstained_count",
                "source_room_face_reason_codes",
                "shadow_competing_edge_count",
                "shadow_unowned_edge_count",
            )
        } for row in report["scopes"]],
        "new_commercial_quantities":[],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
