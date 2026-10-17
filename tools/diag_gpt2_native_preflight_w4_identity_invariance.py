"""Shadow original source W4 identity stability: native preflight read ordering.

Compare identical source PDF bytes and identical producer code in one process.
A diagnostic get_drawings() read MUST NOT grant or revoke source authority.
When scope identity or lineage diverges, report the first exact difference
without rekeying, repairing source geometry or publishing quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import (
    audit_source_room_face_owned_witnesses,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _frozen_wall_record(rec) -> dict:
    return {
        "wall_id": rec.wall_candidate_id,
        "candidate": rec.wall_candidate.to_dict(),
        "physical_identity": {
            "candidate_identity_id": rec.physical_identity.candidate_identity_id,
            "status": rec.physical_identity.status.value,
            "source_ids": list(rec.physical_identity.source_primitive_ids),
            "edge_ids": list(rec.physical_identity.edge_ids),
            "blocking_reasons": list(rec.physical_identity.blocking_reasons),
        },
        "original_w2_lineage": [
            {"edge_id": f.edge_id, "geometry": list(f.geometry),
             "source_primitive_ids": list(f.source_primitive_ids)}
            for f in rec.source_edge_fragments
        ],
        "collapsed_original_w2": [
            {"edge_id": f.edge_id, "geometry": list(f.geometry),
             "source_primitive_ids": list(f.source_primitive_ids)}
            for f in rec.source_snap_collapsed_fragments
        ],
    }


def _freeze_scope(scope, witnesses) -> dict:
    boundary = scope.boundary_evaluation
    return {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "source_sha256": scope.source_sha256,
        "snapshot_id": scope.snapshot_id,
        "page_id": scope.page_id,
        "decision_scope_id": scope.decision_scope_id,
        "status": scope.status.value,
        "reason_codes": list(scope.reason_codes),
        "scope_complete": scope.scope_complete,
        "viewport_bbox": list(scope.viewport_bbox) if scope.viewport_bbox else None,
        "walls": [_frozen_wall_record(row) for row in sorted(
            scope.records, key=lambda x: x.wall_candidate_id
        )],
        "boundary": {
            "status": boundary.status,
            "reason_code": boundary.reason_code,
            "evaluated_wall_ids": list(boundary.evaluated_wall_candidate_ids),
            "tainted_wall_ids": list(boundary.boundary_tainted_wall_candidate_ids),
            "taint_reason_codes": [
                [wall_id, list(reasons)]
                for wall_id, reasons in boundary.boundary_taint_reason_codes
            ],
            "excluded_original_structural_primitives": [
                {"category": x.category,
                 "source_observation_id": x.source_observation_id,
                 "line": [x.x1, x.y1, x.x2, x.y2]}
                for x in boundary.excluded_boundary_primitives
            ],
        },
        "shadow_faces": [
            {"face_id": w["face_id"],
             "polygon": w["polygon_pdf_pts"],
             "bounding_wall_ids": w["bounding_wall_ids"],
             "boundary_wall_edges": w["boundary_wall_edges"]}
            for w in sorted(witnesses, key=lambda x: x["face_id"])
        ],
    }


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()).hexdigest()


def capture_original_source(pdf_bytes: bytes, *, page_no: int, preflight: bool):
    """One fully independent producer replay for one exact source byte string."""
    if type(pdf_bytes) is not bytes or type(page_no) is not int or page_no < 1:
        raise ValueError("original_source_required")
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    preflight_receipt = None
    if preflight:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            if page_no > pdf.page_count:
                raise ValueError("source_page_out_of_range")
            paths = pdf.load_page(page_no - 1).get_drawings()
            preflight_receipt = {
                "drawing_path_count": len(paths),
                "indexed_items_count": sum(len(path.get("items", ())) for path in paths),
            }
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    receipt = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=pdf_bytes,
        source_locator="memory://original-room-source.pdf",
        page_ids=(str(page_no),),
    )
    snapshot = source.published_snapshot_for_revision(receipt.revision.revision_id)
    authority = PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
        source, page_ids=(str(page_no),)
    ).authority()
    room_authority = build_source_room_face_authority(authority)
    selectors = authority.selectors_for_authenticated_viewports(
        document_id=receipt.revision.document_id,
        revision_id=receipt.revision.revision_id,
        source_sha256=sha, snapshot_id=snapshot.snapshot.snapshot_id,
        page_id=str(page_no), view_type="floor_finish_plan",
    )
    scopes = []
    for selector in selectors:
        wall = authority.resolve_scope(selector)
        scope = _freeze_scope(
            wall, audit_source_room_face_owned_witnesses(wall)
        )
        scopes.append(scope)
    scopes.sort(key=lambda x: x["decision_scope_id"])
    return {
        "source_sha256": sha,
        "revision_id": receipt.revision.revision_id,
        "snapshot_id": snapshot.snapshot.snapshot_id,
        "scopes": scopes,
        "preflight_drawing_receipt": preflight_receipt,
        "source_snapshot_unchanged": (
            source.published_snapshot_for_revision(receipt.revision.revision_id)
            == snapshot
        ),
        "shadow_source_room_authority_not_used_for_promotion": (
            room_authority is not None
        ),
    }


def first_difference(left, right, path="$"):
    """Exact deterministic first discrepancy, no float tolerance or matching."""
    if type(left) is not type(right):
        return {"path": path, "left": str(type(left)), "right": str(type(right))}
    if isinstance(left, dict):
        keys = sorted(set(left) | set(right))
        for key in keys:
            if key not in left or key not in right:
                return {"path": f"{path}.{key}", "reason": "missing_key"}
            result = first_difference(left[key], right[key], f"{path}.{key}")
            if result is not None:
                return result
        return None
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return {"path": path, "left_length": len(left), "right_length": len(right)}
        for idx, (a, b) in enumerate(zip(left, right)):
            result = first_difference(a, b, f"{path}[{idx}]")
            if result is not None:
                return result
        return None
    if left != right:
        return {"path": path, "left": str(left)[:200], "right": str(right)[:200]}
    return None


def compare_source_read_order(pdf_bytes: bytes, *, page_no: int) -> dict:
    baseline = capture_original_source(pdf_bytes, page_no=page_no, preflight=False)
    after_read = capture_original_source(pdf_bytes, page_no=page_no, preflight=True)
    repeat = capture_original_source(pdf_bytes, page_no=page_no, preflight=False)
    fields = ("source_sha256", "revision_id", "snapshot_id", "scopes")
    first = {k: baseline[k] for k in fields}
    second = {k: after_read[k] for k in fields}
    third = {k: repeat[k] for k in fields}
    ab = first_difference(first, second)
    aa = first_difference(first, third)
    def summary(value):
        return {
            "source_sha256": value["source_sha256"],
            "revision_id": value["revision_id"],
            "snapshot_id": value["snapshot_id"],
            "source_snapshot_unchanged": value["source_snapshot_unchanged"],
            "preflight_drawing_receipt": value["preflight_drawing_receipt"],
            "scope_ids": [x["decision_scope_id"] for x in value["scopes"]],
            "w4_wall_counts": [len(x["walls"]) for x in value["scopes"]],
            "face_counts": [len(x["shadow_faces"]) for x in value["scopes"]],
            "w4_scope_digests": [_digest(x) for x in value["scopes"]],
        }
    return {
        "source_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "baseline": summary(baseline),
        "with_preflight_native_pdf_read": summary(after_read),
        "repeat_baseline": summary(repeat),
        "preflight_vs_baseline_first_exact_difference": ab,
        "repeat_baseline_first_exact_difference": aa,
        "source_authority_stable_after_diagnostic_read": ab is None and aa is None,
        "physical_room_or_material_granted": False,
        "new_commercial_quantities": [],
        "frozen_benchmark_scored": False,
        "diagnostic_only": True,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--page", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    original = args.pdf.read_bytes()
    if hashlib.sha256(original).hexdigest() != args.sha:
        raise ValueError("original_pdf_sha_mismatch")
    result = compare_source_read_order(original, page_no=args.page)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("GPT2_SOURCE_PREFLIGHT_READ_ORDER", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
