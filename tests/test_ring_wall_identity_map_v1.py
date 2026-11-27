"""Report-only map from layered ring edges to physical wall candidates (#4764 7219675205, C06/C08). Synthetic only."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
from pb_ring_wall_identity_map_shadow import AMBIGUOUS_ONLY, CLOSURE_EDGE, NO_WALL, PUBLISHED, ring_wall_identity_map
from pb_source_visibility_authority import SourceVisibilityProducer

BLACK = (0, 0, 0)


def _double_rooms(*, door=True, width=0.7):
    """Two rooms in double-line walls; the shared wall has a 30 pt doorway with jambs."""
    document = fitz.open()
    page = document.new_page(width=600, height=400)

    def line(a, b):
        page.draw_line(a, b, color=BLACK, width=width)

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


def _split_line_rooms(width, shift=(0.0, 0.0), turn=False, reverse=False):
    """Two rooms in SINGLE-line walls, each side drawn as two source paths: the builder bands the line itself."""
    document = fitz.open()
    page = document.new_page(width=600, height=400)
    pieces = []
    for a, b in (((50, 50), (330, 50)), ((330, 50), (330, 230)), ((330, 230), (50, 230)), ((50, 230), (50, 50)),
                 ((190, 50), (190, 230))):
        middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        pieces += [(a, middle), (middle, b)]
    for ends in (pieces[::-1] if reverse else pieces):
        moved = [(x + shift[0], y + shift[1]) for x, y in ends]
        page.draw_line(*([(400 - y, x) for x, y in moved] if turn else moved), color=BLACK, width=width)
    data = document.tobytes()
    document.close()
    return data


def _drawings(data):
    with fitz.open(stream=data, filetype="pdf") as document:
        return document[0].get_drawings()


@pytest.mark.parametrize("width,face_offset", [(0.5, 0.6), (2.0, 1.0)])
@pytest.mark.parametrize("shift", [(0.0, 0.0), (37.25, 11.75)])
def test_a_face_half_a_stroke_strip_from_the_wall_line_maps_only_with_the_source_rows(width, face_offset, shift):
    data = _split_line_rooms(width, shift)
    scope, rings = _scope_and_rings(data)
    assert len(rings) == 2
    without = ring_wall_identity_map(rings, scope)
    assert [row["counts"][NO_WALL] for row in without] == [4, 4]
    rows = ring_wall_identity_map(rings, scope, drawings=_drawings(data))
    assert [row["counts"][NO_WALL] for row in rows] == [0, 0]
    records = {r.wall_candidate_id: r.wall_candidate for r in scope.records}
    for ring, row in zip(rings, rows):
        points = [tuple(p) for p in ring.polygon_pdf_pts]
        centre = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
        for (a, b), edge in zip(zip(points, points[1:] + points[:1]), row["edges"]):
            axis = 0 if abs(a[1] - b[1]) < abs(a[0] - b[0]) else 1
            coordinate = a[1 - axis]
            outward = 1.0 if coordinate > centre[1 - axis] else -1.0
            assert edge["wall_ids"]
            for wall_id in edge["wall_ids"]:  # the line behind this face, exactly the builder's offset away
                assert all(abs(p[1 - axis] - (coordinate + outward * face_offset)) < 0.05
                           for p in records[wall_id].centerline_pts)


def _link_shape(data):
    scope, rings = _scope_and_rings(data)
    rows = ring_wall_identity_map(rings, scope, drawings=_drawings(data))
    return sorted((tuple(sorted(row["counts"].items())), tuple(sorted(len(edge["wall_ids"]) for edge in row["edges"])))
                  for row in rows)


@pytest.mark.parametrize("turn", [False, True], ids=["flat", "turned"])
@pytest.mark.parametrize("reverse", [False, True], ids=["drawn", "reversed"])
def test_the_links_do_not_depend_on_drawing_order_or_a_quarter_turn(turn, reverse):
    shape = _link_shape(_split_line_rooms(0.5, turn=turn, reverse=reverse))
    assert shape == _link_shape(_split_line_rooms(0.5))
    assert len(shape) == 2 and all(dict(counts)[NO_WALL] == 0 for counts, _links in shape)


def _one_edge_probe(line_x, *, width=0.5, second_x=None, end_x=None, fill=None):
    """A 100 x 100 room whose left face is at x=10; made-up candidates on its owner path, running along that face."""
    ring = SimpleNamespace(record_id="r", status=SimpleNamespace(value="candidate"),
                           polygon_pdf_pts=((10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0)),
                           edge_owner_ids=((), (), (), ("layered_wall_strip:0",)))
    xs = [line_x] if second_x is None else [line_x, second_x]
    scope = SimpleNamespace(equivalence=None, records=tuple(
        SimpleNamespace(wall_candidate_id=f"w{i}", wall_candidate=SimpleNamespace(
                            centerline_pts=((x, 20.0), (x if end_x is None else end_x, 90.0))),
                        physical_identity=SimpleNamespace(source_primitive_ids=("d0i0",)))
        for i, x in enumerate(xs)))
    rows = ring_wall_identity_map([ring], scope, drawings=[{"color": BLACK, "fill": fill, "width": width}])
    return rows[0]["edges"][3]["wall_ids"]


def test_only_lines_on_the_face_or_behind_it_within_the_strip_are_listed_and_none_is_chosen():
    assert _one_edge_probe(10.0) == ["w0"]  # drawn on the face itself
    assert _one_edge_probe(9.4) == ["w0"]  # 0.6 behind: the face of a thin stroke's strip
    assert _one_edge_probe(10.6) == []  # the same distance on the ROOM side is not this face
    assert _one_edge_probe(8.5) == []  # further behind than the builder ever puts it
    assert _one_edge_probe(7.0, width=6.0) == ["w0"]  # a 6 pt stroke's face is 3 pt from its line
    assert _one_edge_probe(9.4, second_x=10.0) == ["w0", "w1"]  # both kept: the ambiguity is reported
    assert _one_edge_probe(9.4, end_x=10.0) == []  # a slanted line across the strip is not this face's line
    assert _one_edge_probe(9.4, fill=BLACK) == []  # a filled shape's face is its own outline, nothing behind it
