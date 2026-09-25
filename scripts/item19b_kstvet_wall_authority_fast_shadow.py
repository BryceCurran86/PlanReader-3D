"""Fast real-source wall-authority shadow for KSTVET Item 19B.

Diagnostic only. This script never reads benchmark quantities, expected values,
finish text, OCR, wall roles, or commercial outputs. It materializes exactly
one producer-authenticated FLOOR_PLAN viewport from the SHA-pinned source and
prints the native wall-candidate/equivalence provenance needed by #899.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

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
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import detect_wall_pairs, extract_native_page
from pb_wall_room_topology_stage_a import is_structural_candidate_segment

EXPECTED_SHA256 = "6856bfa739aa136dd8e0bf17cb25fd43d0d31c9c3dfe3252525454f09d8fa4dc"
PAGE_ID = "54"


def run(pdf_path: Path) -> dict:
    payload = pdf_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(
            f"KSTVET source SHA mismatch: expected {EXPECTED_SHA256}, got {actual}"
        )

    source = SourceVisibilityProducer(
        producer_method="item19b-wall-authority-fast-shadow",
        producer_version="1.0.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-wall-shadow",
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
        floor_plans = [
            viewport
            for viewport in eligible
            if str(getattr(viewport, "view_type", "")) == "floor_plan"
            and viewport.bounding_box is not None
        ]
        if len(floor_plans) != 1:
            raise RuntimeError(
                f"expected exactly one authenticated FLOOR_PLAN viewport, got {len(floor_plans)}"
            )
        viewport = floor_plans[0]
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

        scope = _assemble_scope_result(
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

        native = extract_native_page(page)
        by_raw_id = {
            str(segment.get("id")): segment
            for segment in native.get("segments", ())
            if str(segment.get("id") or "")
        }
        drawings = page.get_drawings() or []

        candidate_raw_ids = {
            raw_id
            for record in scope.records
            for raw_id in record.physical_identity.source_primitive_ids
        }
        pair_rows = detect_wall_pairs(
            [
                by_raw_id[raw_id]
                for raw_id in sorted(candidate_raw_ids)
                if raw_id in by_raw_id
            ],
            0.0,
        )

        candidate_rows = []
        for record in sorted(scope.records, key=lambda item: item.wall_candidate_id):
            primitives = []
            for raw_id in record.physical_identity.source_primitive_ids:
                segment = by_raw_id.get(raw_id)
                if segment is None:
                    primitives.append({"id": raw_id, "native": False})
                    continue
                path_index = segment.get("path_index")
                drawing = (
                    drawings[int(path_index)]
                    if path_index is not None
                    and 0 <= int(path_index) < len(drawings)
                    else None
                )
                primitives.append(
                    {
                        "id": raw_id,
                        "native": True,
                        "geometry": [
                            segment.get("x1"),
                            segment.get("y1"),
                            segment.get("x2"),
                            segment.get("y2"),
                        ],
                        "kind": segment.get("kind"),
                        "width": segment.get("width"),
                        "layer": segment.get("layer"),
                        "dashes": segment.get("dashes"),
                        "path_index": path_index,
                        "item_index": segment.get("item_index"),
                        "edge_index": segment.get("edge_index"),
                        "drawing_item_kinds": (
                            [str(item[0]) for item in drawing.get("items", ()) if item]
                            if drawing is not None
                            else []
                        ),
                        "drawing_rect": (
                            list(drawing.get("rect"))
                            if drawing is not None and drawing.get("rect") is not None
                            else None
                        ),
                    }
                )
            candidate_rows.append(
                {
                    "wall_candidate_id": record.wall_candidate_id,
                    "representation": record.wall_candidate.representation,
                    "path_fingerprint": [
                        list(point)
                        for point in (record.physical_identity.path_fingerprint or ())
                    ],
                    "source_primitives": primitives,
                }
            )

        return {
            "page_id": PAGE_ID,
            "viewport_id": viewport.view_id,
            "viewport_label": viewport.label,
            "viewport_bbox": list(viewport.bounding_box),
            "scope_complete": scope.scope_complete,
            "reason_codes": list(scope.reason_codes),
            "wall_candidate_count": len(scope.records),
            "equivalence_groups": [
                list(group)
                for group in (
                    getattr(scope.equivalence, "equivalence_groups", ()) or ()
                )
            ],
            "pair_classifications": [
                list(row)
                for row in (
                    getattr(scope.equivalence, "pair_classifications", ()) or ()
                )
            ],
            "candidate_rows": candidate_rows,
            "candidate_owned_double_line_pairs": pair_rows,
        }
    finally:
        pdf.close()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: item19b_kstvet_wall_authority_fast_shadow.py <canonical-kstvet.pdf>"
        )
    print(
        "ITEM19B_WALL_AUTHORITY_FAST "
        + json.dumps(run(Path(sys.argv[1])), sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    main()
