"""Read-only: W4 wall scopes + W5 source room faces + grid-separator adjacency, using the production producers unchanged.

p7  : viewport-addressed scopes (the same route the live pipeline uses for room faces; floor-plan viewports only)
p11 : page-addressed scope (p11 has no authenticated plan viewport; geometry evidence only, nothing is published)
Nothing is written to the repository; the helpers imported from pb_source_composite_room_face_authority are used read-only.
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
repo, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)

from pb_drawing_evidence_binding import DrawingViewType  # noqa: E402
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION  # noqa: E402
from pb_physical_wall_candidate_authority import (  # noqa: E402
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _decision_scope_id,
)
from pb_source_composite_room_face_authority import (  # noqa: E402
    _atomic_source_wall_edge_counts,
    _fully_grid_opposed_wall_evidence,
    _grid_local_adjacency,
)
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402

PDF = Path(f"{repo}/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
payload = PDF.read_bytes()
sha = hashlib.sha256(payload).hexdigest()
source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
t0 = time.time()
pub = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("7", "11"))
published = source.published_snapshot_for_revision(pub.revision.revision_id)
print("ingest", round(time.time() - t0, 1), "s", flush=True)


def dump_scope(tag, producer, selector, authority):
    t1 = time.time()
    scope = authority.resolve_scope(selector)
    room_authority = build_source_room_face_authority(authority)
    room_scope = room_authority.resolve_scope(
        SourceRoomFaceSelector(
            document_id=scope.document_id, revision_id=scope.revision_id, source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id, page_id=scope.page_id, decision_scope_id=scope.decision_scope_id,
        )
    )
    grid_ids, _grid_ev = _fully_grid_opposed_wall_evidence(scope)
    counts_grid = _atomic_source_wall_edge_counts(room_scope, set(grid_ids))
    counts_plain = _atomic_source_wall_edge_counts(room_scope, set())
    grid_adj = _grid_local_adjacency(room_scope, set(grid_ids), local_counts=counts_grid)
    # two-sided separators that are NOT grid-opposed (real wall subedges shared by exactly two published faces)
    wall_adj = defaultdict(list)
    for (wall_id, edge), face_counts in counts_plain.items():
        if wall_id in grid_ids or len(face_counts) != 2 or any(c != 1 for c in face_counts.values()):
            continue
        a, b = sorted(face_counts)
        wall_adj[a].append((b, wall_id, [list(edge[0]), list(edge[1])]))
        wall_adj[b].append((a, wall_id, [list(edge[0]), list(edge[1])]))
    records = []
    for r in scope.records:
        w = r.wall_candidate
        records.append({
            "wall_candidate_id": r.wall_candidate_id,
            "grid_fully_opposed": r.wall_candidate_id in grid_ids,
            "centerline_pts": [list(map(float, p)) for p in getattr(w, "centerline_pts", ())],
            "thickness_pt": getattr(w, "thickness_pt", None),
            "face_a_segment_ids": list(getattr(w, "face_a_segment_ids", ()) or ()),
            "face_b_segment_ids": list(getattr(w, "face_b_segment_ids", ()) or ()),
            "source_primitive_ids": list(r.physical_identity.source_primitive_ids),
        })
    faces = [{
        "record_id": f.record_id, "face_id": f.face_id, "polygon_pdf_pts": [list(map(float, p)) for p in f.polygon_pdf_pts],
        "bounding_wall_ids": list(f.bounding_wall_ids), "area_page_pts2": f.area_page_pts2,
        "boundary_wall_edges": [[wid, [list(e[0]), list(e[1])]] for wid, e in f.boundary_wall_edges],
    } for f in room_scope.records]
    abst = [{
        "face_id": f.face_id, "reason": f.reason, "polygon_pdf_pts": [list(map(float, p)) for p in f.polygon_pdf_pts],
        "bounding_wall_ids": list(f.bounding_wall_ids), "area_page_pts2": f.area_page_pts2,
        "boundary_wall_edges": [[wid, [list(e[0]), list(e[1])]] for wid, e in f.boundary_wall_edges],
    } for f in room_scope.abstained_faces]
    # analysis-only adjacency over published AND withheld faces (withheld faces keep exact producer-owned subedge ownership)
    from types import SimpleNamespace
    both = SimpleNamespace(records=tuple(room_scope.records) + tuple(room_scope.abstained_faces))
    counts_grid_all = _atomic_source_wall_edge_counts(both, set(grid_ids))
    counts_plain_all = _atomic_source_wall_edge_counts(both, set())
    grid_adj_all = _grid_local_adjacency(both, set(grid_ids), local_counts=counts_grid_all)
    wall_adj_all = defaultdict(list)
    for (wall_id, edge), face_counts in counts_plain_all.items():
        if wall_id in grid_ids or len(face_counts) != 2 or any(c != 1 for c in face_counts.values()):
            continue
        a, b = sorted(face_counts)
        wall_adj_all[a].append((b, wall_id, [list(edge[0]), list(edge[1])]))
        wall_adj_all[b].append((a, wall_id, [list(edge[0]), list(edge[1])]))
    res = {
        "tag": tag, "page_id": scope.page_id, "decision_scope_id": scope.decision_scope_id, "snapshot_id": scope.snapshot_id,
        "scope_kind": scope.scope_kind, "viewport_id": scope.viewport_id, "viewport_bbox": scope.viewport_bbox,
        "viewport_view_type": scope.viewport_view_type, "viewport_status": scope.viewport_status,
        "w4_status": scope.status.value, "w4_scope_complete": scope.scope_complete, "w4_reasons": list(scope.reason_codes),
        "w4_records": records, "grid_fully_opposed_wall_ids": sorted(grid_ids),
        "w5_status": room_scope.status.value, "w5_scope_complete": room_scope.scope_complete, "w5_reasons": list(room_scope.reason_codes),
        "faces": faces, "abstained_faces": abst,
        "grid_adjacency": {k: [[n, w, [list(e[0]), list(e[1])]] for n, w, e in v] for k, v in grid_adj.items()},
        "wall_adjacency": dict(wall_adj),
        "grid_adjacency_all_faces": {k: [[n, w, [list(e[0]), list(e[1])]] for n, w, e in v] for k, v in grid_adj_all.items()},
        "wall_adjacency_all_faces": dict(wall_adj_all),
        "elapsed_s": round(time.time() - t1, 1),
    }
    print(tag, "W4", scope.status.value, "complete", scope.scope_complete, "records", len(records), "grid-opposed", len(grid_ids),
          "| W5", room_scope.status.value, "faces", len(faces), "abstained", len(abst), "grid-adj faces", len(grid_adj), res["elapsed_s"], "s", flush=True)
    return res


results = {"source_sha256": sha, "scopes": []}
# p7: viewport scopes (floor-plan only) -- same addressing as the live room-face route
producer7 = PhysicalWallCandidateProducer.from_authenticated_viewports(source, page_ids=("7",))
auth7 = producer7.authority()
published = source.published_snapshot_for_revision(pub.revision.revision_id)  # newest derived generation (selector must match it)
print("snapshot after viewport producer:", published.snapshot.snapshot_id, flush=True)
selectors = auth7.selectors_for_authenticated_viewports(
    document_id=published.revision.document_id, revision_id=published.revision.revision_id,
    source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
    page_id="7", view_type=DrawingViewType.FLOOR_PLAN.value,
)
print("p7 floor-plan viewport selectors:", len(selectors), flush=True)
for sel in selectors:
    results["scopes"].append(dump_scope("p7_viewport", producer7, sel, auth7))
    json.dump(results, open(out, "w"))
# p11: page-addressed
producer11 = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("11",))
auth11 = producer11.authority()
published = source.published_snapshot_for_revision(pub.revision.revision_id)
sel11 = PhysicalWallCandidateSelector(
    document_id=published.revision.document_id, revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
    snapshot_id=published.snapshot.snapshot_id, page_id="11", decision_scope_id=_decision_scope_id("11"),
)
results["scopes"].append(dump_scope("p11_page", producer11, sel11, auth11))
json.dump(results, open(out, "w"))
print("saved", out, "total", round(time.time() - t0, 1), "s")
