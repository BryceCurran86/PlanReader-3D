"""Original-source FT3 mark to all W4-owned shadow faces: first boundary gate.

A word/face geometric intersection is only an investigation address. No
source room, label, material definition, FIRM quantity or score is published.
Retains all competing, boundary tainted and degenerate face witnesses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer, RasterTextCorroborationSelector,
)
from pb_source_material_semantic_authority import _trusted_words_by_page
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    _excluded_primitive_touches_face,
    _point_in_or_on_polygon,
    _point_on_edge,
    _edge,
    audit_source_room_face_owned_witnesses,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def audit_mark_local_faces(*, wall, face, witnesses, marks):
    """No nearest-owner election; exactly producer-indexed face candidates."""
    boundary = wall.boundary_evaluation
    evaluator = face.ownership_evaluation
    if (
        getattr(boundary, "status", None) != "evaluated"
        or getattr(evaluator, "status", None) != "evaluated"
    ):
        raise ValueError("producer_shadow_boundary_evidence_unavailable")
    witnesses = tuple(witnesses)
    ids = [w["face_id"] for w in witnesses]
    if len(ids) != len(set(ids)) or set(ids) != set(evaluator.owned_face_ids):
        raise ValueError("source_shadow_witness_universe_incomplete")
    tainted_walls = set(boundary.boundary_tainted_wall_candidate_ids)
    excluded = tuple(boundary.excluded_boundary_primitives)
    degenerate = set(evaluator.degenerate_owned_face_ids)
    obs_ids = [m["source_word_observation_id"] for m in marks]
    if len(obs_ids) != len(set(obs_ids)):
        raise ValueError("repeated_original_native_word_receipt")
    rows = []
    for mark in marks:
        bbox = mark["native_bbox_pdf_pts"]
        if len(bbox) != 4:
            raise ValueError("native_mark_bbox_invalid")
        x0, y0, x1, y1 = (float(x) for x in bbox)
        if not (x0 < x1 and y0 < y1):
            raise ValueError("native_mark_bbox_invalid")
        centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        viewport = wall.viewport_bbox
        inside_view = bool(
            viewport is not None and len(viewport) == 4 and
            viewport[0] <= x0 and viewport[1] <= y0 and
            x1 <= viewport[2] and y1 <= viewport[3]
        )
        containing = []
        for w in witnesses:
            polygon = tuple(tuple(p) for p in w["polygon_pdf_pts"])
            if not _point_in_or_on_polygon(centre, polygon):
                continue
            boundary_edges = tuple(
                _edge(p, polygon[(i + 1) % len(polygon)])
                for i, p in enumerate(polygon)
            )
            on_border = any(_point_on_edge(centre, edge) for edge in boundary_edges)
            affected_wall_ids = sorted(set(w["bounding_wall_ids"]) & tainted_walls)
            touching = sorted({
                str(p.source_observation_id)
                for p in excluded
                if _excluded_primitive_touches_face(p, polygon)
            })
            reasons = []
            if affected_wall_ids:
                reasons.append("producer_w4_boundary_tainted")
            if touching:
                reasons.append("original_excluded_structural_primitive_touches_face")
            if w["face_id"] in degenerate:
                reasons.append("producer_shadow_degenerate_or_tiny")
            if on_border:
                reasons.append("mark_centre_on_face_boundary")
            if not reasons:
                reasons.append("shadow_edge_ownership_only_not_physical_room")
            containing.append({
                "shadow_face_id": w["face_id"],
                "source_w4_candidate_wall_ids": list(w["bounding_wall_ids"]),
                "original_boundary_tainted_w4_ids": affected_wall_ids,
                "excluded_original_source_observation_ids": touching,
                "first_boundary_gates": reasons,
                "original_polygon_pdf_pts": [list(p) for p in polygon],
                "source_verified_room_face": False,
                "material_occurrence_owner": False,
            })
        containing.sort(key=lambda v: v["shadow_face_id"])
        status = (
            "source_word_integrity_unresolved"
            if not mark["source_text_verified"] else
            "source_mark_outside_authenticated_viewport"
            if not inside_view else
            "original_source_mark_not_inside_edge_owned_face"
            if not containing else
            "multiple_shadow_faces_at_original_mark"
            if len(containing) > 1 else
            "one_shadow_face_not_authentic_physical_room"
        )
        rows.append({
            "native_source_observation_id": mark["source_word_observation_id"],
            "literal_original_source_text": mark["text"],
            "native_bbox_pdf_pts": list(bbox),
            "native_text_or_raster_source_verified": bool(mark["source_text_verified"]),
            "within_source_owned_plan_viewport": inside_view,
            "first_unclosed_gate": status,
            "all_containing_shadow_faces": containing,
            "physical_room_identity_published": False,
            "ft3_occurrence_published": False,
            "finish_area_published": False,
        })
    rows.sort(key=lambda v: v["native_source_observation_id"])
    return {
        "w4_candidate_count": len(wall.records),
        "shadow_edge_owned_witness_count": len(witnesses),
        "original_source_mark_count": len(marks),
        "mark_local_boundary_first_gates": rows,
        "authoritative_source_room_face_records_retained": len(face.records),
        "new_material_occurrence_or_metric_quantity_published": False,
        "diagnostic_only": True,
    }


def replay(pdf_bytes: bytes, *, source_page: int, mark_literal: str = "FT3"):
    """Reconstruct marks and W4 faces in ONE original revision and snapshot."""
    if type(pdf_bytes) is not bytes or type(source_page) is not int or source_page < 1:
        raise ValueError("original_pdf_source_address_invalid")
    if not mark_literal.isalnum() or not mark_literal.isupper():
        raise ValueError("original_source_mark_literal_invalid")
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=pdf_bytes,
        source_locator="memory://original-room-source.pdf",
        page_ids=(str(source_page),),
    )
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    walls = PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
        source, page_ids=(str(source_page),)
    ).authority()
    faces = build_source_room_face_authority(walls)
    selectors = walls.selectors_for_authenticated_viewports(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=sha,
        snapshot_id=snapshot.snapshot.snapshot_id,
        page_id=str(source_page),
        view_type="floor_finish_plan",
    )
    words = _trusted_words_by_page(source, published).get(str(source_page), ())
    raster = RasterTextCorroborationProducer.from_source_visibility_producer(source)
    marks = []
    for w in words:
        if w.text != mark_literal:
            continue
        receipt = None
        if not w.trusted:
            receipt = raster.publish(RasterTextCorroborationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=sha,
                snapshot_id=snapshot.snapshot.snapshot_id,
                observation_id=w.observation_id,
            ))
        verified = bool(
            w.trusted or (
                receipt is not None
                and receipt.status is EvidenceResolutionStatus.CORROBORATED
                and receipt.corroborated_text == w.text
                and receipt.record is not None
            )
        )
        marks.append({
            "source_word_observation_id": w.observation_id,
            "native_bbox_pdf_pts": w.bbox,
            "source_text_verified": verified,
            "text": w.text,
            "native_text_reason_codes": list(w.reason_codes),
            "raster_status": getattr(getattr(receipt, "status", None), "value", None),
        })
    scope_reports = []
    for selector in selectors:
        wall = walls.resolve_scope(selector)
        face = faces.resolve_scope(SourceRoomFaceSelector(
            document_id=wall.document_id, revision_id=wall.revision_id,
            source_sha256=wall.source_sha256, snapshot_id=wall.snapshot_id,
            page_id=wall.page_id, decision_scope_id=wall.decision_scope_id,
        ))
        report = audit_mark_local_faces(
            wall=wall, face=face, witnesses=audit_source_room_face_owned_witnesses(wall),
            marks=marks,
        )
        report.update({
            "source_sha256": wall.source_sha256,
            "revision_id": wall.revision_id, "snapshot_id": wall.snapshot_id,
            "page_id": wall.page_id, "decision_scope_id": wall.decision_scope_id,
            "original_w4_scope_complete": wall.scope_complete,
            "source_face_status": face.status.value,
            "source_face_reason_codes": list(face.reason_codes),
        })
        scope_reports.append(report)
    return {
        "source_sha256": sha, "original_pdf_source_page": source_page,
        "source_snapshot_preserved": (
            source.published_snapshot_for_revision(published.revision.revision_id)
            == snapshot
        ),
        "source_w4_plan_scope_count": len(selectors),
        "scopes": scope_reports,
        "new_commercial_quantities": [],
        "frozen_benchmark_scored": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    payload = args.pdf.read_bytes()
    if hashlib.sha256(payload).hexdigest() != args.sha:
        raise RuntimeError("original_pdf_sha_mismatch")
    report = replay(payload, source_page=args.page)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "source_sha256": report["source_sha256"],
        "scope_count": len(report["scopes"]),
        "mark_gate_results": [
            (row["native_source_observation_id"], row["first_unclosed_gate"],
             len(row["all_containing_shadow_faces"]))
            for scope in report["scopes"]
            for row in scope["mark_local_boundary_first_gates"]
        ],
        "new_commercial_quantities": [],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
