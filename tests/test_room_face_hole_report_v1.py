"""Report-only enclosures inside room faces (#4764 7211359981, geometry task C23). Synthetic only."""
from __future__ import annotations

import copy
import itertools
import math
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
from pb_room_face_hole_report_shadow import ENCLOSED_LOOP, NESTED_FACE, room_face_hole_report
from pb_source_room_face_authority import _derive_scope
from pb_source_visibility_authority import SourceVisibilityProducer


def _wall(wall_id, *points):
    return SimpleNamespace(wall_candidate_id=wall_id, wall_candidate=SimpleNamespace(centerline_pts=points))


def _face(face_id, points, walls):
    return SimpleNamespace(face_id=face_id, polygon_pdf_pts=tuple(points), bounding_wall_ids=tuple(walls))


def _square(prefix, x0, y0, x1, y1):
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [_wall(f"{prefix}{i}", corners[i], corners[(i + 1) % 4]) for i in range(4)], corners


def _scene(extra_walls=(), faces=None, transform=lambda p: p):
    walls, corners = _square("r", 0, 0, 100, 100)
    walls += list(extra_walls)
    walls = [_wall(w.wall_candidate_id, *[transform(p) for p in w.wall_candidate.centerline_pts]) for w in walls]
    faces = faces if faces is not None else [_face("room", corners, ["r0", "r1", "r2", "r3"])]
    faces = [_face(f.face_id, [transform(p) for p in f.polygon_pdf_pts], f.bounding_wall_ids) for f in faces]
    return (SimpleNamespace(page_id="1", records=tuple(walls)),
            SimpleNamespace(records=tuple(faces), abstained_faces=()))


def _only(report):
    (row,) = report["faces"]
    return row


def test_a_column_inside_a_room_is_a_hole_and_reduces_the_net_area():
    column, _ = _square("c", 40, 40, 50, 50)
    row = _only(room_face_hole_report(*_scene(column)))
    assert row["gross_area_pt2"] == pytest.approx(10000) and row["net_area_pt2"] == pytest.approx(9900)
    (hole,) = row["holes"]
    assert hole["kind"] == ENCLOSED_LOOP and hole["area_pt2"] == pytest.approx(100)
    assert hole["wall_ids"] == ["c0", "c1", "c2", "c3"]


def test_lines_crossing_past_the_corners_still_enclose_the_column():
    crossing = [_wall("x1", (38, 40), (52, 40)), _wall("x2", (50, 38), (50, 52)),
                _wall("x3", (52, 50), (38, 50)), _wall("x4", (40, 52), (40, 38))]
    row = _only(room_face_hole_report(*_scene(crossing)))
    assert row["net_area_pt2"] == pytest.approx(9900) and [h["wall_ids"] for h in row["holes"]] == [["x1", "x2", "x3", "x4"]]


def test_dangling_stubs_split_walls_and_nested_loops_do_not_change_the_hole():
    column, _ = _square("c", 40, 40, 50, 50)
    split = [_wall("c0a", (40, 40), (45, 40)), _wall("c0b", (45, 40), (50, 40))] + column[1:]
    stub = _wall("s", (50, 45), (60, 45))
    inner, _ = _square("i", 43, 43, 47, 47)
    base = _only(room_face_hole_report(*_scene(column)))
    for extra in (split, column + [stub], column + inner):
        row = _only(room_face_hole_report(*_scene(extra)))
        assert row["net_area_pt2"] == pytest.approx(base["net_area_pt2"]) and len(row["holes"]) == 1


@pytest.mark.parametrize("walls", [
    [_wall("l1", (40, 40), (60, 40)), _wall("l2", (60, 40), (60, 60))],          # open lines enclose nothing
    _square("o", 120, 120, 130, 130)[0],                                          # outside the room
    [_wall("t1", (0, 40), (10, 40)), _wall("t2", (10, 40), (10, 50)), _wall("t3", (10, 50), (0, 50)),
     _wall("t4", (0, 50), (0, 40))],                                              # touches the room boundary
], ids=["open", "outside", "touching"])
def test_look_alikes_are_not_holes(walls):
    row = _only(room_face_hole_report(*_scene(walls)))
    assert row["holes"] == [] and row["net_area_pt2"] == row["gross_area_pt2"]


def test_only_the_room_that_contains_the_column_is_reduced():
    column, _ = _square("c", 140, 40, 150, 50)
    other, corners = _square("q", 100, 0, 200, 100)
    faces = [_face("a", [(0, 0), (100, 0), (100, 100), (0, 100)], ["r0", "r1", "r2", "r3"]),
             _face("b", corners, [w.wall_candidate_id for w in other])]
    report = room_face_hole_report(*_scene(other + column, faces=faces))
    nets = {row["face_id"]: row["net_area_pt2"] for row in report["faces"]}
    assert nets == {"a": pytest.approx(10000), "b": pytest.approx(9900)} and report["faces_with_holes"] == 1


def test_an_inner_room_face_is_reported_as_a_hole_of_the_outer_one():
    inner, corners = _square("n", 20, 20, 40, 40)
    faces = [_face("outer", [(0, 0), (100, 0), (100, 100), (0, 100)], ["r0", "r1", "r2", "r3"]),
             _face("inner", corners, [w.wall_candidate_id for w in inner])]
    report = room_face_hole_report(*_scene(inner, faces=faces))
    rows = {row["face_id"]: row for row in report["faces"]}
    assert [hole["kind"] for hole in rows["outer"]["holes"]] == [NESTED_FACE]
    assert rows["outer"]["net_area_pt2"] == pytest.approx(9600) and rows["inner"]["holes"] == []


@pytest.mark.parametrize("transform, factor", [
    (lambda p: (p[0] + 512.25, p[1] - 31.5), 1.0), (lambda p: (p[0] * 2.5, p[1] * 2.5), 6.25),
    (lambda p: (-p[1], p[0]), 1.0),
    (lambda p: (p[0] * math.cos(0.3) - p[1] * math.sin(0.3), p[0] * math.sin(0.3) + p[1] * math.cos(0.3)), 1.0),
], ids=["translate", "scale", "rotate90", "rotate"])
def test_moving_the_whole_drawing_scales_only_the_areas(transform, factor):
    column, _ = _square("c", 40, 40, 50, 50)
    row = _only(room_face_hole_report(*_scene(column, transform=transform)))
    assert row["net_area_pt2"] == pytest.approx(9900 * factor, rel=1e-9) and len(row["holes"]) == 1


def test_input_order_does_not_matter_and_inputs_are_not_changed():
    column, _ = _square("c", 40, 40, 50, 50)
    reference = room_face_hole_report(*_scene(column))
    for order in itertools.islice(itertools.permutations(column), 8):
        assert room_face_hole_report(*_scene(list(order))) == reference
    scope, rooms = _scene(column)
    before = copy.deepcopy((scope, rooms))
    room_face_hole_report(scope, rooms)
    assert (scope, rooms) == before


def _two_rooms_with_a_column(tmp_path: Path):
    document = fitz.open()
    page = document.new_page(width=420, height=300)
    for first, second in (((50, 50), (350, 50)), ((350, 50), (350, 250)), ((350, 250), (50, 250)), ((50, 250), (50, 50)),
                          ((200, 50), (200, 250)), ((260, 120), (290, 120)), ((290, 120), (290, 150)),
                          ((290, 150), (260, 150)), ((260, 150), (260, 120))):
        page.draw_line(first, second, color=(0, 0, 0), width=1)
    data = document.tobytes()
    document.close()
    return data


def test_through_the_real_wall_and_room_authorities(tmp_path):
    source = SourceVisibilityProducer(producer_method="room-hole-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="holes", source_bytes=_two_rooms_with_a_column(tmp_path),
                                               source_locator="memory://holes.pdf", page_ids=("1",))
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    scope = authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id="holes", revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1", decision_scope_id=_decision_scope_id("1")))
    rooms = _derive_scope(scope)
    report = room_face_hole_report(scope, rooms)
    assert len(report["faces"]) == 2 and report["faces_with_holes"] == 1
    (reduced,) = [row for row in report["faces"] if row["holes"]]
    assert reduced["gross_area_pt2"] - reduced["net_area_pt2"] == pytest.approx(900, rel=1e-6)
