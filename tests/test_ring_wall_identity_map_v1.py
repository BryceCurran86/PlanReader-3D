"""Report-only map from layered ring edges to physical wall candidates (#4764 7219675205, C06/C08). Synthetic only."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import fitz

from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
from pb_ring_wall_identity_map_shadow import AMBIGUOUS_ONLY, CLOSURE_EDGE, NO_WALL, PUBLISHED, ring_wall_identity_map
from pb_source_visibility_authority import SourceVisibilityProducer

BLACK = (0, 0, 0)


def _double_rooms(*, door=True):
    """Two rooms in double-line walls; the shared wall has a 30 pt doorway with jambs."""
    document = fitz.open()
    page = document.new_page(width=600, height=400)

    def line(a, b):
        page.draw_line(a, b, color=BLACK, width=0.7)

    def rect(x0, y0, x1, y1):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(a, b)

    rect(44, 44, 290, 170)
    if door:
        for a, b in (((50, 50), (164, 50)), ((50, 50), (50, 164)), ((50, 164), (164, 164)), ((164, 50), (164, 90)),
                     ((164, 120), (164, 164)), ((164, 90), (170, 90)), ((164, 120), (170, 120)), ((170, 50), (284, 50)),
                     ((284, 50), (284, 164)), ((170, 164), (284, 164)), ((170, 50), (170, 90)), ((170, 120), (170, 164))):
            line(a, b)
    else:
        rect(50, 50, 164, 164)
        rect(170, 50, 284, 164)
    data = document.tobytes()
    document.close()
    return data


def _scope_and_rings(data):
    source = SourceVisibilityProducer(producer_method="ring-wall-map-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="ring-map", source_bytes=data,
                                               source_locator="memory://rings.pdf", page_ids=("1",))
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    scope = authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id="ring-map", revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1", decision_scope_id=_decision_scope_id("1")))
    result = build_from_pdf_bytes(data, source_sha256=hashlib.sha256(data).hexdigest(), page_index=0,
                                  dark_painted_wall_source=True)
    return scope, [ring for ring in result.rings if ring.status.value == "candidate"]


def test_every_ring_wall_edge_maps_to_a_wall_on_that_line_and_closures_stay_closures():
    scope, rings = _scope_and_rings(_double_rooms())
    assert len(rings) == 2
    rows = ring_wall_identity_map(rings, scope)
    records = {r.wall_candidate_id: r.wall_candidate for r in scope.records}
    for ring, row in zip(rings, rows):
        points = [tuple(p) for p in ring.polygon_pdf_pts]
        assert len(row["edges"]) == len(points)
        for (a, b), edge in zip(zip(points, points[1:] + points[:1]), row["edges"]):
            if edge["kind"] == CLOSURE_EDGE:
                assert not edge["wall_ids"]
                continue
            assert edge["kind"] != NO_WALL and edge["wall_ids"]
            axis = 0 if abs(a[1] - b[1]) < abs(a[0] - b[0]) else 1
            for wall_id in edge["wall_ids"]:  # each mapped wall runs along this very line, not the far face
                line_coordinate = a[1 - axis]
                assert all(abs(p[1 - axis] - line_coordinate) < 1.0 for p in records[wall_id].centerline_pts)
    assert sum(row["counts"][CLOSURE_EDGE] for row in rows) >= 1
    assert all(set(row["counts"]) == {PUBLISHED, AMBIGUOUS_ONLY, NO_WALL, CLOSURE_EDGE} for row in rows)


def test_publication_is_reported_never_chosen():
    scope, rings = _scope_and_rings(_double_rooms(door=False))
    rows = ring_wall_identity_map(rings, scope)
    # without a physical scale the two faces of each wall compete, so no edge claims a published wall
    published = set(scope.equivalence.representative_wall_ids)
    for row in rows:
        for edge in row["edges"]:
            assert (edge["kind"] == PUBLISHED) == bool(set(edge["wall_ids"]) & published)


def test_a_wall_from_another_path_or_off_the_line_is_not_mapped():
    scope, rings = _scope_and_rings(_double_rooms(door=False))
    foreign = SimpleNamespace(records=tuple(
        SimpleNamespace(wall_candidate_id=r.wall_candidate_id, wall_candidate=r.wall_candidate,
                        physical_identity=SimpleNamespace(source_primitive_ids=("d999i0",)))
        for r in scope.records), equivalence=scope.equivalence)
    assert all(edge["kind"] == NO_WALL for row in ring_wall_identity_map(rings, foreign) for edge in row["edges"])


def test_results_are_deterministic_and_inputs_are_unchanged():
    scope, rings = _scope_and_rings(_double_rooms())
    before = [ring.polygon_pdf_pts for ring in rings]
    assert ring_wall_identity_map(rings, scope) == ring_wall_identity_map(rings, scope)
    assert [ring.polygon_pdf_pts for ring in rings] == before
