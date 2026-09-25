"""Focused real-source wall-authority shadow for KSTVET Item 19B.

Diagnostic only. It materializes only the two authenticated viewports that own
Item 19B's source callouts (GROUND FLOOR PLAN and ELEVATION E-02), then reports
raw terminator hits and physical-wall equivalence normalization. It does not
publish quantities and does not alter text/OCR authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS,
    PhysicalWallCandidateSelector,
    _assemble_scope_result,
    _authenticated_viewports,
    _decision_scope_id,
    _segment_fully_inside_bbox,
    _segment_intersects_bbox,
    _segment_is_authenticated_vector_frame_edge,
    _segment_lies_on_bbox_edge,
    _source_page_segments,
    _viewport_decision_scope_id,
    _viewport_sibling_set_fingerprint,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_wall_finish_face_binding_authority import (
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _segment_intersects_bbox as _geometry_intersects_bbox,
    _viewport_owned_lines,
)
from pb_wall_room_topology_stage_a import is_structural_candidate_segment

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"
TARGET_SEQUENCE_RANGES = {
    "external_e02": (10061, 10065),
    "internal_ground_plan": (10070, 10078),
}


def _callouts(source, published):
    authority = source.text_integrity_authority()
    rows = []
    for target, (seq_start, seq_end) in TARGET_SEQUENCE_RANGES.items():
        words = []
        for observation_id in published.text_observation_ids:
            resolved = authority.resolve_text(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            receipt = resolved.receipt
            if (
                receipt is None
                or receipt.page_id != PAGE_ID
                or receipt.sequence_number is None
                or not seq_start <= int(receipt.sequence_number) <= seq_end
            ):
                continue
            words.append((int(receipt.sequence_number), receipt))
        words.sort(key=lambda item: item[0])
        if not words:
            continue
        boxes = [tuple(float(v) for v in receipt.geometry) for _, receipt in words]
        heights = sorted(max(0.1, box[3] - box[1]) for box in boxes)
        rows.append(
            {
                "target": target,
                "text": " ".join(str(receipt.raw_text or "") for _, receipt in words),
                "bbox": (
                    min(box[0] for box in boxes),
                    min(box[1] for box in boxes),
                    max(box[2] for box in boxes),
                    max(box[3] for box in boxes),
                ),
                "text_height": heights[len(heights) // 2],
            }
        )
    return rows


def _scope_for_viewport(
    *,
    source,
    published,
    payload,
    page_segments,
    page_width,
    page_height,
    all_viewports,
    eligible,
    viewport,
):
    sibling_fingerprint = _viewport_sibling_set_fingerprint(all_viewports)
    scope_id = _viewport_decision_scope_id(
        published=published,
        page_id=PAGE_ID,
        viewport=viewport,
        sibling_set_fingerprint=sibling_fingerprint,
    )
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=PAGE_ID,
        decision_scope_id=scope_id,
    )
    owned = []
    owned_observation_ids = []
    boundary_observation_ids = []
    ambiguous_observation_ids = []
    pre_boundary_reasons = []

    for segment in page_segments:
        observation_id = str(segment.get("source_observation_id") or "")
        owners = [
            other
            for other in eligible
            if other.bounding_box is not None
            and _segment_fully_inside_bbox(segment, other.bounding_box)
        ]
        target_owned = any(other.view_id == viewport.view_id for other in owners)
        structural, _ = is_structural_candidate_segment(segment)

        if (
            target_owned
            and len(owners) == 1
            and not _segment_lies_on_bbox_edge(segment, viewport.bounding_box)
        ):
            scoped = dict(segment)
            scoped["viewport_id"] = scope_id
            owned.append(scoped)
            if observation_id:
                owned_observation_ids.append(observation_id)
            continue

        if target_owned and _segment_is_authenticated_vector_frame_edge(
            segment, viewport=viewport
        ):
            continue

        if target_owned and (
            len(owners) > 1
            or _segment_lies_on_bbox_edge(segment, viewport.bounding_box)
        ):
            if structural:
                pre_boundary_reasons.append(
                    PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS
                )
                if observation_id:
                    ambiguous_observation_ids.append(observation_id)
            continue

        if _segment_intersects_bbox(segment, viewport.bounding_box) and structural:
            pre_boundary_reasons.append(
                PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY
            )
            if observation_id:
                boundary_observation_ids.append(observation_id)

    return _assemble_scope_result(
        source_producer=source,
        published=published,
        page_id=PAGE_ID,
        selector=selector,
        segments=owned,
        source_observation_ids=owned_observation_ids,
        page_width=page_width,
        page_height=page_height,
        source_bytes=payload,
        viewport=viewport,
        sibling_set_fingerprint=sibling_fingerprint,
        pre_boundary_reasons=pre_boundary_reasons,
        scope_boundary_observation_ids=boundary_observation_ids,
        ambiguous_source_observation_ids=ambiguous_observation_ids,
    )


def run(pdf_path: Path) -> dict:
    payload = pdf_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(
            f"KSTVET source SHA mismatch: expected {EXPECTED_SHA256}, got {actual}"
        )

    source = SourceVisibilityProducer(
        producer_method="item19b-callout-wall-fast-shadow",
        producer_version="1.0.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-callout-wall-fast-shadow",
        source_bytes=payload,
        source_locator=f"sha256://{EXPECTED_SHA256}",
        page_ids=(PAGE_ID,),
    )
    page_scope_id = _decision_scope_id(PAGE_ID)
    page_segments, _, page_width, page_height = _source_page_segments(
        source_producer=source,
        published=published,
        source_bytes=payload,
        page_id=PAGE_ID,
        decision_scope_id=page_scope_id,
    )

    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        page = pdf.load_page(int(PAGE_ID) - 1)
        authenticated = _authenticated_viewports(page, page_number=int(PAGE_ID))
        if authenticated is None:
            raise RuntimeError("authenticated viewport authority unavailable")
        all_viewports, eligible = authenticated
        callouts = _callouts(source, published)
        visible_lines = _page_visible_lines(source, published, PAGE_ID)
        native = extract_native_page(page)
        native_by_id = {
            str(segment.get("id")): segment
            for segment in native.get("segments", ())
            if str(segment.get("id") or "")
        }

        scope_by_viewport = {}
        out = []
        seen = set()
        for callout in callouts:
            viewport = assign_bbox_to_viewport(
                callout["bbox"],
                eligible,
                allow_derived=True,
            )
            if viewport is None or viewport.bounding_box is None:
                out.append(
                    {
                        "target": callout["target"],
                        "status": "viewport_unresolved",
                    }
                )
                continue
            if viewport.view_id not in scope_by_viewport:
                scope_by_viewport[viewport.view_id] = _scope_for_viewport(
                    source=source,
                    published=published,
                    payload=payload,
                    page_segments=page_segments,
                    page_width=page_width,
                    page_height=page_height,
                    all_viewports=all_viewports,
                    eligible=eligible,
                    viewport=viewport,
                )
            scope = scope_by_viewport[viewport.view_id]
            # Use the same exact, fail-closed viewport ownership rule as the
            # production finish binder. Wall targeting below remains confined
            # to producer-owned physical-wall records.
            owned_lines = _viewport_owned_lines(
                visible_lines,
                viewport,
                eligible,
            )
            terms = tuple(
                term
                for term in _filled_terminators(page, callout["text_height"])
                if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
            )
            leader_paths = _leader_paths(
                callout["bbox"],
                owned_lines,
                terms,
            )
            emitted_for_callout = 0
            for leader_ids, term in leader_paths:
                emitted_for_callout += 1
                raw_hits = sorted(
                    {
                        line.raw_id
                        for line in owned_lines
                        if _geometry_intersects_bbox(line.geometry, term.bbox)
                    }
                )
                matching = [
                    record
                    for record in scope.records
                    if set(raw_hits)
                    & set(record.physical_identity.source_primitive_ids)
                ]
                representative_for = {}
                for group in tuple(
                    getattr(scope.equivalence, "equivalence_groups", ()) or ()
                ):
                    representative = sorted(group)[0]
                    for wall_id in group:
                        representative_for[wall_id] = representative
                normalized = sorted(
                    {
                        representative_for.get(
                            record.wall_candidate_id,
                            record.wall_candidate_id,
                        )
                        for record in matching
                    }
                )
                signature = (
                    callout["target"],
                    term.primitive_id,
                    tuple(normalized),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                raw_details = []
                for raw_id in raw_hits:
                    segment = native_by_id.get(raw_id)
                    if segment is None:
                        continue
                    keep, exclusion_reasons = is_structural_candidate_segment(segment)
                    raw_details.append(
                        {
                            "id": raw_id,
                            "layer": segment.get("layer"),
                            "path_index": segment.get("path_index"),
                            "geometry": [
                                segment.get("x1"),
                                segment.get("y1"),
                                segment.get("x2"),
                                segment.get("y2"),
                            ],
                            "structural_candidate": keep,
                            "exclusion_reasons": exclusion_reasons,
                        }
                    )
                out.append(
                    {
                        "target": callout["target"],
                        "text": callout["text"],
                        "viewport_id": viewport.view_id,
                        "viewport_label": viewport.label,
                        "scope_complete": scope.scope_complete,
                        "scope_reason_codes": list(scope.reason_codes),
                        "wall_candidate_count": len(scope.records),
                        "terminator_id": term.primitive_id,
                        "leader_path_ids": list(leader_ids),
                        "raw_source_primitive_hits": raw_hits,
                        "raw_hit_details": raw_details,
                        "raw_wall_owner_ids": sorted(
                            record.wall_candidate_id for record in matching
                        ),
                        "normalized_wall_owner_ids": normalized,
                        "normalized_owner_count": len(normalized),
                        "equivalence_groups_touching_hit": [
                            list(group)
                            for group in (
                                getattr(scope.equivalence, "equivalence_groups", ()) or ()
                            )
                            if set(group)
                            & {record.wall_candidate_id for record in matching}
                        ],
                        "owner_source_primitives": {
                            record.wall_candidate_id: list(
                                record.physical_identity.source_primitive_ids
                            )
                            for record in matching
                        },
                        "owner_path_fingerprints": {
                            record.wall_candidate_id: [
                                [float(point[0]), float(point[1])]
                                for point in (
                                    record.physical_identity.path_fingerprint or ()
                                )
                            ]
                            for record in matching
                        },
                        "owner_centerlines": {
                            record.wall_candidate_id: [
                                [float(point[0]), float(point[1])]
                                for point in record.wall_candidate.centerline_pts
                            ]
                            for record in matching
                        },
                        "pair_classifications_touching_hit": [
                            list(row)
                            for row in (
                                getattr(
                                    scope.equivalence,
                                    "pair_classifications",
                                    (),
                                )
                                or ()
                            )
                            if row[0]
                            in {record.wall_candidate_id for record in matching}
                            and row[1]
                            in {record.wall_candidate_id for record in matching}
                        ],
                        "owner_details": {
                            record.wall_candidate_id: {
                                "representation": record.wall_candidate.representation,
                                "centerline_pts": [
                                    [float(point[0]), float(point[1])]
                                    for point in record.wall_candidate.centerline_pts
                                ],
                                "face_a_segment_ids": list(
                                    record.wall_candidate.face_a_segment_ids
                                ),
                                "face_b_segment_ids": list(
                                    record.wall_candidate.face_b_segment_ids or ()
                                ),
                                "path_fingerprint": [
                                    [float(point[0]), float(point[1])]
                                    for point in (
                                        record.physical_identity.path_fingerprint or ()
                                    )
                                ],
                                "comparison_mode": record.physical_identity.comparison_mode,
                            }
                            for record in matching
                        },
                    }
                )
            if emitted_for_callout == 0:
                out.append(
                    {
                        "target": callout["target"],
                        "text": callout["text"],
                        "callout_bbox": list(callout["bbox"]),
                        "text_height": callout["text_height"],
                        "viewport_id": viewport.view_id,
                        "viewport_label": viewport.label,
                        "viewport_bbox": list(viewport.bounding_box),
                        "status": "no_leader_path",
                        "wall_candidate_count": len(scope.records),
                        "scope_complete": scope.scope_complete,
                        "scope_reason_codes": list(scope.reason_codes),
                        "normalized_owner_count": 0,
                        "viewport_owned_line_count": len(owned_lines),
                        "terminator_count": len(terms),
                        "terminators": [
                            {
                                "primitive_id": term.primitive_id,
                                "bbox": list(term.bbox),
                                "center": list(term.center),
                            }
                            for term in terms
                        ],
                        "near_callout_lines": [
                            {
                                "observation_id": line.observation_id,
                                "raw_id": line.raw_id,
                                "geometry": list(line.geometry),
                            }
                            for line in owned_lines
                            if _geometry_intersects_bbox(
                                line.geometry,
                                (
                                    callout["bbox"][0] - 40.0,
                                    callout["bbox"][1] - 40.0,
                                    callout["bbox"][2] + 40.0,
                                    callout["bbox"][3] + 40.0,
                                ),
                            )
                        ],
                    }
                )

        return {
            "page_id": PAGE_ID,
            "callouts": out,
            "scope_summaries": {
                viewport_id: {
                    "scope_complete": scope.scope_complete,
                    "reason_codes": list(scope.reason_codes),
                    "wall_candidate_count": len(scope.records),
                    "equivalence_group_count": len(
                        getattr(scope.equivalence, "equivalence_groups", ()) or ()
                    ),
                }
                for viewport_id, scope in scope_by_viewport.items()
            },
        }
    finally:
        pdf.close()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: item19b_kstvet_callout_wall_fast_shadow.py <canonical-kstvet.pdf>"
        )
    print(
        "ITEM19B_CALLOUT_WALL_FAST "
        + json.dumps(run(Path(sys.argv[1])), sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    main()
