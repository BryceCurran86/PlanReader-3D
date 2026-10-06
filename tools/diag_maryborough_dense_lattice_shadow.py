from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import (
    SourceRoomLabelProducer,
    SourceRoomLabelSelector,
    _point_in_polygon,
)
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "7"
FRAGMENT_TARGETS = {
    "POS COUNTER",
    "FOOD SERVICE",
    "WASH UP",
    "TRUCK DRIVER LOUNGE",
    "DRY STORE",
}
CONTROL_LABELS = {
    "FOOD PREP",
    "COLD ROOM",
    "FREEZER",
    "SALES",
    "AIRLOCK",
    "LAUNDRY",
    "OFFICE",
    "PWD",
}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    source = SourceVisibilityProducer(
        producer_method="gpt2-dense-lattice-shadow-source",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-dense-lattice-shadow-source",
        source_bytes=SOURCE.read_bytes(),
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None

    # Match the production composition pre-pass used by the successful
    # fragment-lineage diagnostic so authenticated viewport ownership is
    # resolved before selecting the exact A110 floor-plan scope.
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )

    wall_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,
        page_ids=(PAGE_ID,),
    )
    wall_authority = wall_producer.authority()
    selectors = wall_authority.selectors_for_authenticated_viewports(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    assert len(selectors) == 1
    selector = selectors[0]
    wall_scope = wall_authority.resolve_scope(selector)
    lattice = wall_scope.dense_lattice_evaluation
    assert lattice is not None
    grid_like = set(lattice.grid_like_wall_candidate_ids)

    room_authority = build_source_room_face_authority(wall_authority)
    room_selector = SourceRoomFaceSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    )
    room_scope = room_authority.resolve_scope(room_selector)
    room_by_face = {
        str(record.face_id): record for record in room_scope.records
    }
    room_by_record = {
        str(record.record_id): record for record in room_scope.records
    }

    label_producer = SourceRoomLabelProducer.from_authorities(
        source,
        room_authority,
        page_ids=(PAGE_ID,),
    )
    label_scope = label_producer.authority().resolve_scope(
        SourceRoomLabelSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )
    )

    controls = {}
    for label_record in label_scope.records:
        label = _norm(label_record.label)
        if label not in CONTROL_LABELS:
            continue
        room = room_by_record.get(str(label_record.source_room_face_record_id))
        if room is None:
            continue
        bounding = tuple(str(value) for value in room.bounding_wall_ids)
        controls[label] = {
            "source_room_face_record_id": str(room.record_id),
            "bounding_wall_count": len(bounding),
            "grid_like_bounding_wall_ids": sorted(set(bounding) & grid_like),
        }

    text_authority = source.text_integrity_authority()
    grouped = defaultdict(list)
    for observation_id in current.text_observation_ids:
        result = text_authority.resolve_text(
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
            or str(receipt.page_id) != PAGE_ID
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
        ].append(receipt)

    transitions = []
    for key, receipts in sorted(grouped.items()):
        receipts = sorted(receipts, key=lambda item: int(item.word_no))
        line = _norm(
            " ".join(
                str(item.raw_text or "").strip()
                for item in receipts
                if str(item.raw_text or "").strip()
            )
        )
        if line not in FRAGMENT_TARGETS:
            continue
        face_ids = []
        for receipt in receipts:
            geom = tuple(float(value) for value in receipt.geometry)
            centre = (
                (geom[0] + geom[2]) * 0.5,
                (geom[1] + geom[3]) * 0.5,
            )
            matches = [
                room
                for room in room_scope.records
                if _point_in_polygon(centre, room.polygon_pdf_pts)
            ]
            face_ids.append(
                str(matches[0].face_id) if len(matches) == 1 else None
            )

        rows = []
        for index in range(len(face_ids) - 1):
            left_id = face_ids[index]
            right_id = face_ids[index + 1]
            if not left_id or not right_id or left_id == right_id:
                continue
            left = room_by_face[left_id]
            right = room_by_face[right_id]
            shared = tuple(
                sorted(
                    set(str(value) for value in left.bounding_wall_ids)
                    & set(str(value) for value in right.bounding_wall_ids)
                )
            )
            rows.append(
                {
                    "from_word": str(receipts[index].raw_text or ""),
                    "to_word": str(receipts[index + 1].raw_text or ""),
                    "shared_wall_ids": list(shared),
                    "grid_like_shared_wall_ids": sorted(
                        set(shared) & grid_like
                    ),
                    "all_shared_walls_grid_like": bool(shared)
                    and set(shared) <= grid_like,
                }
            )
        transitions.append(
            {
                "line": line,
                "source_line_key": list(key),
                "word_face_ids": face_ids,
                "transitions": rows,
            }
        )

    print(
        json.dumps(
            {
                "source_sha256": current.revision.source_sha256,
                "wall_scope_status": getattr(
                    wall_scope.status, "value", str(wall_scope.status)
                ),
                "wall_candidate_count": len(wall_scope.records),
                "dense_lattice_status": lattice.status,
                "dense_lattice_candidate_count": len(grid_like),
                "room_scope_status": getattr(
                    room_scope.status, "value", str(room_scope.status)
                ),
                "room_face_count": len(room_scope.records),
                "authenticated_label_count": len(label_scope.records),
                "controls": controls,
                "fragment_transitions": transitions,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
