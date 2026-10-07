from __future__ import annotations

import itertools
import json
from collections import Counter
from pathlib import Path

from shapely.geometry import Polygon
from shapely.ops import unary_union

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
import pb_source_composite_room_face_authority as comp
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import SourceRoomLabelProducer, SourceRoomLabelSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGET = "WASH UP"


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


source = SourceVisibilityProducer(
    producer_method="diag-gpt2-wash-up-unique-closed-subcomponent",
    producer_version="1",
)
published = source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-wash-up-unique-closed-subcomponent",
    source_bytes=SOURCE.read_bytes(),
    source_locator="memory://maryborough.pdf",
    page_ids=("7",),
)
compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=("7",),
    evidence_page_ids=(),
)
current = source.published_snapshot_for_revision(published.revision.revision_id)
assert current is not None

wall_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
    source, page_ids=("7",)
)
wall_auth = wall_producer.authority()
selectors = wall_auth.selectors_for_authenticated_viewports(
    document_id=current.revision.document_id,
    revision_id=current.revision.revision_id,
    source_sha256=current.revision.source_sha256,
    snapshot_id=current.snapshot.snapshot_id,
    page_id="7",
    view_type=DrawingViewType.FLOOR_PLAN.value,
)
assert len(selectors) == 1, len(selectors)
selector = selectors[0]
wall_scope = wall_auth.resolve_scope(selector)

room_auth = build_source_room_face_authority(wall_auth)
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
label_scope = SourceRoomLabelProducer.from_authorities(
    source, room_auth, page_ids=("7",)
).authority().resolve_scope(
    SourceRoomLabelSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    )
)
candidates = [c for c in label_scope.split_face_candidates if norm(c.label) == TARGET]
assert len(candidates) == 1, len(candidates)
candidate = candidates[0]

fully_grid, evidence_by_wall = comp._fully_grid_opposed_wall_evidence(wall_scope)
full_component = comp._grid_connected_component(
    tuple(str(v) for v in candidate.word_face_ids),
    room_scope=room_scope,
    fully_grid_wall_ids=fully_grid,
)
assert full_component is not None
room_by_face = {str(r.face_id): r for r in room_scope.records}
edge_owners = comp._local_edge_owners(room_scope)
adjacency = comp._grid_local_adjacency(room_scope, fully_grid)

seeds = tuple(dict.fromkeys(str(v) for v in candidate.word_face_ids))
seed_set = set(seeds)
optional = tuple(face for face in full_component if face not in seed_set)


def is_connected(face_ids: set[str]) -> bool:
    start = next(iter(face_ids))
    visited = {start}
    pending = [start]
    while pending:
        face = pending.pop()
        for neighbour, _wall_id, _edge in adjacency.get(face, ()):
            if neighbour in face_ids and neighbour not in visited:
                visited.add(neighbour)
                pending.append(neighbour)
    return visited == face_ids


def evaluate(face_ids: set[str]):
    if not seed_set.issubset(face_ids) or not is_connected(face_ids):
        return None
    ordered = tuple(sorted(face_ids))
    if comp._component_has_conflicting_label(
        ordered, candidate, label_scope=label_scope
    ):
        return None

    constituent = [room_by_face[face] for face in ordered]
    polygons = [Polygon(record.polygon_pdf_pts) for record in constituent]
    if any(poly.is_empty or not poly.is_valid or poly.area <= 0.0 for poly in polygons):
        return None
    merged = unary_union(polygons)
    if (
        merged.geom_type != "Polygon"
        or merged.is_empty
        or not merged.is_valid
        or merged.area <= 0.0
        or len(tuple(merged.interiors)) != 0
    ):
        return None

    counts = Counter()
    for record in constituent:
        for wall_id, edge in tuple(record.boundary_wall_edges or ()):
            key = (str(wall_id), comp._edge_key(edge))
            if not key[0] or key[1] is None:
                return None
            counts[key] += 1
    if not counts or any(count > 2 for count in counts.values()):
        return None

    separator = []
    external = []
    invalid_internal = []
    external_grid = []
    for key, count in counts.items():
        wall_id, edge = key
        global_owners = edge_owners.get(key, ())
        if count == 2:
            if (
                wall_id not in fully_grid
                or len(global_owners) != 2
                or not set(global_owners).issubset(face_ids)
            ):
                invalid_internal.append(
                    {
                        "wall_id": wall_id,
                        "edge": [list(edge[0]), list(edge[1])],
                        "global_owners": list(global_owners),
                        "grid": wall_id in fully_grid,
                    }
                )
            else:
                separator.append(key)
        elif count == 1:
            external.append(key)
            if wall_id in fully_grid:
                external_grid.append(
                    {
                        "wall_id": wall_id,
                        "edge": [list(edge[0]), list(edge[1])],
                        "global_owners": list(global_owners),
                    }
                )
        else:
            return None

    if invalid_internal or external_grid or not separator or not external:
        return None

    grid_evidence = sorted(
        {
            evidence_id
            for wall_id, _edge in separator
            for evidence_id in evidence_by_wall.get(wall_id, ())
        }
    )
    if not grid_evidence:
        return None

    return {
        "face_count": len(face_ids),
        "face_ids": ordered,
        "area_page_pts2": float(merged.area),
        "separator_subedge_count": len(separator),
        "external_subedge_count": len(external),
        "separator_wall_ids": sorted({wall_id for wall_id, _edge in separator}),
        "external_wall_ids": sorted({wall_id for wall_id, _edge in external}),
        "grid_evidence_count": len(grid_evidence),
    }


valid = []
examined = 0
connected = 0
for size in range(len(optional) + 1):
    for choice in itertools.combinations(optional, size):
        examined += 1
        faces = seed_set | set(choice)
        if is_connected(faces):
            connected += 1
        result = evaluate(faces)
        if result is not None:
            valid.append(result)

print(
    json.dumps(
        {
            "target": TARGET,
            "seed_face_ids": seeds,
            "full_component_face_count": len(full_component),
            "full_component_face_ids": list(full_component),
            "optional_face_count": len(optional),
            "subsets_examined": examined,
            "connected_subsets_examined": connected,
            "valid_source_closed_subcomponent_count": len(valid),
            "valid_source_closed_subcomponents": valid,
        },
        indent=2,
        sort_keys=True,
    )
)
