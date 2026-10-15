"""Original-source plan-plane receipt audit, with NO metric authority.

This bounded bridge operates on the same immutable PDF bytes as the actual
SourceVisibility -> canonical-room handoff.  Source page native coordinates,
producer segmented viewport membership, room face lineage and figured-axis
witness geometry are checked *together* before any future physical scale
authority can even be considered.  Spatial containment and a consistent ratio
are NOT proof that figured dimensions measure a particular room's floor.

Never use this shadow's candidate receipt to issue scale, PDF-scaled area,
QuantityEvidence, customer output, host/height/count or a benchmark identity.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
from typing import Mapping, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_scale_consistency_shadow import source_figured_scale_shadow
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    segment_source_page_viewports,
    validate_non_overlapping_viewports,
)


def _box(value: object) -> tuple[float, float, float, float] | None:
    if type(value) not in (tuple, list) or len(value) != 4:
        return None
    if any(type(v) not in (float, int) for v in value):
        return None
    b = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in b) or b[2] <= b[0] or b[3] <= b[1]:
        return None
    return b


def _contains(box: tuple[float, float, float, float], point: object) -> bool:
    return (
        type(point) in (tuple, list) and len(point) == 2
        and all(type(v) in (int, float) and math.isfinite(float(v)) for v in point)
        and box[0] <= float(point[0]) <= box[2]
        and box[1] <= float(point[1]) <= box[3]
    )


def _enclosed_source_axis(row: Mapping, axis: str, bbox: tuple[float, ...]) -> bool:
    points = row.get(f"{axis}_endpoints_pt")
    strokes = row.get(f"{axis}_witness_segments")
    ids = row.get(f"{axis}_source_witness_ids")
    if (
        type(row.get(f"{axis}_dimension_id")) is not str
        or not row[f"{axis}_dimension_id"]
        or type(points) not in (list, tuple)
        or len(points) != 2
        or type(strokes) not in (list, tuple)
        or len(strokes) < 2
        or type(ids) not in (list, tuple)
        or len(ids) < 2
        or len(ids) != len(set(ids))
        or any(type(x) is not str or not x for x in ids)
    ):
        return False
    if not all(_contains(bbox, point) for point in points):
        return False
    return all(
        type(segment) in (list, tuple)
        and len(segment) == 4
        and _contains(bbox, segment[:2])
        and _contains(bbox, segment[2:])
        for segment in strokes
    )


def original_figured_plan_plane_shadow(
    source_bytes: bytes,
    *,
    expected_source_sha256: str,
    page_index: int,
    rooms: Sequence[object],
    witness_audit: Mapping,
    source_visibility_producer: SourceVisibilityProducer | None = None,
    source_revision_id: str | None = None,
) -> dict:
    """Explain first source plane registration failure on exact original PDF.

    Room objects must be derived from the same live source+snapshot producer.
    This is not a scale producer and never returns a trusted metric conversion.
    """
    if type(source_bytes) is not bytes:
        raise TypeError("source_bytes must be immutable original PDF bytes")
    sha = hashlib.sha256(source_bytes).hexdigest()
    if sha != expected_source_sha256:
        raise ValueError("original source SHA conflict")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("invalid source page")
    if (source_visibility_producer is None) != (source_revision_id is None):
        raise TypeError("source producer and exact revision must be supplied together")
    if source_visibility_producer is not None:
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("actual source visibility producer required")
        if type(source_revision_id) is not str or not source_revision_id:
            raise ValueError("authenticated source revision required")
        published = source_visibility_producer.published_snapshot_for_revision(
            source_revision_id
        )
        if (
            published is None
            or published.revision.source_sha256 != sha
            or source_visibility_producer._producer.current_revision_id(
                published.revision.document_id
            ) != source_revision_id
            or source_visibility_producer._producer._store.source_bytes_by_revision.get(
                source_revision_id
            ) != source_bytes
            or page_index + 1 not in published.coverage.decoded_pages
        ):
            raise ValueError("foreign, stale, or incomplete producer source plan scope")
        # This existing source-owned F.07 boundary re-proves its complete
        # extent from the immutable producer, with no caller-supplied box.
        viewports = tuple(segment_source_page_viewports(
            source_visibility_producer,
            revision_id=source_revision_id, page_id=str(page_index + 1),
            physical_plan_view_shadow=True,
        ))
        if source_visibility_producer.published_snapshot_for_revision(
            source_revision_id
        ) != published:
            raise RuntimeError("source plan reader mutated published snapshot")
    else:
        published = None
        with fitz.open(stream=source_bytes, filetype="pdf") as doc:
            if page_index >= len(doc):
                raise ValueError("source page out of bounds")
            viewports = tuple(segment_page_viewports(
                doc[page_index], page_number=page_index + 1,
            ))
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        if page_index >= len(doc):
            raise ValueError("source page out of bounds")
        rotation = int(doc[page_index].rotation)
    no_overlap = validate_non_overlapping_viewports(viewports)
    candidates = []
    for v in viewports:
        bbox = _box(v.bounding_box)
        if (
            bbox is None
            or v.view_type != DrawingViewType.FLOOR_PLAN.value
            or not no_overlap
            or not (
                v.status == ViewportSegmentationStatus.RESOLVED.value
                or (
                    v.status == ViewportSegmentationStatus.DERIVED.value
                    and is_authoritative_derived_viewport(v)
                )
            )
        ):
            continue
        candidates.append((str(v.view_id), bbox))
    if len({v[0] for v in candidates}) != len(candidates):
        candidates = []
    consistent = source_figured_scale_shadow(witness_audit)
    source_axis_available = (
        consistent["first_unclosed_gate"]
        == "source_figured_scale_shadow_consistent_not_authority"
    )
    original_failed = witness_audit.get("failed_pair_samples", ()) if isinstance(witness_audit, Mapping) else ()
    rows = original_failed if type(original_failed) in (list, tuple) else ()
    def axis_count(axis: str, bbox: tuple[float, ...]) -> int:
        return len({
            item[f"{axis}_dimension_id"]
            for item in rows
            if isinstance(item, Mapping) and _enclosed_source_axis(item, axis, bbox)
        })
    room_counts = Counter(str(getattr(r, "physical_room_id", "")) for r in rooms)
    output = []
    for room in rooms:
        room_id = str(getattr(room, "physical_room_id", "") or "")
        page_id = str(getattr(room, "page_id", "") or "")
        original_id = str(getattr(room, "viewport_id", "") or "")
        polygons = getattr(room, "polygon_pdf_pts", None)
        valid_room = (
            room_id and room_counts[room_id] == 1
            and page_id == str(page_index + 1)
            and str(getattr(room, "source_sha256", "") or "").lower() == sha
            and bool(getattr(room, "source_room_face_record_id", None))
            and bool(getattr(room, "room_label_binding_record_id", None))
            and bool(getattr(room, "room_label_evidence_ids", ()))
            and bool(getattr(room, "geometry_complete", False))
            and type(polygons) in (tuple, list)
            and len(polygons) >= 3
        )
        enclosing = [
            (view_id, bbox) for view_id, bbox in candidates
            if valid_room and all(_contains(bbox, p) for p in polygons)
        ]
        producer_room_snapshot_owned = (
            published is None or (
                str(getattr(room, "document_id", "") or "")
                    == published.revision.document_id
                and str(getattr(room, "revision_id", "") or "")
                    == published.revision.revision_id
                and str(getattr(room, "snapshot_id", "") or "")
                    == published.snapshot.snapshot_id
            )
        )
        full_ownership = (
            len(enclosing) == 1
            and original_id == enclosing[0][0]
            and producer_room_snapshot_owned
        )
        two_axis_sources = (
            full_ownership and source_axis_available
            and axis_count("horizontal", enclosing[0][1]) >= 2
            and axis_count("vertical", enclosing[0][1]) >= 2
        )
        first = (
            "physical_room_source_receipts_incomplete"
            if not valid_room else
            "unique_original_source_floor_plan_viewport_unavailable"
            if len(enclosing) != 1 else
            "physical_room_source_revision_or_snapshot_unmatched"
            if not producer_room_snapshot_owned else
            "physical_room_source_viewport_identity_unresolved"
            if not full_ownership else
            "two_source_figured_axis_systems_not_within_owned_viewport"
            if not two_axis_sources else
            "room_specific_source_wall_scale_registration_unproven"
        )
        output.append({
            "physical_room_id": room_id,
            "source_face_id": str(getattr(room, "source_room_face_record_id", "") or ""),
            "original_room_viewport_id": original_id or None,
            "source_room_snapshot_owned_by_this_view_producer": bool(
                producer_room_snapshot_owned
            ),
            "containing_original_viewport_ids_not_authority": sorted(v[0] for v in enclosing),
            "source_own_viewport_and_axes_candidate": bool(two_axis_sources),
            "first_unclosed_gate": first,
            "metric_room_area_m2": None,
            "signed_quantity_id": None,
        })
    return {
        "diagnostic_only": True,
        "original_source_sha256": sha,
        "source_page_id": str(page_index + 1),
        "source_plan_view_proof_mode": (
            "producer_source_owned" if published is not None else "legacy_page_only"
        ),
        "source_plan_view_snapshot_id": (
            published.snapshot.snapshot_id if published is not None else None
        ),
        "original_page_rotation": rotation,
        "source_viewport_nonoverlap": bool(no_overlap),
        "source_proven_floor_plan_viewports": [
            {"viewport_id": v, "native_bbox_pdf_points": list(b)}
            for v, b in candidates
        ],
        "original_figured_axis_consistency": consistent["first_unclosed_gate"],
        "original_figured_dimensions_consistent": source_axis_available,
        "per_room": output,
        "first_unclosed_gate_counts": dict(sorted(Counter(x["first_unclosed_gate"] for x in output).items())),
        "physical_scale_authority_granted": False,
        "room_metric_area_authority_granted": False,
        "published_quantities": [],
        "commercial_projection_allowed": False,
    }


__all__ = ["original_figured_plan_plane_shadow"]
