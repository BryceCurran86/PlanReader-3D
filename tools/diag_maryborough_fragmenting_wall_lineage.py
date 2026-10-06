from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGETS = {
    "POS COUNTER",
    "FOOD SERVICE",
    "WASH UP",
    "TRUCK DRIVER LOUNGE",
    "DRY STORE",
}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _bbox(record) -> list[float]:
    pts = tuple(record.polygon_pdf_pts)
    return [
        min(float(p[0]) for p in pts),
        min(float(p[1]) for p in pts),
        max(float(p[0]) for p in pts),
        max(float(p[1]) for p in pts),
    ]


def main() -> int:
    path = SOURCE
    source = SourceVisibilityProducer(
        producer_method="gpt2-fragmenting-wall-lineage",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-fragmenting-wall-lineage",
        source_bytes=path.read_bytes(),
        source_locator="memory://maryborough.pdf",
        page_ids=("7",),
    )
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("7",),
    )

    vp_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=("7",),
    )
    vp_authority = vp_producer.authority()
    current = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None
    selectors = vp_authority.selectors_for_authenticated_viewports(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id="7",
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    assert len(selectors) == 1
    selector = selectors[0]
    wall_scope = vp_authority.resolve_scope(selector)
    wall_by_id = {
        str(record.wall_candidate_id): record
        for record in wall_scope.records
    }

    room_auth = build_source_room_face_authority(vp_authority)
    room_scope = room_auth.resolve_scope(
        SourceRoomFaceSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )
    )
    room_by_face = {str(record.face_id): record for record in room_scope.records}

    doc = fitz.open(path)
    try:
        native = extract_native_page(doc[6])
    finally:
        doc.close()
    native_segments = {
        str(segment.get("id")): segment
        for segment in native.get("segments") or ()
    }

    text_auth = source.text_integrity_authority()
    grouped = defaultdict(list)
    for observation_id in current.text_observation_ids:
        result = text_auth.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if (
            receipt is None
            or str(receipt.page_id) != "7"
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        grouped[
            (
                str(receipt.source_partition_id),
                int(receipt.block_no),
                int(receipt.line_no),
            )
        ].append((observation_id, result, receipt))

    def wall_payload(wall_id: str) -> dict:
        record = wall_by_id.get(wall_id)
        if record is None:
            return {"wall_candidate_id": wall_id, "record_unavailable": True}
        candidate = record.wall_candidate
        source_result = source._producer.authority().resolve(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=record.source_observation_id,
            )
        )
        observation = source_result.observation
        primitive_ref = (
            "" if observation is None else str(observation.source_primitive_ref)
        )
        segment_id = primitive_ref.removeprefix("segment:")
        segment = native_segments.get(segment_id)
        return {
            "wall_candidate_id": wall_id,
            "record_source_observation_id": record.source_observation_id,
            "source_primitive_ref": primitive_ref,
            "candidate_representation": candidate.representation,
            "candidate_reason_codes": list(candidate.reason_codes),
            "centerline_pts": [list(p) for p in candidate.centerline_pts],
            "face_a_segment_ids": list(candidate.face_a_segment_ids),
            "face_b_segment_ids": (
                None
                if candidate.face_b_segment_ids is None
                else list(candidate.face_b_segment_ids)
            ),
            "native_segment": (
                None
                if segment is None
                else {
                    key: segment.get(key)
                    for key in (
                        "id",
                        "kind",
                        "x1",
                        "y1",
                        "x2",
                        "y2",
                        "width",
                        "stroke",
                        "fill",
                        "layer",
                        "dashes",
                    )
                }
            ),
        }

    rows = []
    for key, items in sorted(grouped.items()):
        items = sorted(items, key=lambda item: int(item[2].word_no))
        line = _norm(
            " ".join(
                str(item[2].raw_text or "").strip()
                for item in items
                if str(item[2].raw_text or "").strip()
            )
        )
        if line not in TARGETS:
            continue

        words = []
        face_ids = []
        for _oid, result, receipt in items:
            geom = tuple(float(v) for v in receipt.geometry)
            centre = ((geom[0] + geom[2]) / 2.0, (geom[1] + geom[3]) / 2.0)
            matches = [
                record
                for record in room_scope.records
                if _point_in_polygon(centre, record.polygon_pdf_pts)
            ]
            ids = tuple(str(record.face_id) for record in matches)
            face_ids.append(ids[0] if len(ids) == 1 else None)
            words.append(
                {
                    "raw": str(receipt.raw_text or ""),
                    "center": list(centre),
                    "native_status": getattr(
                        result.status, "value", str(result.status)
                    ),
                    "native_reason_codes": list(result.reason_codes),
                    "face_ids": list(ids),
                }
            )

        transitions = []
        for index in range(len(face_ids) - 1):
            left_id = face_ids[index]
            right_id = face_ids[index + 1]
            if not left_id or not right_id or left_id == right_id:
                continue
            left = room_by_face[left_id]
            right = room_by_face[right_id]
            shared = sorted(
                set(left.bounding_wall_ids) & set(right.bounding_wall_ids)
            )
            transitions.append(
                {
                    "from_word": words[index]["raw"],
                    "to_word": words[index + 1]["raw"],
                    "left_face_id": left_id,
                    "left_face_bbox": _bbox(left),
                    "left_area_page_pts2": left.area_page_pts2,
                    "right_face_id": right_id,
                    "right_face_bbox": _bbox(right),
                    "right_area_page_pts2": right.area_page_pts2,
                    "shared_bounding_wall_ids": shared,
                    "shared_walls": [wall_payload(wall_id) for wall_id in shared],
                }
            )

        rows.append(
            {
                "line": line,
                "key": list(key),
                "word_face_ids": face_ids,
                "words": words,
                "transitions": transitions,
            }
        )

    print(
        json.dumps(
            {
                "source_sha256": current.revision.source_sha256,
                "decision_scope_id": selector.decision_scope_id,
                "wall_scope_status": getattr(
                    wall_scope.status, "value", str(wall_scope.status)
                ),
                "wall_count": len(wall_scope.records),
                "room_scope_status": getattr(
                    room_scope.status, "value", str(room_scope.status)
                ),
                "room_face_count": len(room_scope.records),
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
