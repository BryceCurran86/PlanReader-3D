from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fitz

import pb_physical_wall_candidate_authority as wallmod
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
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_wall_assembly import assemble_wall_topology
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import (
    KIND_GRID,
    POLARITY_OPPOSING,
    bundle_status,
    collect_typed_semantic_evidence,
)


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


def _exact_production_graph(
    source: SourceVisibilityProducer,
    published,
    selector,
    source_bytes: bytes,
):
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

    page_scope_id = wallmod._decision_scope_id(PAGE_ID)
    page_segments, _obs_ids, page_width, page_height = wallmod._source_page_segments(
        source_producer=source,
        published=current,
        source_bytes=source_bytes,
        page_id=PAGE_ID,
        decision_scope_id=page_scope_id,
    )

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page = pdf.load_page(int(PAGE_ID) - 1)
        page_viewports = wallmod._all_viewports(page, page_number=int(PAGE_ID))
    finally:
        pdf.close()
    authenticated = wallmod._authenticated_viewports_from_rows(page_viewports)
    assert authenticated is not None
    all_viewports, eligible = authenticated
    sibling_fingerprint = wallmod._viewport_sibling_set_fingerprint(all_viewports)

    matching_viewports = [
        viewport
        for viewport in eligible
        if wallmod._viewport_decision_scope_id(
            published=current,
            page_id=PAGE_ID,
            viewport=viewport,
            sibling_set_fingerprint=sibling_fingerprint,
        )
        == selector.decision_scope_id
    ]
    assert len(matching_viewports) == 1
    viewport = matching_viewports[0]
    assert viewport.bounding_box is not None

    owned = []
    for segment in page_segments:
        owners = [
            other
            for other in eligible
            if other.bounding_box is not None
            and wallmod._segment_fully_inside_bbox(segment, other.bounding_box)
        ]
        target_owned = any(other.view_id == viewport.view_id for other in owners)
        if (
            target_owned
            and len(owners) == 1
            and not wallmod._segment_lies_on_bbox_edge(
                segment, viewport.bounding_box
            )
        ):
            scoped = dict(segment)
            scoped["viewport_id"] = selector.decision_scope_id
            owned.append(scoped)

    topology_segments = wallmod._filter_repeated_non_physical_drafting_primitives(
        owned,
        page_width=page_width,
        page_height=page_height,
    )
    proven_wall_strips = wallmod._proven_filled_wall_strips(topology_segments)
    graph_segments = wallmod._filter_proven_wall_strip_geometry(
        topology_segments,
        proven_wall_strips,
    )
    graph = build_wall_graph_for_viewport(graph_segments)
    junctions, relationships = classify_junctions(
        graph,
        document_id=current.revision.document_id,
        page_id=PAGE_ID,
        viewport_id=selector.decision_scope_id,
    )
    walls, _ = assemble_wall_topology(
        graph,
        junctions,
        relationships,
        viewport_id=selector.decision_scope_id,
    )
    return graph, tuple(walls), viewport


def _edge_payload(edge_id: str, atoms_by_edge: dict[str, list[object]]) -> dict:
    atoms = tuple(atoms_by_edge.get(edge_id, ()))
    grid = tuple(
        atom
        for atom in atoms
        if atom.kind == KIND_GRID
        and str((atom.metadata or {}).get("polarity") or "") == POLARITY_OPPOSING
    )
    return {
        "edge_id": edge_id,
        "bundle_status": bundle_status(atoms).value if atoms else "abstained",
        "kinds": sorted({atom.kind for atom in atoms}),
        "polarities": sorted(
            {
                str((atom.metadata or {}).get("polarity") or "")
                for atom in atoms
            }
        ),
        "grid_opposing": bool(grid),
        "grid_reason_codes": sorted(
            {
                reason
                for atom in grid
                for reason in tuple(atom.reason_codes or ())
            }
        ),
        "grid_feature_basis": [
            dict((atom.metadata or {}).get("feature_basis") or {})
            for atom in grid
        ],
    }


def main() -> int:
    source_bytes = SOURCE.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="gpt2-maryborough-u2-grid-wall-bridge",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-maryborough-u2-grid-wall-bridge",
        source_bytes=source_bytes,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )

    # Prime the same production composition/viewport ownership used by the live
    # Maryborough chain before asking for authenticated floor-plan selectors.
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
    current = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None
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

    graph, replay_walls, viewport = _exact_production_graph(
        source,
        current,
        selector,
        source_bytes,
    )
    live_wall_ids = {str(record.wall_candidate_id) for record in wall_scope.records}
    replay_wall_ids = {str(wall.candidate_id) for wall in replay_walls}
    assert replay_wall_ids == live_wall_ids

    atoms = collect_typed_semantic_evidence(
        graph,
        document_id=current.revision.document_id,
        page_id=PAGE_ID,
        viewport_id=selector.decision_scope_id,
    )
    atoms_by_edge: dict[str, list[object]] = defaultdict(list)
    for atom in atoms:
        edge_id = str((atom.metadata or {}).get("target_edge_id") or "")
        if edge_id:
            atoms_by_edge[edge_id].append(atom)

    wall_by_id = {
        str(record.wall_candidate_id): record
        for record in wall_scope.records
    }

    def wall_payload(wall_id: str) -> dict:
        record = wall_by_id.get(wall_id)
        if record is None:
            return {"wall_candidate_id": wall_id, "record_unavailable": True}
        wall = record.wall_candidate
        edge_ids = tuple(
            dict.fromkeys(
                (
                    *tuple(str(value) for value in (wall.face_a_segment_ids or ())),
                    *tuple(
                        str(value)
                        for value in (wall.face_b_segment_ids or ())
                    ),
                )
            )
        )
        edge_rows = [_edge_payload(edge_id, atoms_by_edge) for edge_id in edge_ids]
        grid_rows = [row for row in edge_rows if row["grid_opposing"]]
        return {
            "wall_candidate_id": wall_id,
            "representation": wall.representation,
            "edge_ids": list(edge_ids),
            "edge_evidence": edge_rows,
            "has_any_u2_grid_opposition": bool(grid_rows),
            "all_contributing_edges_u2_grid_opposed": bool(edge_rows)
            and len(grid_rows) == len(edge_rows),
            "grid_edge_bundle_statuses": sorted(
                {row["bundle_status"] for row in grid_rows}
            ),
        }

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

    fragment_rows = []
    fragment_wall_ids: set[str] = set()
    for key, receipts in sorted(grouped.items()):
        ordered = sorted(receipts, key=lambda item: int(item.word_no))
        line = _norm(
            " ".join(
                str(item.raw_text or "").strip()
                for item in ordered
                if str(item.raw_text or "").strip()
            )
        )
        if line not in FRAGMENT_TARGETS:
            continue
        word_face_ids = []
        for receipt in ordered:
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
            word_face_ids.append(
                str(matches[0].face_id) if len(matches) == 1 else None
            )

        transitions = []
        for index in range(len(word_face_ids) - 1):
            left_id = word_face_ids[index]
            right_id = word_face_ids[index + 1]
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
            fragment_wall_ids.update(shared)
            transitions.append(
                {
                    "from_word": str(ordered[index].raw_text or ""),
                    "to_word": str(ordered[index + 1].raw_text or ""),
                    "shared_wall_ids": list(shared),
                    "shared_walls": [wall_payload(wall_id) for wall_id in shared],
                }
            )

        fragment_rows.append(
            {
                "line": line,
                "source_line_key": list(key),
                "word_face_ids": word_face_ids,
                "transitions": transitions,
            }
        )

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
    control_wall_ids: set[str] = set()
    for label_record in label_scope.records:
        label = _norm(label_record.label)
        if label not in CONTROL_LABELS:
            continue
        room = room_by_record.get(str(label_record.source_room_face_record_id))
        if room is None:
            continue
        bounding = tuple(sorted(str(value) for value in room.bounding_wall_ids))
        control_wall_ids.update(bounding)
        controls[label] = {
            "source_room_face_record_id": str(room.record_id),
            "bounding_wall_ids": list(bounding),
            "bounding_walls": [wall_payload(wall_id) for wall_id in bounding],
        }

    fragment_payloads = [
        wall_payload(wall_id) for wall_id in sorted(fragment_wall_ids)
    ]
    control_payloads = [
        wall_payload(wall_id) for wall_id in sorted(control_wall_ids)
    ]

    print(
        json.dumps(
            {
                "source_sha256": current.revision.source_sha256,
                "viewport_id": str(viewport.view_id),
                "decision_scope_id": selector.decision_scope_id,
                "graph_edge_count": len(graph.get("edges") or ()),
                "w4_wall_count": len(wall_scope.records),
                "room_face_count": len(room_scope.records),
                "u2_atom_count": len(atoms),
                "u2_grid_atom_count": sum(
                    1
                    for atom in atoms
                    if atom.kind == KIND_GRID
                    and str((atom.metadata or {}).get("polarity") or "")
                    == POLARITY_OPPOSING
                ),
                "fragment_wall_count": len(fragment_wall_ids),
                "fragment_walls_with_any_u2_grid_opposition": sum(
                    1
                    for row in fragment_payloads
                    if row.get("has_any_u2_grid_opposition")
                ),
                "fragment_walls_all_edges_u2_grid_opposed": sum(
                    1
                    for row in fragment_payloads
                    if row.get("all_contributing_edges_u2_grid_opposed")
                ),
                "control_wall_count": len(control_wall_ids),
                "control_walls_with_any_u2_grid_opposition": sum(
                    1
                    for row in control_payloads
                    if row.get("has_any_u2_grid_opposition")
                ),
                "fragment_transitions": fragment_rows,
                "fragment_walls": fragment_payloads,
                "authenticated_controls": controls,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
