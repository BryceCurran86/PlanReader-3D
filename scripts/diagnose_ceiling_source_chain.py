#!/usr/bin/env python3
"""Diagnostic-only trace of the source-owned ceiling chain on one source page.

This script is generic: the caller supplies a PDF path and one source page.
It never reads benchmark expected quantities, mappings, tolerances, or scores.

It reports:
- source integrity and visibility ingestion
- source-owned physical wall scope
- source-authenticated room faces
- explicit ceiling-finish text candidates and unique room ownership
- producer-owned physical graphic-scale evidence

It does not emit a production prediction or commercial quantity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from pb_ceiling_lining_finish_evidence import (
    collect_unscoped_ceiling_finish_candidates,
)
from pb_ceiling_lining_scope_binder import (
    build_owned_source_room_face_index,
    resolve_ceiling_finish_scope_proofs,
)
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_scale_authority import (
    PhysicalScaleProducer,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    assign_bbox_to_viewport,
    segment_page_viewports,
)


def _status(value: Any) -> str:
    return str(getattr(value, "value", value))


def _viewport_status(value: str) -> ViewportResolutionStatus:
    if value == ViewportSegmentationStatus.RESOLVED.value:
        return ViewportResolutionStatus.RESOLVED
    if value == ViewportSegmentationStatus.DERIVED.value:
        return ViewportResolutionStatus.DERIVED
    if value == ViewportSegmentationStatus.AMBIGUOUS.value:
        return ViewportResolutionStatus.AMBIGUOUS
    return ViewportResolutionStatus.UNSUPPORTED


def _finish_geometry(page: fitz.Page, atoms) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for atom in atoms:
        try:
            rects = page.search_for(atom.raw_text)
        except Exception:
            rects = ()
        if len(rects) != 1:
            continue
        rect = rects[0]
        rows.append(
            {
                "raw_text": atom.raw_text,
                "bbox": (
                    float(rect.x0),
                    float(rect.y0),
                    float(rect.x1),
                    float(rect.y1),
                ),
            }
        )
    return tuple(rows)


def run(pdf_path: Path, *, page_no: int, expected_sha256: str | None, document_id: str):
    payload = pdf_path.read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if expected_sha256 and actual_sha != expected_sha256.lower():
        raise SystemExit(
            f"SHA mismatch: expected {expected_sha256.lower()} got {actual_sha}"
        )

    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        if page_no < 1 or page_no > pdf.page_count:
            raise SystemExit(f"page {page_no} outside 1..{pdf.page_count}")
        page = pdf.load_page(page_no - 1)
        page_text = page.get_text("text")
        viewports = segment_page_viewports(page, page_number=page_no)
        viewport_rows = [
            {
                "view_id": item.view_id,
                "view_type": item.view_type,
                "label": item.label,
                "status": item.status,
                "bounding_box": item.bounding_box,
                "scale_raw": item.scale_raw,
                "scale_denominator": item.scale_denominator,
                "scale_conflict": item.scale_conflict,
                "notes": list(item.notes),
            }
            for item in viewports
        ]
        ceiling_lines = tuple(
            line.strip()
            for line in page_text.splitlines()
            if "ceiling" in line.casefold()
        )[:50]
    finally:
        pdf.close()

    source = SourceVisibilityProducer(
        producer_method="diagnose-ceiling-source-chain",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=str(pdf_path),
    )

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=(str(page_no),),
    ).authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page_no),
        decision_scope_id=f"wall-source:page-{page_no}",
    )
    wall_result = wall_authority.resolve_scope(wall_selector)

    room_authority = build_source_room_face_authority(wall_authority)
    room_selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page_no),
        decision_scope_id=f"wall-source:page-{page_no}",
    )
    room_result = room_authority.resolve_scope(room_selector)

    # First collect semantics without geometry, then attach geometry only where
    # the exact source text has one unique native search result.
    unscoped = collect_unscoped_ceiling_finish_candidates(
        page_text=page_text,
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        page_id=str(page_no),
        page_no=page_no,
        viewport_id=None,
        text_geometry=None,
        method="native_pdf_text",
    )
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(page_no - 1)
        geometry = _finish_geometry(page, unscoped)
    finally:
        pdf.close()

    # Recollect per independently resolved viewport so ownership is not
    # caller-injected. A candidate is retained for scope proof only when its
    # bbox falls in exactly one segmented viewport.
    scoped_candidates = []
    proof_rows = []
    document_ids = set()
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(page_no - 1)
        for atom in unscoped:
            matching_geometry = [
                item for item in geometry if item["raw_text"] == atom.raw_text
            ]
            if len(matching_geometry) != 1:
                proof_rows.append(
                    {
                        "finish_text": atom.raw_text,
                        "status": "bbox_unresolved",
                    }
                )
                continue
            bbox = matching_geometry[0]["bbox"]
            assigned = assign_bbox_to_viewport(bbox, viewports, allow_derived=True)
            if assigned is None or assigned.bounding_box is None:
                proof_rows.append(
                    {
                        "finish_text": atom.raw_text,
                        "bbox": bbox,
                        "status": "viewport_ambiguous_or_unresolved",
                    }
                )
                continue

            candidates = collect_unscoped_ceiling_finish_candidates(
                page_text=atom.raw_text,
                document_id=published.revision.document_id,
                source_sha256=published.revision.source_sha256,
                revision_id=published.revision.revision_id,
                page_id=str(page_no),
                page_no=page_no,
                viewport_id=assigned.view_id,
                text_geometry=(
                    {
                        "raw_text": atom.raw_text,
                        "bbox": bbox,
                    },
                ),
                method="native_pdf_text",
            )
            if len(candidates) != 1:
                proof_rows.append(
                    {
                        "finish_text": atom.raw_text,
                        "bbox": bbox,
                        "viewport_id": assigned.view_id,
                        "status": "candidate_recollection_failed",
                    }
                )
                continue
            candidate = candidates[0]
            scoped_candidates.append(candidate)
            document_ids.add(candidate.evidence_id)

            context = ProviderContext(
                run_id="diagnostic-ceiling-source-chain",
                workspace_id="diagnostic",
                project_id="diagnostic",
                document_id=published.revision.document_id,
                source_sha256=published.revision.source_sha256,
                revision_id=published.revision.revision_id,
                current_revision_id=published.revision.revision_id,
                selected_pages=(page_no - 1,),
                owned_viewport_ids=(assigned.view_id,),
                evidence_snapshot_id=published.snapshot.snapshot_id,
                owned_page_numbers=(page_no,),
                viewport_page_ownership=((assigned.view_id, page_no),),
            )
            viewport = ViewportEvidence(
                viewport_id=assigned.view_id,
                document_id=published.revision.document_id,
                page_id=str(page_no),
                bbox=tuple(float(value) for value in assigned.bounding_box),
                view_type=assigned.view_type,
                status=_viewport_status(assigned.status),
                evidence_ids=(candidate.evidence_id,),
                confidence=float(assigned.confidence),
            )
            document = DocumentEvidence(
                document_id=published.revision.document_id,
                source_sha256=published.revision.source_sha256,
                page_count=int(published.revision.page_count),
                page_ids=(),
                evidence_ids=(candidate.evidence_id,),
                producer="diagnose-ceiling-source-chain",
                producer_version="1.0",
            )
            room_index = build_owned_source_room_face_index(
                room_face_authority=room_authority,
                selector=room_selector,
                context=context,
                viewport=viewport,
            )
            proofs = resolve_ceiling_finish_scope_proofs(
                candidates=(candidate,),
                room_index=room_index,
                document=document,
                viewport=viewport,
            )
            proof_rows.append(
                {
                    "finish_text": candidate.raw_text,
                    "finish_evidence_id": candidate.evidence_id,
                    "bbox": candidate.bbox,
                    "viewport_id": assigned.view_id,
                    "viewport_status": assigned.status,
                    "room_index_resolved": bool(
                        room_index is not None and room_index.is_producer_owned
                    ),
                    "proof_count": len(proofs),
                    "room_entity_ids": [
                        proof.room_entity_id for proof in proofs
                    ],
                    "status": (
                        "unique_room_bound"
                        if len(proofs) == 1
                        else "room_scope_unresolved"
                    ),
                }
            )
    finally:
        pdf.close()

    scale_producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    scale_rows = []
    resolved_viewports = [
        item
        for item in viewports
        if item.status == ViewportSegmentationStatus.RESOLVED.value
        and item.bounding_box is not None
    ]
    if resolved_viewports:
        scale_viewport_ids = [item.view_id for item in resolved_viewports]
    else:
        scale_viewport_ids = [None]

    for viewport_id in scale_viewport_ids:
        selector = PhysicalScaleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=str(page_no),
            viewport_id=viewport_id,
        )
        result = scale_producer.publish_scope(selector)
        row = {
            "viewport_id": viewport_id,
            "status": _status(result.status),
            "reason_codes": list(result.reason_codes),
        }
        if result.evidence is not None:
            row["evidence"] = {
                "record_id": result.evidence.record_id,
                "source_kind": result.evidence.source_kind,
                "source_span_pt": result.evidence.source_span_pt,
                "physical_span_mm": result.evidence.physical_span_mm,
                "points_per_mm": result.evidence.points_per_mm,
                "mm_per_point": result.evidence.mm_per_point,
            }
        scale_rows.append(row)

    wall_ok = (
        wall_result.status is EvidenceResolutionStatus.CORROBORATED
        and wall_result.scope_complete
        and bool(wall_result.records)
    )
    room_ok = (
        room_result.status is EvidenceResolutionStatus.CORROBORATED
        and room_result.scope_complete
        and bool(room_result.records)
    )
    finish_ok = bool(unscoped)
    room_finish_ok = any(row.get("status") == "unique_room_bound" for row in proof_rows)
    scale_ok = any(row["status"] == EvidenceResolutionStatus.CORROBORATED.value for row in scale_rows)

    if not wall_ok:
        next_blocker = "physical_wall_scope"
    elif not room_ok:
        next_blocker = "source_room_faces"
    elif not finish_ok:
        next_blocker = "explicit_ceiling_finish_evidence"
    elif not room_finish_ok:
        next_blocker = "finish_to_room_scope_binding"
    elif not scale_ok:
        next_blocker = "producer_owned_physical_scale"
    else:
        next_blocker = "physical_scale_to_existing_room_area_calibration_bridge"

    report = {
        "source": {
            "document_id": published.revision.document_id,
            "sha256": actual_sha,
            "page_count": int(published.revision.page_count),
            "diagnostic_page": page_no,
            "decoded_pages": list(published.coverage.decoded_pages),
        },
        "page": {
            "ceiling_lines": list(ceiling_lines),
            "viewports": viewport_rows,
        },
        "physical_wall_scope": {
            "status": _status(wall_result.status),
            "scope_complete": bool(wall_result.scope_complete),
            "record_count": len(wall_result.records),
            "reason_codes": list(wall_result.reason_codes),
        },
        "source_room_faces": {
            "status": _status(room_result.status),
            "scope_complete": bool(room_result.scope_complete),
            "record_count": len(room_result.records),
            "reason_codes": list(room_result.reason_codes),
            "faces": [
                {
                    "face_id": record.face_id,
                    "area_page_pts2": record.area_page_pts2,
                    "bounding_wall_count": len(record.bounding_wall_ids),
                }
                for record in room_result.records
            ],
        },
        "ceiling_finish_candidates": {
            "semantic_count": len(unscoped),
            "texts": [atom.raw_text for atom in unscoped],
            "geometry_count": len(geometry),
            "scope_proofs": proof_rows,
        },
        "physical_scale": scale_rows,
        "summary": {
            "wall_scope_ready": wall_ok,
            "room_faces_ready": room_ok,
            "explicit_finish_ready": finish_ok,
            "finish_room_scope_ready": room_finish_ok,
            "physical_scale_ready": scale_ok,
            "next_blocker": next_blocker,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--sha256", default="")
    parser.add_argument("--document-id", default="source-ceiling-diagnostic")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run(
        args.pdf,
        page_no=args.page,
        expected_sha256=args.sha256 or None,
        document_id=args.document_id,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
