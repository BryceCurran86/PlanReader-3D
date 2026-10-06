from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import fitz
from shapely.geometry import Polygon
from shapely.ops import unary_union

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
    _Word,
    _line_groups,
    _normalized_room_line,
    _point_in_polygon,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import (
    KIND_GRID,
    POLARITY_OPPOSING,
    collect_typed_semantic_evidence,
)
from pb_wall_room_topology_wall_assembly import assemble_wall_topology

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "7"
SOURCE_GRID_REASON = "source_lineage_dense_orthogonal_lattice"
TARGETS = {
    "TRUCK DRIVER LOUNGE",
    "POS COUNTER",
    "FOOD SERVICE",
    "DRY STORE",
    "WASH UP",
}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _exact_production_graph(source, published, selector, source_bytes):
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
    matching = [
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
    assert len(matching) == 1
    viewport = matching[0]
    assert viewport.bounding_box is not None

    owned = []
    for segment in page_segments:
        owners = [
            other
            for other in eligible
            if other.bounding_box is not None
            and wallmod._segment_fully_inside_bbox(segment, other.bounding_box)
        ]
        if (
            any(other.view_id == viewport.view_id for other in owners)
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
    strips = wallmod._proven_filled_wall_strips(topology_segments)
    graph_segments = wallmod._filter_proven_wall_strip_geometry(
        topology_segments,
        strips,
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
    return graph, tuple(walls)


def _fully_grid_opposed_wall_ids(graph, wall_scope):
    atoms = collect_typed_semantic_evidence(
        graph,
        document_id=wall_scope.document_id,
        page_id=wall_scope.page_id,
        viewport_id=wall_scope.decision_scope_id,
    )
    grid_edges = set()
    evidence_by_edge = defaultdict(list)
    for atom in atoms:
        metadata = dict(atom.metadata or {})
        if (
            atom.kind == KIND_GRID
            and str(metadata.get("polarity") or "") == POLARITY_OPPOSING
            and SOURCE_GRID_REASON in tuple(atom.reason_codes or ())
        ):
            edge_id = str(metadata.get("target_edge_id") or "")
            if edge_id:
                grid_edges.add(edge_id)
                evidence_by_edge[edge_id].append(atom.evidence_id)

    fully = set()
    payload = {}
    for record in wall_scope.records:
        wall = record.wall_candidate
        edge_ids = tuple(
            dict.fromkeys(
                (
                    *tuple(str(v) for v in (wall.face_a_segment_ids or ())),
                    *tuple(str(v) for v in (wall.face_b_segment_ids or ())),
                )
            )
        )
        grid_count = sum(edge_id in grid_edges for edge_id in edge_ids)
        is_full = bool(edge_ids) and grid_count == len(edge_ids)
        if is_full:
            fully.add(str(record.wall_candidate_id))
        payload[str(record.wall_candidate_id)] = {
            "edge_count": len(edge_ids),
            "grid_edge_count": grid_count,
            "fully_grid_opposed": is_full,
            "grid_evidence_ids": sorted(
                {
                    evidence_id
                    for edge_id in edge_ids
                    for evidence_id in evidence_by_edge.get(edge_id, ())
                }
            ),
        }
    return fully, payload, len(atoms), len(grid_edges)


def main() -> int:
    source_bytes = SOURCE.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="gpt2-grid-composite-face-diag",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
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
    current = source.published_snapshot_for_revision(published.revision.revision_id)
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

    graph, replay_walls = _exact_production_graph(
        source, published, selector, source_bytes
    )
    assert {w.candidate_id for w in replay_walls} == {
        str(r.wall_candidate_id) for r in wall_scope.records
    }
    fully_grid, wall_payload, atom_count, grid_edge_count = (
        _fully_grid_opposed_wall_ids(graph, wall_scope)
    )

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

    label_producer = SourceRoomLabelProducer.from_authorities(
        source,
        room_authority,
        page_ids=(PAGE_ID,),
    )

    text_authority = source.text_integrity_authority()
    words = []
    for observation_id in current.text_observation_ids:
        native = text_authority.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = native.receipt
        if (
            receipt is None
            or str(receipt.page_id) != PAGE_ID
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        geometry = tuple(float(v) for v in receipt.geometry)
        if (
            len(geometry) != 4
            or not all(math.isfinite(v) for v in geometry)
            or geometry[2] <= geometry[0]
            or geometry[3] <= geometry[1]
        ):
            continue
        words.append(
            _Word(
                observation_id=observation_id,
                receipt_id=receipt.receipt_id,
                source_partition_id=str(receipt.source_partition_id),
                raw_text=str(receipt.raw_text or ""),
                geometry=geometry,
                block_no=int(receipt.block_no),
                line_no=int(receipt.line_no),
                word_no=int(receipt.word_no),
            )
        )

    rows = []
    for line in _line_groups(words):
        raw_line = " ".join(
            word.raw_text.strip()
            for word in line
            if word.raw_text.strip()
        )
        candidate = _normalized_room_line(raw_line)
        if candidate is None or _norm(candidate) not in TARGETS:
            continue

        evidence = []
        unresolved = False
        for word in line:
            authorized = label_producer._authorize_word(published, word)
            if authorized is None:
                unresolved = True
                break
            evidence.append(authorized)
        if unresolved:
            fallback = label_producer._authorize_line_fallback(
                published, line, raw_line
            )
            if fallback is None:
                rows.append({
                    "label": _norm(candidate),
                    "eligible": False,
                    "reason": "text_authority_unresolved",
                })
                continue
            evidence = list(fallback)

        face_ids = []
        word_rows = []
        for item in evidence:
            x0, y0, x1, y1 = item.geometry
            point = ((x0 + x1) * 0.5, (y0 + y1) * 0.5)
            matches = [
                record
                for record in room_scope.records
                if _point_in_polygon(point, record.polygon_pdf_pts)
            ]
            face_id = str(matches[0].face_id) if len(matches) == 1 else None
            face_ids.append(face_id)
            word_rows.append({
                "text": item.trusted_text,
                "point": list(point),
                "face_id": face_id,
                "match_count": len(matches),
            })

        transitions = []
        transition_ok = True
        for index in range(len(face_ids) - 1):
            left_id = face_ids[index]
            right_id = face_ids[index + 1]
            if not left_id or not right_id:
                transition_ok = False
                transitions.append({
                    "from": word_rows[index]["text"],
                    "to": word_rows[index + 1]["text"],
                    "reason": "face_ownership_unresolved",
                })
                continue
            if left_id == right_id:
                transitions.append({
                    "from": word_rows[index]["text"],
                    "to": word_rows[index + 1]["text"],
                    "same_face": True,
                    "eligible": True,
                })
                continue
            left = room_by_face[left_id]
            right = room_by_face[right_id]
            shared = tuple(sorted(
                set(str(v) for v in left.bounding_wall_ids)
                & set(str(v) for v in right.bounding_wall_ids)
            ))
            all_grid = bool(shared) and all(wall_id in fully_grid for wall_id in shared)
            if not all_grid:
                transition_ok = False
            transitions.append({
                "from": word_rows[index]["text"],
                "to": word_rows[index + 1]["text"],
                "left_face_id": left_id,
                "right_face_id": right_id,
                "shared_wall_ids": list(shared),
                "all_shared_walls_fully_grid_opposed": all_grid,
                "shared_walls": {
                    wall_id: wall_payload.get(wall_id) for wall_id in shared
                },
            })

        constituent_ids = tuple(dict.fromkeys(
            face_id for face_id in face_ids if face_id
        ))
        composite = None
        union_diagnostics = None
        composite_ok = transition_ok and len(constituent_ids) >= 2
        if composite_ok:
            polygons = [
                Polygon(room_by_face[face_id].polygon_pdf_pts)
                for face_id in constituent_ids
            ]
            pairwise = []
            for left_index, left in enumerate(polygons):
                for right_index, right in enumerate(polygons[left_index + 1 :], start=left_index + 1):
                    intersection = left.intersection(right)
                    pairwise.append({
                        "left_face_id": constituent_ids[left_index],
                        "right_face_id": constituent_ids[right_index],
                        "distance": float(left.distance(right)),
                        "touches": bool(left.touches(right)),
                        "intersects": bool(left.intersects(right)),
                        "intersection_geom_type": intersection.geom_type,
                        "intersection_area": float(intersection.area),
                        "intersection_length": float(intersection.length),
                    })
            merged = unary_union(polygons)
            union_diagnostics = {
                "constituent_face_ids": list(constituent_ids),
                "constituent_polygons": [
                    {
                        "face_id": face_id,
                        "is_valid": bool(polygon.is_valid),
                        "area_page_pts2": float(polygon.area),
                        "bounds": list(polygon.bounds),
                        "polygon_pdf_pts": [
                            [float(x), float(y)]
                            for x, y in tuple(polygon.exterior.coords)[:-1]
                        ],
                    }
                    for face_id, polygon in zip(constituent_ids, polygons)
                ],
                "pairwise": pairwise,
                "union_geom_type": merged.geom_type,
                "union_is_empty": bool(merged.is_empty),
                "union_is_valid": bool(merged.is_valid),
                "union_area_page_pts2": float(merged.area),
            }
            if (
                merged.geom_type != "Polygon"
                or merged.is_empty
                or not merged.is_valid
            ):
                composite_ok = False
            else:
                composite = {
                    "constituent_face_ids": list(constituent_ids),
                    "area_page_pts2": float(merged.area),
                    "vertex_count": len(tuple(merged.exterior.coords)) - 1,
                    "polygon_pdf_pts": [
                        [float(x), float(y)]
                        for x, y in tuple(merged.exterior.coords)[:-1]
                    ],
                }

        rows.append({
            "label": _norm(candidate),
            "eligible": bool(composite_ok),
            "word_faces": word_rows,
            "transitions": transitions,
            "composite": composite,
            "union_diagnostics": union_diagnostics,
        })

    print(json.dumps({
        "source_sha256": source_sha,
        "wall_count": len(wall_scope.records),
        "room_face_count": len(room_scope.records),
        "u2_atom_count": atom_count,
        "source_grid_edge_count": grid_edge_count,
        "fully_grid_opposed_wall_count": len(fully_grid),
        "rows": rows,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
