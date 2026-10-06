from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import SourceRoomLabelProducer, SourceRoomLabelSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_typed_negative_evidence import KIND_GRID, POLARITY_OPPOSING

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "7"
TARGET = "WASH UP"
SOURCE_GRID_REASON = "source_lineage_dense_orthogonal_lattice"


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-wash-up-separators",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

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
    if len(selectors) != 1:
        raise RuntimeError(f"expected one floor-plan viewport selector, got {len(selectors)}")
    selector = selectors[0]
    wall_scope = wall_authority.resolve_scope(selector)

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
    label_authority = SourceRoomLabelProducer.from_authorities(
        source,
        room_authority,
        page_ids=(PAGE_ID,),
    ).authority()
    label_scope = label_authority.resolve_scope(
        SourceRoomLabelSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )
    )

    candidates = [
        item
        for item in label_scope.split_face_candidates
        if _norm(item.label) == TARGET
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one {TARGET} split candidate, got {len(candidates)}")
    candidate = candidates[0]

    room_by_face = {str(record.face_id): record for record in room_scope.records}
    wall_by_id = {
        str(record.wall_candidate_id): record for record in wall_scope.records
    }

    grid_by_edge = {}
    all_atoms_by_edge = {}
    for atom in wall_scope.typed_semantic_evidence_atoms:
        metadata = dict(atom.metadata or {})
        edge_id = str(metadata.get("target_edge_id") or "")
        if not edge_id:
            continue
        all_atoms_by_edge.setdefault(edge_id, []).append({
            "evidence_id": atom.evidence_id,
            "kind": atom.kind,
            "status": getattr(atom.status, "value", str(atom.status)),
            "reason_codes": list(atom.reason_codes or ()),
            "polarity": metadata.get("polarity"),
            "feature_basis": metadata.get("feature_basis"),
        })
        if (
            atom.kind == KIND_GRID
            and atom.status is EvidenceResolutionStatus.CANDIDATE
            and str(metadata.get("polarity") or "") == POLARITY_OPPOSING
            and SOURCE_GRID_REASON in tuple(atom.reason_codes or ())
        ):
            grid_by_edge.setdefault(edge_id, []).append(atom.evidence_id)

    table = wall_scope.source_metadata_table
    transitions = []
    for left_id, right_id in zip(candidate.word_face_ids, candidate.word_face_ids[1:]):
        if left_id == right_id:
            continue
        left = room_by_face[str(left_id)]
        right = room_by_face[str(right_id)]
        shared = sorted(
            set(str(v) for v in left.bounding_wall_ids)
            & set(str(v) for v in right.bounding_wall_ids)
        )
        wall_rows = []
        for wall_id in shared:
            record = wall_by_id[wall_id]
            wall = record.wall_candidate
            edge_ids = list(dict.fromkeys([
                *[str(v) for v in (wall.face_a_segment_ids or ())],
                *[str(v) for v in (wall.face_b_segment_ids or ())],
            ]))
            descriptor = None if table is None else table.descriptor_for(wall_id)
            wall_rows.append({
                "wall_candidate_id": wall_id,
                "representation": wall.representation,
                "edge_ids": edge_ids,
                "fully_source_lineage_grid_opposed": bool(edge_ids) and all(
                    edge_id in grid_by_edge for edge_id in edge_ids
                ),
                "grid_edge_count": sum(edge_id in grid_by_edge for edge_id in edge_ids),
                "edge_count": len(edge_ids),
                "edge_atoms": {
                    edge_id: all_atoms_by_edge.get(edge_id, [])
                    for edge_id in edge_ids
                },
                "source_metadata": None if descriptor is None else {
                    "source_primitive_ids": list(descriptor.source_primitive_ids),
                    "matched_source_primitive_ids": list(descriptor.matched_source_primitive_ids),
                    "missing_source_primitive_ids": list(descriptor.missing_source_primitive_ids),
                    "width_values_pt": list(descriptor.width_values_pt),
                    "stroke_values": list(descriptor.stroke_values),
                    "fill_values": list(descriptor.fill_values),
                    "layer_values": list(descriptor.layer_values),
                    "dashes_values": list(descriptor.dashes_values),
                },
            })
        transitions.append({
            "left_face_id": str(left_id),
            "right_face_id": str(right_id),
            "shared_wall_ids": shared,
            "walls": wall_rows,
        })

    print(json.dumps({
        "source_sha256": source_sha,
        "label": candidate.label,
        "label_candidate_record_id": candidate.record_id,
        "word_face_ids": list(candidate.word_face_ids),
        "source_room_face_record_ids": list(candidate.source_room_face_record_ids),
        "transitions": transitions,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
