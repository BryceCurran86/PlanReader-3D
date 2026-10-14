"""Read-only original-PDF indexed ink and W2 spans at W4-owned face SUBEDGES.

Never elect an enclosing physical wall/room, alter boundary taint, assert
post-clip visibility, or publish material, metric QuantityEvidence or customer.
Whole-W4 boundary taint and original excluded primitives remain negatives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer, _segment_segment_distance,
)
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer, RasterTextCorroborationSelector,
)
from pb_source_material_semantic_authority import _trusted_words_by_page
from pb_source_room_face_authority import (
    SourceRoomFaceSelector, _edge, _edge_contains_edge,
    audit_source_room_face_owned_witnesses, build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gpt2_native_w2_ink_source_role import read_native_ink_receipt
from tools.diag_gpt2_p11_ft3_mark_local_face_gates import audit_mark_local_faces


def inspect_local_edges(*, wall, witnesses, marks, drawings):
    """Compare EVERY original wall-face subedge with its candidate's native IDs."""
    if getattr(wall.boundary_evaluation, "status", None) != "evaluated":
        raise ValueError("unavailable_original_boundary_evaluation")
    wall_records = {rec.wall_candidate_id: rec for rec in wall.records}
    if len(wall_records) != len(wall.records):
        raise ValueError("replayed_original_w4_wall_id")
    native_excluded = tuple(wall.boundary_evaluation.excluded_boundary_primitives)
    contact_tolerance = wall.boundary_evaluation.contact_tolerance_pt
    taint_reasons = dict(wall.boundary_evaluation.boundary_taint_reason_codes)

    originals = {row["face_id"]: row for row in witnesses}
    if len(originals) != len(tuple(witnesses)):
        raise ValueError("replayed_w4_shadow_face_id")
    adjacent = {}
    for witness in witnesses:
        for wid, edge in witness["boundary_wall_edges"]:
            canonical = _edge(*edge)
            adjacent.setdefault((wid, canonical), set()).add(witness["face_id"])

    rows = []
    for mark in marks:
        for face in mark["all_containing_shadow_faces"]:
            face_id = face["shadow_face_id"]
            if face_id not in originals:
                raise ValueError("foreign_source_shadow_face")
            witness = originals[face_id]
            if set(face["source_w4_candidate_wall_ids"]) != set(witness["bounding_wall_ids"]):
                raise ValueError("mark_to_w4_wall_inventory_drift")
            inspected = []
            for wid, edge in witness["boundary_wall_edges"]:
                atom = _edge(*edge)
                rec = wall_records.get(wid)
                if rec is None:
                    raise ValueError("unowned_original_face_subedge_wall")
                fragments = tuple(rec.source_edge_fragments)
                w2_full = sorted({
                    source_id
                    for fragment in fragments
                    if _edge_contains_edge(
                        _edge(
                            fragment.geometry[:2], fragment.geometry[2:]
                        ), atom
                    )
                    for source_id in fragment.source_primitive_ids
                })
                referenced = sorted({
                    ident for fragment in fragments for ident in fragment.source_primitive_ids
                })
                native = []
                for ident in referenced:
                    try:
                        ink = read_native_ink_receipt(drawings, ident, atom)
                    except (ValueError, TypeError, IndexError, OverflowError) as exc:
                        native.append({
                            "source_primitive_id": ident,
                            "original_indexed_ink_spans_subedge": None,
                            "unavailable_reason": type(exc).__name__,
                        })
                    else:
                        native.append({
                            "source_primitive_id": ident,
                            "original_indexed_ink_spans_subedge": bool(
                                ink["native_stroke_fully_covers_atomic_wall_candidate"]
                            ),
                            "original_native_edge_pdf_pts": ink["native_source_edge_pdf_pts"],
                            "original_ink_metadata_candidate_only":
                                ink["original_native_paint_metadata_candidate_only"],
                        })
                positives = sorted(
                    n["source_primitive_id"] for n in native
                    if n["original_indexed_ink_spans_subedge"] is True
                )
                unknown = any(
                    n["original_indexed_ink_spans_subedge"] is None for n in native
                ) or not referenced
                native_status = (
                    "indexed_original_pdf_source_unavailable" if unknown else
                    "one_or_more_original_native_items_span" if positives else
                    "no_indexed_native_item_spans_w4_face_subedge"
                )
                excluded_contacts = sorted({
                    p.source_observation_id for p in native_excluded
                    if _segment_segment_distance(
                        atom[0], atom[1], (p.x1, p.y1), (p.x2, p.y2)
                    ) <= contact_tolerance
                })
                v = wall.viewport_bbox
                inside = bool(
                    v is not None and len(v) == 4 and
                    all(v[0] <= p[0] <= v[2] and v[1] <= p[1] <= v[3]
                        for p in atom)
                )
                inspected.append({
                    "source_w4_wall_id": wid,
                    "shadow_subedge_pdf_pts": [list(p) for p in atom],
                    "referenced_original_source_primitive_ids": referenced,
                    "surviving_w2_full_edge_source_primitive_ids": w2_full,
                    "indexed_original_ink_receipts": native,
                    "indexed_native_ink_status": native_status,
                    "original_native_source_ids_covering_subedge": positives,
                    "original_excluded_primitive_subedge_contact_ids": excluded_contacts,
                    "subedge_inside_original_owned_viewport": inside,
                    "other_shadow_face_ids_sharing_same_w4_subedge": sorted(
                        adjacent[(wid, atom)] - {face_id}
                    ),
                    "whole_w4_candidate_taint_reasons_retained": list(
                        taint_reasons.get(wid, ())
                    ),
                    "source_local_room_authority_granted": False,
                    "structural_wall_role_granted": False,
                })
            inspected.sort(key=lambda v: (v["source_w4_wall_id"], v["shadow_subedge_pdf_pts"]))
            if not inspected:
                raise ValueError("empty_source_room_face_boundary")
            rows.append({
                "native_mark_id": mark["native_source_observation_id"],
                "shadow_face_id": face_id,
                "original_owned_face_subedges": inspected,
                "native_text_authenticated": mark["native_text_or_raster_source_verified"],
                "original_room_ring_authentication": False,
                "room_finish_owner_authenticated": False,
                "customer_quantity_published": False,
            })
    rows.sort(key=lambda v: (v["native_mark_id"], v["shadow_face_id"]))
    return {
        "shadow_mark_face_count": len(rows),
        "mark_local_subedges": rows,
        "original_source_scope_complete_promoted": False,
        "physical_room_published": False,
        "material_occurrence_published": False,
        "metric_quantity_published": False,
        "diagnostic_only": True,
    }


def replay(pdf_bytes: bytes, *, source_page: int, code: str):
    """Replay producer-authenticated marks, W4 and face witnesses in one revision."""
    if type(pdf_bytes) is not bytes or type(source_page) is not int or source_page < 1:
        raise ValueError("original_source_scope_unavailable")
    if type(code) is not str or not code.isalnum() or not code.isupper():
        raise ValueError("original_material_code_invalid")
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        if source_page > pdf.page_count:
            raise ValueError("original_source_page_missing")
        drawings = pdf.load_page(source_page - 1).get_drawings()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=pdf_bytes,
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
        source_sha256=sha, snapshot_id=snapshot.snapshot.snapshot_id,
        page_id=str(source_page), view_type="floor_finish_plan",
    )
    words = _trusted_words_by_page(source, published).get(str(source_page), ())
    raster = RasterTextCorroborationProducer.from_source_visibility_producer(source)
    marks = []
    for w in words:
        if w.text != code:
            continue
        receipt = None
        if not w.trusted:
            receipt = raster.publish(RasterTextCorroborationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=sha, snapshot_id=snapshot.snapshot.snapshot_id,
                observation_id=w.observation_id,
            ))
        verified = bool(w.trusted or (
            receipt is not None and
            receipt.status is EvidenceResolutionStatus.CORROBORATED and
            receipt.corroborated_text == w.text and receipt.record is not None
        ))
        marks.append({
            "source_word_observation_id": w.observation_id,
            "native_bbox_pdf_pts": w.bbox, "source_text_verified": verified,
            "text": w.text,
        })
    results = []
    for selector in selectors:
        wall = walls.resolve_scope(selector)
        face = faces.resolve_scope(SourceRoomFaceSelector(
            document_id=wall.document_id, revision_id=wall.revision_id,
            source_sha256=wall.source_sha256, snapshot_id=wall.snapshot_id,
            page_id=wall.page_id, decision_scope_id=wall.decision_scope_id,
        ))
        witnesses = audit_source_room_face_owned_witnesses(wall)
        plan_marks = audit_mark_local_faces(
            wall=wall, face=face, witnesses=witnesses, marks=marks
        )
        local = inspect_local_edges(
            wall=wall, witnesses=witnesses,
            marks=plan_marks["mark_local_boundary_first_gates"],
            drawings=drawings,
        )
        results.append({
            "document_id": wall.document_id,
            "revision_id": wall.revision_id, "snapshot_id": wall.snapshot_id,
            "source_sha256": wall.source_sha256, "page_id": wall.page_id,
            "decision_scope_id": wall.decision_scope_id,
            "w4_scope_complete": wall.scope_complete,
            "native_drawings_count": len(drawings),
            "producer_w4_wall_count": len(wall.records),
            "producer_shadow_face_count": len(witnesses),
            "producer_native_text_mark_count": len(marks),
            "original_authoritative_source_room_face_count": len(face.records),
            **local,
        })
    return {
        "source_sha256": sha, "original_page": source_page,
        "snapshot_preserved": (
            source.published_snapshot_for_revision(published.revision.revision_id) == snapshot
        ),
        "scopes": results, "new_commercial_quantities": [],
        "frozen_benchmark_grant": False, "diagnostic_only": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    original = args.pdf.read_bytes()
    if hashlib.sha256(original).hexdigest() != args.sha:
        raise ValueError("original_pdf_sha_check_failed")
    report = replay(original, source_page=args.page, code=args.code)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("GPT2_MARK_LOCAL_NATIVE_SUBEDGE_GATES", json.dumps({
        "sha": report["source_sha256"],
        "scopes": len(report["scopes"]),
        "mark_local_subedges": [
            (row["native_mark_id"], row["shadow_face_id"], len(row["original_owned_face_subedges"]))
            for scope in report["scopes"] for row in scope["mark_local_subedges"]
        ], "new_commercial_quantities": [],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
