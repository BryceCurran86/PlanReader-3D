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
    EDGE_OWNERSHIP_COMPETING,
    SourceRoomFaceSelector,
    _source_interval_owner_check,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _competing_source_edges(wall, face):
    """Expose every contender's original primitives without electing a wall.

    An original W4 identity and an original source edge are evidence, not
    structural equivalence; GRID and crop negatives must remain in force.
    """
    by_id = {r.wall_candidate_id: r for r in wall.records
             if hasattr(r, "wall_candidate_id")}
    if len(by_id) != len(wall.records):
        raise RuntimeError("duplicate_source_w4_candidate_identity")
    equivalence = getattr(wall, "equivalence", None)
    pair_decisions = {}
    if equivalence is not None:
        for left, right, value in getattr(equivalence, "pair_classifications", ()):
            pair_decisions.setdefault(tuple(sorted((left, right))), set()).add(
                getattr(value, "value", str(value))
            )
    # Reuse the production proof as a *read-only diagnosis*, never as a
    # permission to rewrite the authoritative face decision.
    source_parent_proof = _source_interval_owner_check(wall, tuple(wall.records))
    rows = []
    for finding in face.ownership_evaluation.unresolved_faces:
        for edge in finding.edge_findings:
            if edge.kind != EDGE_OWNERSHIP_COMPETING:
                continue
            candidates = []
            for wall_id in edge.wall_ids:
                record = by_id.get(wall_id)
                if record is None:
                    candidates.append({"wall_id": wall_id, "w4_record_unavailable": True})
                    continue
                fragments = tuple(
                    {"edge_id": f.edge_id,
                     "geometry": tuple(f.geometry),
                     "source_primitive_ids": tuple(f.source_primitive_ids)}
                    for f in record.source_edge_fragments
                )
                candidates.append({
                    "wall_id": wall_id,
                    "source_primitive_ids": tuple(record.physical_identity.source_primitive_ids),
                    "source_edge_fragments": fragments,
                    "source_snap_collapsed_fragment_count":
                        len(record.source_snap_collapsed_fragments),
                    "structural_wall_role_proven_by_this_report": False,
                })
            pair_rows = []
            wall_ids = tuple(sorted(edge.wall_ids))
            for index, left in enumerate(wall_ids):
                for right in wall_ids[index + 1:]:
                    pair_rows.append({
                        "left_wall_id": left,
                        "right_wall_id": right,
                        "sealed_w4_equivalence_classes": tuple(sorted(
                            pair_decisions.get((left, right), ())
                        )),
                    })
            rows.append({
                "face_id": finding.face_id,
                "competing_planar_edge": tuple(edge.edge),
                "candidate_walls": candidates,
                "pairwise_source_equivalence_receipts": pair_rows,
                "existing_local_source_interval_proof": bool(
                    source_parent_proof(edge.edge, wall_ids)
                ),
                "unique_source_wall_owner_granted": False,
            })
    return rows


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
        # Candidate-only. Even a completely edge-owned *shadow* face is NOT a
        # published SourceRoomFace nor a material/floor/quantity identity.
        "shadow_evaluated_face_count": evaluation.face_count,
        "shadow_owned_face_count": len(evaluation.owned_face_ids),
        "shadow_owned_face_ids": evaluation.owned_face_ids,
        "shadow_degenerate_owned_face_ids": evaluation.degenerate_owned_face_ids,
        "shadow_largest_owned_face_area_page_pts2":
            evaluation.largest_owned_face_area_pt2,
        "shadow_owned_face_publication_granted": False,
        "competing_source_edges": _competing_source_edges(wall, face),
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
        source_locator="memory://original-source-view.pdf",
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
