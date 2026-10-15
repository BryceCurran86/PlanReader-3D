"""Independently re-prove original F07 siblings and compare with sealed W4 scope.

Opt-in source plan shadows DO NOT populate the ordinary F07 viewport cache.
This tool therefore performs a SECOND, INDEPENDENT producer-owned F07 replay on
the exact same source revision, then checks exact W4 scope ID parity. A second
diagnostic segmentation is never asserted to be the first W4 producer's
original in-memory view objects. No wall, room or quantity authority changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer, _authenticated_viewports_from_rows,
    _viewport_decision_scope_id, _viewport_sibling_set_fingerprint,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector, audit_source_room_face_owned_witnesses,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    segment_source_page_viewports, _producer_fingerprint_payload,
    segmented_viewport_producer_fingerprint, is_segment_page_viewports_product,
)
from pb_drawing_evidence_binding import DrawingViewType


def classify_independent_f07_siblings(*, viewports, published, page_no: int,
                                      original_w4_scope_ids: tuple[str, ...]):
    """Original source F07 producer records only; preserve ALL siblings."""
    originals = _authenticated_viewports_from_rows(viewports)
    if originals is None:
        return {
            "status": "independent_f07_producer_unavailable_or_unsealed",
            "all_source_owned_views": [],
            "original_w4_scope_id_parity_verified": False,
            "diagnostic_only": True,
        }
    all_views, eligible = originals
    siblings = _viewport_sibling_set_fingerprint(all_views)
    rows = []
    candidate_ids = []
    for view in sorted(all_views, key=lambda v: v.view_id):
        if not is_segment_page_viewports_product(view):
            raise ValueError("unsealed_independent_original_f07_view")
        proof = _producer_fingerprint_payload(view)
        accepted = any(x is view for x in eligible)
        plan_source_positive = bool(
            accepted and view.view_type in (
                DrawingViewType.FLOOR_PLAN.value,
                DrawingViewType.FLOOR_FINISH_PLAN.value,
            ) and (view.provenance or {}).get("source_owned_plan_view_proven") is True
        )
        derived_scope = (
            _viewport_decision_scope_id(
                published=published, page_id=str(page_no), viewport=view,
                sibling_set_fingerprint=siblings,
            )
            if plan_source_positive else None
        )
        if derived_scope is not None:
            candidate_ids.append(derived_scope)
        rows.append({
            "source_f07_view_id": view.view_id,
            "source_view_type": view.view_type,
            "source_sealed_f07_payload": proof,
            "individual_source_f07_fingerprint":
                segmented_viewport_producer_fingerprint(view),
            "source_view_producer_seal_verified": True,
            "producer_source_plan_eligible": plan_source_positive,
            "recomputed_source_plan_scope_candidate_only": derived_scope,
        })
    observed = sorted(original_w4_scope_ids)
    candidates = sorted(candidate_ids)
    unique = len(observed)==len(set(observed)) and len(candidates)==len(set(candidates))
    parity = bool(unique and observed and observed == candidates)
    return {
        "status": (
            "independent_source_f07_replay_exact_w4_scope_parity"
            if parity else "independent_source_f07_replay_w4_scope_conflict_or_unavailable"
        ),
        "sibling_source_fingerprint": siblings,
        "original_w4_scopes_from_first_producer": observed,
        "replayed_source_plan_scope_candidates": candidates,
        "all_original_f07_view_count": len(rows),
        "all_source_owned_views": rows,
        "original_w4_scope_id_parity_verified": parity,
        "room_or_wall_authority_granted": False,
        "diagnostic_only": True,
    }


def replay_original_source_f07_first_gate(source_bytes: bytes, *, page_no: int):
    if type(source_bytes) is not bytes or type(page_no) is not int or page_no < 1:
        raise ValueError("original_pdf_bytes_and_page_required")
    sha=hashlib.sha256(source_bytes).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1"
    )
    receipt=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://source-owned-original-plan-f07.pdf",
        page_ids=(str(page_no),),
    )
    original=source.published_snapshot_for_revision(receipt.revision.revision_id)
    if original is None or original.revision.source_sha256 != sha:
        raise ValueError("source_f07_original_revision_unavailable")
    walls=PhysicalWallCandidateProducer.from_source_owned_plan_view_shadow(
        source, page_ids=(str(page_no),)
    ).authority()
    faces=build_source_room_face_authority(walls)
    selectors=walls.selectors_for_authenticated_viewports(
        document_id=original.revision.document_id,
        revision_id=original.revision.revision_id,
        source_sha256=sha, snapshot_id=original.snapshot.snapshot_id,
        page_id=str(page_no), view_type="floor_finish_plan",
    )
    first = []
    for selector in selectors:
        wall=walls.resolve_scope(selector)
        face=faces.resolve_scope(SourceRoomFaceSelector(
            document_id=wall.document_id, revision_id=wall.revision_id,
            source_sha256=wall.source_sha256, snapshot_id=wall.snapshot_id,
            page_id=wall.page_id, decision_scope_id=wall.decision_scope_id,
        ))
        witnesses=audit_source_room_face_owned_witnesses(wall)
        first.append({
            "decision_scope_id":wall.decision_scope_id,
            "original_w4_candidate_count":len(wall.records),
            "original_w4_owned_shadow_face_count":len(witnesses),
            "original_authoritative_source_room_face_count":len(face.records),
            "original_w4_scope_complete":wall.scope_complete,
        })
    # A second independent source-owned re-segmentation, not an original
    # captured W4 producer internal! Any non-parity abstains.
    second=tuple(segment_source_page_viewports(
        source, revision_id=original.revision.revision_id,
        page_id=str(page_no), physical_plan_view_shadow=True,
    ))
    after=source.published_snapshot_for_revision(receipt.revision.revision_id)
    if after != original:
        raise RuntimeError("independent_f07_shadow_modified_original_source_snapshot")
    census=classify_independent_f07_siblings(
        viewports=second, published=original, page_no=page_no,
        original_w4_scope_ids=tuple(row["decision_scope_id"] for row in first),
    )
    return {
        "original_source_sha256":sha,
        "original_source_revision_id":original.revision.revision_id,
        "original_source_snapshot_id":original.snapshot.snapshot_id,
        "original_source_snapshot_unchanged":True,
        "source_f07_ownership_note":
            "independently_recomputed_source_F07_not_original_wall_in_memory_views",
        "first_original_w4_scopes":first,
        "independent_second_f07_sibling_source_replay":census,
        "new_physical_room_authority":False,
        "new_finish_occurrence":False,
        "new_customer_quantities":[],
        "frozen_benchmark_scored":False,
        "diagnostic_only":True,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--page", type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    source=args.pdf.read_bytes()
    if hashlib.sha256(source).hexdigest()!=args.sha:
        raise ValueError("original_source_sha_mismatch")
    result=replay_original_source_f07_first_gate(source,page_no=args.page)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    proof=result["independent_second_f07_sibling_source_replay"]
    print("GPT2_INDEPENDENT_F07_SOURCE_PARITY",json.dumps({
        "original_pdf_sha":result["original_source_sha256"],
        "first_w4_scope_count":len(result["first_original_w4_scopes"]),
        "sibling_view_count":proof.get("all_original_f07_view_count"),
        "exact_producer_scope_parity":proof["original_w4_scope_id_parity_verified"],
        "status":proof["status"],
        "new_customer_quantities":[],
    },sort_keys=True))


if __name__=="__main__":
    main()
