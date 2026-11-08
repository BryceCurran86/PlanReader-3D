"""Doorway flank members: an edge is lined only if EVERY drawn shape on it is a frame strip (shadow, noncommercial).

Predicted before the tests were written (the contract's expected abstentions):

* a doorway with no flank members still resolves (positive control);
* a thin cap on a frame run's face (at the doorway end or anywhere along the face), a mitred non-strip block at the
  doorway and the exposed end face of a wall stub each leave the face UNRESOLVED with no lining offset, whatever the
  drawing order, translation, run splitting or unrelated content;
* a run drawn as several abutting frame-thickness strips still resolves (no over-abstention);
* geometry the classifier cannot see abstains (``wall_edge_geometry_not_verifiable``), never resolves.

The ring builder names an edge's owners only at the edge midpoint, so before this guard the verdict depended on
where the midpoint fell: the same members resolved or not according to where a thin cap sat along the face.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_layered_wall_face_identity_shadow import (
    CLASS_EDGE_GEOMETRY_UNVERIFIABLE,
    CLASS_EDGE_NOT_COVERED,
    CLASS_END_FACE_NOT_CLASSIFIED,
    CLASS_FILL_NOT_CLASSIFIED,
    CLASS_LINED_INTERNAL_FRAME_FACE,
    CLASS_OWNERS_MIXED,
    CLASS_THRESHOLD_CHORD,
    VERDICT_RESOLVED,
    VERDICT_UNRESOLVED,
    WallStripFact,
    _classify_edges,
    classify_ring_face_identity,
    wall_strip_facts,
)

K = 0.5522847498
MM_PER_PT = 17.5  # 70 mm frame = 4.0 pt on this synthetic page
FRAME = 4.0
TOL = 0.01  # PDF coordinates are stored at about 1/1000 pt


def doorway_pdf(
    *,
    cap_pt: float = 0.0,
    cap_where: str = "end",
    block_on_face: bool = False,
    notch_fill: bool = False,
    stub: bool = False,
    split_run: bool = False,
    reverse: bool = False,
    far_walls: bool = False,
    ox: float = 0.0,
    oy: float = 0.0,
) -> bytes:
    """Room inner box (100,80)-(250,180); a swing doorway in the right wall closes the ring.

    ``cap_pt``: a full-wall-width cap of that length on the upper run's room face, at the doorway end
    (``cap_where='end'``) or in the middle of the run (``'middle'``).
    ``notch_fill``: a mitred non-strip block at the lower run's end (leaves the run's end face partly exposed).
    ``stub``: a frame-thickness wall stub hanging into the room from the top wall.
    ``block_on_face``: the same stub with a mitred non-strip block abutting its end (left side collinear with the stub's face).
    ``split_run``: the upper frame run is drawn as two abutting frame-thickness strips.
    """
    doc = fitz.open()
    page = doc.new_page(width=450.0 + ox + 60.0, height=350.0 + oy + 60.0)
    internal = doc.add_ocg("Enclosure_WallInternal", on=True)

    def rect(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0 + ox, y0 + oy, x1 + ox, y1 + oy), color=None, fill=(0, 0, 0), oc=internal)

    def polygon(points):
        shape = page.new_shape()
        shifted = [fitz.Point(x + ox, y + oy) for x, y in points]
        shape.draw_polyline(shifted + [shifted[0]])
        shape.finish(color=None, fill=(0, 0, 0), oc=internal, closePath=True)
        shape.commit()

    wall_end = 108.0  # the upper run ends here (doorway side)
    pieces: list[tuple[float, float]] = []  # (y0, y1) of every piece of the upper run, caps included
    if cap_pt and cap_where == "middle":
        pieces = [(80.0, 94.0), (94.0, 94.0 + cap_pt), (94.0 + cap_pt, wall_end)]
        door_start = wall_end
    elif cap_pt:
        pieces = [(80.0, wall_end), (wall_end, wall_end + cap_pt)]
        door_start = wall_end + cap_pt
    elif split_run:
        pieces = [(80.0, 94.0), (94.0, wall_end)]
        door_start = wall_end
    else:
        pieces = [(80.0, wall_end)]
        door_start = wall_end
    door_end = 138.0
    ops = [
        lambda: rect(96, 76, 254, 80),
        lambda: rect(96, 180, 254, 184),
        lambda: rect(96, 80, 100, 180),
        lambda: rect(250, 138, 254, 180),
    ]
    for y0, y1 in pieces:
        ops.append(lambda y0=y0, y1=y1: rect(250, y0, 254, y1))
    if block_on_face:  # a mitred non-strip block abutting the stub's end, its left side collinear with the stub's face
        ops.append(lambda: polygon([(150, 120), (154, 120), (152.5, 123), (150, 123)]))
    if notch_fill:
        ops.append(lambda: polygon([(250, 136.5), (254, 136.5), (254, 138), (252.8, 138)]))
        door_end = 136.5
    if stub or block_on_face:
        ops.append(lambda: rect(150, 80, 154, 120))
    if far_walls:
        ops.append(lambda: rect(300, 300, 340, 304))
        ops.append(lambda: rect(300, 300, 304, 330))
    for op in (reversed(ops) if reverse else ops):
        op()
    gap = door_end - door_start
    c, o, t = (250.0, door_start), (250.0 - gap, door_start), (250.0, door_end)
    p2 = (o[0] + K * (t[0] - c[0]), o[1] + K * (t[1] - c[1]))
    p3 = (t[0] + K * (o[0] - c[0]), t[1] + K * (o[1] - c[1]))
    page.draw_bezier(fitz.Point(o[0] + ox, o[1] + oy), fitz.Point(p2[0] + ox, p2[1] + oy),
                     fitz.Point(p3[0] + ox, p3[1] + oy), fitz.Point(t[0] + ox, t[1] + oy),
                     color=(0, 0, 0), width=0.34, oc=internal)
    page.draw_line(fitz.Point(c[0] + ox, c[1] + oy), fitz.Point(o[0] + ox, o[1] + oy), color=(0, 0, 0), width=0.34, oc=internal)
    return doc.tobytes()


def ring_and_facts(data: bytes):
    sha = hashlib.sha256(data).hexdigest()
    result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    candidates = [r for r in result.rings if r.status.value == "candidate"]
    assert len(candidates) == 1, [(r.status.value, r.reason_codes) for r in result.rings]
    facts = wall_strip_facts(fitz.open(stream=data, filetype="pdf")[0].get_drawings())
    return candidates[0], facts


def statement(frame=70.0, lining=10.0):
    return SimpleNamespace(scope="internal_walls", frame_mm=frame, lining_mm=lining, wet_area_lining_mm=None, text_sha256="a" * 64)


def identify(ring, facts):
    return classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)


def classes(identity):
    return dict(identity.class_lengths_pt)


def assert_unresolved_unlined_noncommercial(identity):
    assert identity.verdict == VERDICT_UNRESOLVED and identity.lined_edge_offsets_mm == ()
    assert (identity.takeoff_eligible, identity.commercial_projection_allowed, identity.metric_area_issued,
            identity.floor_finish_issued, identity.diagnostic_only) == (False, False, False, False, True)


def test_a_doorway_without_flank_members_still_resolves():
    identity = identify(*ring_and_facts(doorway_pdf()))
    assert identity.verdict == VERDICT_RESOLVED and identity.reason_codes == ()
    assert set(classes(identity)) == {CLASS_LINED_INTERNAL_FRAME_FACE, CLASS_THRESHOLD_CHORD}
    assert {offset for _edge, offset in identity.lined_edge_offsets_mm} == {10.0}


def test_the_owner_list_alone_cannot_see_a_cap_on_a_frame_runs_face():
    """Pins WHY the guard exists: the ring names only the run at the edge midpoint, yet the cap is on the edge."""
    ring, facts = ring_and_facts(doorway_pdf(cap_pt=1.417, cap_where="end"))
    edge = next(i for i, p in enumerate(ring.polygon_pdf_pts) if abs(p[0] - 250.0) < TOL and abs(p[1] - 109.417) < TOL)
    owners = ring.edge_owner_ids[edge]
    assert len(owners) == 1  # the run only
    caps = [i for i, f in facts.items() if len(f.shapes_pt) == 1 and f.shapes_pt[0][3] - f.shapes_pt[0][1] == pytest.approx(1.417, abs=TOL)]
    assert len(caps) == 1 and f"layered_wall_strip:{caps[0]}" not in owners


@pytest.mark.parametrize("cap_where", ["end", "middle"])
@pytest.mark.parametrize("cap_pt", [0.28, 1.417, 2.0, 3.9])
def test_a_thin_cap_on_the_same_face_leaves_the_face_unresolved_wherever_it_sits(cap_pt, cap_where):
    identity = identify(*ring_and_facts(doorway_pdf(cap_pt=cap_pt, cap_where=cap_where)))
    assert_unresolved_unlined_noncommercial(identity)
    lengths = classes(identity)
    # the whole face (run + cap) is ONE unresolved edge; none of it is counted as a lined face
    edge_len = 28.0 + (cap_pt if cap_where == "end" else 0.0)
    assert lengths[CLASS_OWNERS_MIXED] == pytest.approx(edge_len, abs=TOL)


def test_the_verdict_does_not_depend_on_where_a_cap_sits_along_the_face():
    """Before the guard a cap at the edge midpoint made the face unresolved and a cap elsewhere did not."""
    at_end = identify(*ring_and_facts(doorway_pdf(cap_pt=1.0, cap_where="end")))
    in_middle = identify(*ring_and_facts(doorway_pdf(cap_pt=1.0, cap_where="middle")))
    assert at_end.verdict == in_middle.verdict == VERDICT_UNRESOLVED
    assert at_end.lined_edge_offsets_mm == in_middle.lined_edge_offsets_mm == ()


def test_a_frame_thickness_square_member_is_not_a_long_face():
    """A square block on the face has no run direction (a post, not a wall): it is never a lined face."""
    identity = identify(*ring_and_facts(doorway_pdf(cap_pt=FRAME, cap_where="end")))
    assert_unresolved_unlined_noncommercial(identity)


def test_a_mitred_non_strip_block_stays_its_own_unclassified_edge_and_exposes_the_run_end_face():
    identity = identify(*ring_and_facts(doorway_pdf(notch_fill=True)))
    assert_unresolved_unlined_noncommercial(identity)
    lengths = classes(identity)
    assert lengths[CLASS_FILL_NOT_CLASSIFIED] == pytest.approx(3.1765, abs=0.001)
    # the exposed end face of the lower run (2.8 pt) is not a lined face; it shares its edge with the block's face
    assert lengths[CLASS_OWNERS_MIXED] == pytest.approx(2.8, abs=0.001)


def test_a_non_strip_block_on_a_frame_runs_face_is_a_member_the_owner_list_does_not_name():
    ring, facts = ring_and_facts(doorway_pdf(block_on_face=True))
    identity = identify(ring, facts)
    assert_unresolved_unlined_noncommercial(identity)
    # stub face (40) + the block's collinear side (3) form one edge; the ring's owner list names only the stub
    assert classes(identity)[CLASS_OWNERS_MIXED] == pytest.approx(43.0, abs=TOL)
    assert CLASS_FILL_NOT_CLASSIFIED in classes(identity)
    n = len(ring.polygon_pdf_pts)
    edge = next(i for i, p in enumerate(ring.polygon_pdf_pts)
                if abs(p[0] - 150.0) < TOL and abs(ring.polygon_pdf_pts[(i + 1) % n][0] - 150.0) < TOL
                and abs(abs(p[1] - ring.polygon_pdf_pts[(i + 1) % n][1]) - 43.0) < TOL)
    assert len(ring.edge_owner_ids[edge]) == 1 and ring.edge_owner_ids[edge][0].startswith("layered_wall_strip:")


def test_the_end_face_of_a_frame_thickness_wall_stub_is_not_a_lined_face():
    ring, facts = ring_and_facts(doorway_pdf(stub=True))
    identity = identify(ring, facts)
    assert_unresolved_unlined_noncommercial(identity)
    lengths = classes(identity)
    assert lengths[CLASS_END_FACE_NOT_CLASSIFIED] == pytest.approx(FRAME, abs=TOL)  # the stub's end, 4 pt
    # the stub's two long sides and every other long face are still lined faces
    assert lengths[CLASS_LINED_INTERNAL_FRAME_FACE] > 400.0
    # the owner list alone calls the end face a frame strip (the old verdict): that is the false-lining it prevents
    end_edge = next(i for i, p in enumerate(ring.polygon_pdf_pts) if abs(p[1] - 120.0) < TOL and abs(ring.polygon_pdf_pts[(i + 1) % len(ring.polygon_pdf_pts)][1] - 120.0) < TOL)
    assert len(ring.edge_owner_ids[end_edge]) == 1


def test_both_flank_members_leave_both_marks_and_no_lining_anywhere():
    identity = identify(*ring_and_facts(doorway_pdf(cap_pt=1.417, notch_fill=True)))
    assert_unresolved_unlined_noncommercial(identity)
    lengths = classes(identity)
    assert CLASS_FILL_NOT_CLASSIFIED in lengths and CLASS_OWNERS_MIXED in lengths
    assert identity.chord_edge_count == 1


def test_a_run_drawn_as_abutting_frame_strips_is_not_over_abstained():
    split = identify(*ring_and_facts(doorway_pdf(split_run=True)))
    assert split.verdict == VERDICT_RESOLVED and split.reason_codes == ()
    assert {offset for _e, offset in split.lined_edge_offsets_mm} == {10.0}


SCENARIOS = [
    dict(cap_pt=1.417), dict(cap_pt=1.417, cap_where="middle"), dict(notch_fill=True), dict(cap_pt=1.417, notch_fill=True),
    dict(stub=True), dict(split_run=True), dict(block_on_face=True), dict(),
]


@pytest.mark.parametrize("kwargs", SCENARIOS)
def test_verdict_and_class_lengths_are_invariant_to_drawing_order_translation_and_unrelated_content(kwargs):
    base = identify(*ring_and_facts(doorway_pdf(**kwargs)))
    for variant in (dict(reverse=True), dict(ox=37.5, oy=12.25), dict(far_walls=True), dict(reverse=True, ox=11.0, oy=3.5, far_walls=True)):
        other = identify(*ring_and_facts(doorway_pdf(**kwargs, **variant)))
        assert other.verdict == base.verdict, (kwargs, variant)
        assert other.reason_codes == base.reason_codes, (kwargs, variant)
        assert [name for name, _ in other.class_lengths_pt] == [name for name, _ in base.class_lengths_pt], (kwargs, variant)
        for (_n, got), (_m, want) in zip(other.class_lengths_pt, base.class_lengths_pt):
            assert got == pytest.approx(want, abs=TOL), (kwargs, variant)
        assert (other.lined_edge_offsets_mm == ()) == (base.lined_edge_offsets_mm == ())


def test_geometry_the_classifier_cannot_see_abstains_never_resolves():
    ring, facts = ring_and_facts(doorway_pdf())
    assert identify(ring, facts).verdict == VERDICT_RESOLVED
    blind = {index: replace(fact, shapes_pt=()) for index, fact in facts.items()}
    identity = identify(ring, blind)
    assert_unresolved_unlined_noncommercial(identity)
    assert set(classes(identity)) == {CLASS_EDGE_GEOMETRY_UNVERIFIABLE, CLASS_THRESHOLD_CHORD}


def test_a_shape_beside_the_room_does_not_become_a_member_of_its_edges():
    base = identify(*ring_and_facts(doorway_pdf()))
    far = identify(*ring_and_facts(doorway_pdf(far_walls=True)))
    assert far.verdict == VERDICT_RESOLVED and far.class_lengths_pt == base.class_lengths_pt


def test_every_shape_of_a_multi_shape_path_is_judged_not_just_the_last():
    """One drawing path holding a frame rectangle and a thin cap: the path-level thickness is only the last strip's."""
    doc = fitz.open()
    page = doc.new_page(width=450.0, height=350.0)
    internal = doc.add_ocg("Enclosure_WallInternal", on=True)

    def rect(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=(0, 0, 0), oc=internal)

    rect(96, 76, 254, 80)
    rect(96, 180, 254, 184)
    rect(96, 80, 100, 180)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(250, 80, 254, 108))       # the frame run
    shape.draw_rect(fitz.Rect(250, 108, 254, 109.5))    # a thin cap in the SAME drawing path
    shape.finish(color=None, fill=(0, 0, 0), oc=internal)
    shape.commit()
    rect(250, 138, 254, 180)
    c, o, t = (250.0, 109.5), (250.0 - 28.5, 109.5), (250.0, 138.0)
    p2 = (o[0] + K * (t[0] - c[0]), o[1] + K * (t[1] - c[1]))
    p3 = (t[0] + K * (o[0] - c[0]), t[1] + K * (o[1] - c[1]))
    page.draw_bezier(fitz.Point(*o), fitz.Point(*p2), fitz.Point(*p3), fitz.Point(*t), color=(0, 0, 0), width=0.34, oc=internal)
    page.draw_line(fitz.Point(*c), fitz.Point(*o), color=(0, 0, 0), width=0.34, oc=internal)
    ring, facts = ring_and_facts(doc.tobytes())
    multi = [f for f in facts.values() if len(f.shapes_pt) > 1]
    assert len(multi) == 1 and len(multi[0].shapes_pt) == 2
    assert_unresolved_unlined_noncommercial(identify(ring, facts))


def _unit(points, owners, shapes, *, mm_per_pt=MM_PER_PT, extra=()):
    facts = {0: WallStripFact(0, "Enclosure_WallInternal", True, FRAME, tuple(shapes))}
    for position, (layer, shape) in enumerate(extra, start=1):
        facts[position] = WallStripFact(position, layer, True, min(shape[2] - shape[0], shape[3] - shape[1]), (shape,))
    return _classify_edges("r", points, tuple(("layered_wall_strip:0",) for _ in owners), strip_facts=facts,
                           statements=[statement()], mm_per_pt=mm_per_pt)


LONG_FACE = ((0.0, 0.0, FRAME, 100.0, True),)  # a vertical frame strip, x in [0,4], y in [0,100]


def test_edge_level_only_an_axis_aligned_edge_along_a_strips_long_axis_is_lined():
    straight = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], LONG_FACE)
    assert classes(straight) == {CLASS_LINED_INTERNAL_FRAME_FACE: 200.0}
    across = _unit([(0.0, 0.0), (FRAME, 0.0)], [0, 1], LONG_FACE)
    assert classes(across) == {CLASS_END_FACE_NOT_CLASSIFIED: 2 * FRAME} and across.lined_edge_offsets_mm == ()
    slanted = _unit([(0.0, 0.0), (FRAME, 30.0)], [0, 1], LONG_FACE)
    assert set(classes(slanted)) == {CLASS_END_FACE_NOT_CLASSIFIED} and slanted.lined_edge_offsets_mm == ()
    degenerate = _unit([(0.0, 5.0), (0.0, 5.0)], [0, 1], LONG_FACE)
    assert set(classes(degenerate)) == {CLASS_END_FACE_NOT_CLASSIFIED} and degenerate.lined_edge_offsets_mm == ()


def test_edge_level_an_edge_longer_than_the_members_that_cover_it_is_not_lined():
    covered = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], LONG_FACE)
    assert covered.verdict == VERDICT_RESOLVED
    short = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], ((0.0, 0.0, FRAME, 60.0, True),))
    assert classes(short) == {CLASS_EDGE_NOT_COVERED: 200.0} and short.lined_edge_offsets_mm == ()
    tolerated = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], ((0.0, 0.0, FRAME, 100.0 - 0.04, True),))
    assert tolerated.verdict == VERDICT_RESOLVED  # a gap below the representation noise is not a gap


def test_edge_level_two_abutting_frame_members_cover_an_edge_and_a_hole_between_them_does_not():
    abutting = ((0.0, 0.0, FRAME, 60.0, True), (0.0, 60.0, FRAME, 100.0, True))
    assert _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], abutting).verdict == VERDICT_RESOLVED
    holed = ((0.0, 0.0, FRAME, 50.0, True), (0.0, 60.0, FRAME, 100.0, True))
    result = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], holed)
    assert classes(result) == {CLASS_EDGE_NOT_COVERED: 200.0}
    noise_gap = ((0.0, 0.0, FRAME, 60.0, True), (0.0, 60.04, FRAME, 100.0, True))
    assert _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], noise_gap).verdict == VERDICT_RESOLVED  # below the noise: not a gap
    over_noise = ((0.0, 0.0, FRAME, 60.0, True), (0.0, 60.2, FRAME, 100.0, True))
    assert classes(_unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], over_noise)) == {CLASS_EDGE_NOT_COVERED: 200.0}


def test_edge_level_a_member_of_another_class_on_the_edge_makes_it_mixed():
    square_sliver = ((0.0, 0.0, FRAME, 100.0, True), (0.0, 40.0, 1.5, 41.5, True))
    result = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], square_sliver)
    assert classes(result) == {CLASS_OWNERS_MIXED: 200.0} and result.lined_edge_offsets_mm == ()
    # a thin strip that runs PARALLEL to the face: only its thickness (not its direction) separates it from the frame
    thin_parallel = ((0.0, 0.0, FRAME, 100.0, True), (0.0, 40.0, 1.5, 60.0, True))
    result = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], thin_parallel)
    assert classes(result) == {CLASS_OWNERS_MIXED: 200.0} and result.lined_edge_offsets_mm == ()
    # the same strip at the frame thickness is just more frame
    frame_parallel = ((0.0, 0.0, FRAME, 100.0, True), (0.0, 40.0, FRAME, 60.0, True))
    assert _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], frame_parallel).verdict == VERDICT_RESOLVED


def test_edge_level_an_external_wall_member_on_the_edge_makes_it_mixed():
    external = ("Enclosure_WallExternal", (0.0, 40.0, FRAME + 2.0, 60.0, True))  # a 6 pt external strip sharing the face
    result = _unit([(0.0, 0.0), (0.0, 100.0)], [0, 1], LONG_FACE, extra=[external])
    assert classes(result) == {CLASS_OWNERS_MIXED: 200.0} and result.lined_edge_offsets_mm == ()


def test_classification_never_mutates_its_inputs_and_replays_identically():
    ring, facts = ring_and_facts(doorway_pdf(cap_pt=1.417, notch_fill=True))
    before = (repr(ring), repr(sorted(facts.items())))
    first = identify(ring, facts)
    second = identify(ring, dict(reversed(list(facts.items()))))
    assert first == second
    assert (repr(ring), repr(sorted(facts.items()))) == before
