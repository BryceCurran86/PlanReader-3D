"""Face identity of a doorway-closed ring: frame face with a stated lining, or an explicit unresolved reason."""
from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes
from pb_layered_wall_face_identity_shadow import (
    CLASS_EXTERNAL_DRAWN_INNER_FACE,
    CLASS_EXTERNAL_LINING_NOT_STATED,
    CLASS_FILL_NOT_CLASSIFIED,
    CLASS_INTERNAL_STATEMENT_UNUSABLE,
    CLASS_INTERNAL_THICKNESS_MISMATCH,
    CLASS_LAYER_NOT_CLASSIFIED,
    CLASS_LINED_INTERNAL_FRAME_FACE,
    CLASS_OWNER_UNKNOWN,
    CLASS_OWNERS_MIXED,
    CLASS_THRESHOLD_CHORD,
    REASON_NO_WALL_EDGES,
    REASON_SCALE_UNAVAILABLE,
    REASON_STATEMENT_UNAVAILABLE,
    REASON_STATEMENTS_CONFLICT,
    REASON_WET_AREA_STATUS,
    VERDICT_RESOLVED,
    VERDICT_UNRESOLVED,
    WallStripFact,
    apply_lined_finished_face_polygon,
    classify_ring_face_identity,
    wall_strip_facts,
)

K = 0.5522847498
MM_PER_PT = 17.5  # 70 mm frame = 4.0 pt on this synthetic page


def identity_pdf(*, right_layer: str = "Enclosure_WallInternal", right_pt: float = 4.0, top_pt: float = 4.0,
                 ox: float = 0.0, oy: float = 0.0) -> bytes:
    """Room inner box (100,80)-(250,180); a swing doorway in the right wall closes the ring."""
    doc = fitz.open()
    page = doc.new_page(width=450.0 + ox, height=350.0 + oy)
    internal = doc.add_ocg("Enclosure_WallInternal", on=True)
    right = internal if right_layer == "Enclosure_WallInternal" else doc.add_ocg(right_layer, on=True)

    def rect(x0, y0, x1, y1, oc):
        page.draw_rect(fitz.Rect(x0 + ox, y0 + oy, x1 + ox, y1 + oy), color=None, fill=(0, 0, 0), oc=oc)

    rect(96, 80 - top_pt, 250 + right_pt, 80, internal)
    rect(96, 180, 250 + right_pt, 184, internal)
    rect(96, 80, 100, 180, internal)
    rect(250, 80, 250 + right_pt, 110, right)
    rect(250, 134, 250 + right_pt, 180, right)
    c, o, t = (250, 110), (226, 110), (250, 134)
    p2 = (o[0] + K * (t[0] - c[0]), o[1] + K * (t[1] - c[1]))
    p3 = (t[0] + K * (o[0] - c[0]), t[1] + K * (o[1] - c[1]))
    page.draw_bezier(fitz.Point(o[0] + ox, o[1] + oy), fitz.Point(p2[0] + ox, p2[1] + oy),
                     fitz.Point(p3[0] + ox, p3[1] + oy), fitz.Point(t[0] + ox, t[1] + oy),
                     color=(0, 0, 0), width=0.34, oc=internal)
    page.draw_line(fitz.Point(c[0] + ox, c[1] + oy), fitz.Point(o[0] + ox, o[1] + oy), color=(0, 0, 0), width=0.34, oc=internal)
    return doc.tobytes()


def _ring_and_facts(data: bytes):
    sha = hashlib.sha256(data).hexdigest()
    ring_result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    ring, = [r for r in ring_result.rings if r.status.value == "candidate"]
    facts = wall_strip_facts(fitz.open(stream=data, filetype="pdf")[0].get_drawings())
    return ring, facts


def statement(frame=70.0, lining=10.0, wet=None, text="a" * 64):
    return SimpleNamespace(scope="internal_walls", frame_mm=frame, lining_mm=lining, wet_area_lining_mm=wet, text_sha256=text)


def classes(identity):
    return dict(identity.class_lengths_pt)


@pytest.fixture(scope="module")
def base():
    return _ring_and_facts(identity_pdf())


def test_every_wall_edge_a_lined_internal_frame_face_resolves_with_the_stated_lining_offset(base):
    ring, facts = base
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert identity.verdict == VERDICT_RESOLVED and identity.reason_codes == ()
    assert set(classes(identity)) == {CLASS_LINED_INTERNAL_FRAME_FACE, CLASS_THRESHOLD_CHORD}
    assert identity.chord_edge_count == 1 and identity.wall_edge_count == len(identity.lined_edge_offsets_mm) > 0
    assert {offset for _edge, offset in identity.lined_edge_offsets_mm} == {10.0}
    assert (identity.takeoff_eligible, identity.commercial_projection_allowed, identity.metric_area_issued,
            identity.floor_finish_issued, identity.diagnostic_only) == (False, False, False, False, True)


def test_an_external_wall_run_whose_lining_the_set_does_not_state_is_the_drawn_inner_face():
    ring, facts = _ring_and_facts(identity_pdf(right_layer="Enclosure_WallExternal", right_pt=90.0 / MM_PER_PT))
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert identity.verdict == VERDICT_RESOLVED and identity.reason_codes == ()
    lengths = classes(identity)
    assert lengths[CLASS_EXTERNAL_DRAWN_INNER_FACE] == pytest.approx(30.0 + 46.0, abs=0.01)
    assert lengths[CLASS_LINED_INTERNAL_FRAME_FACE] > 0
    assert {offset for _edge, offset in identity.lined_edge_offsets_mm} == {10.0}
    assert CLASS_EXTERNAL_LINING_NOT_STATED not in identity.reason_codes


def test_an_internal_strip_that_is_not_the_stated_frame_thickness_is_not_resolved():
    ring, facts = _ring_and_facts(identity_pdf(top_pt=40.0 / MM_PER_PT))
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert identity.verdict == VERDICT_UNRESOLVED and CLASS_INTERNAL_THICKNESS_MISMATCH in identity.reason_codes


@pytest.mark.parametrize("pt, resolved", [(4.0, True), (4.03, True), (4.0 - 0.03, True), (4.07, False), (3.93, False)])
def test_thickness_match_is_bounded_by_the_representation_noise_at_the_page_scale(pt, resolved):
    ring, facts = _ring_and_facts(identity_pdf(top_pt=pt))
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert (identity.verdict == VERDICT_RESOLVED) is resolved


def test_no_statement_or_conflicting_statements_never_resolve_and_never_guess_a_lining(base):
    ring, facts = base
    none = classify_ring_face_identity(ring, strip_facts=facts, statements=[], mm_per_pt=MM_PER_PT)
    assert none.verdict == VERDICT_UNRESOLVED
    assert REASON_STATEMENT_UNAVAILABLE in none.reason_codes and CLASS_INTERNAL_STATEMENT_UNUSABLE in none.reason_codes
    assert none.lined_edge_offsets_mm == ()
    conflict = classify_ring_face_identity(
        ring, strip_facts=facts, statements=[statement(70.0, 10.0), statement(90.0, 13.0)], mm_per_pt=MM_PER_PT)
    assert conflict.verdict == VERDICT_UNRESOLVED and REASON_STATEMENTS_CONFLICT in conflict.reason_codes
    same_frame_other_lining = classify_ring_face_identity(
        ring, strip_facts=facts, statements=[statement(70.0, 10.0), statement(70.0, 13.0)], mm_per_pt=MM_PER_PT)
    assert same_frame_other_lining.verdict == VERDICT_UNRESOLVED and REASON_STATEMENTS_CONFLICT in same_frame_other_lining.reason_codes
    other_scope = SimpleNamespace(scope="external_walls", frame_mm=70.0, lining_mm=10.0, wet_area_lining_mm=None, text_sha256="b" * 64)
    assert classify_ring_face_identity(ring, strip_facts=facts, statements=[other_scope], mm_per_pt=MM_PER_PT).verdict == VERDICT_UNRESOLVED


@pytest.mark.parametrize("scale", [None, 0.0, -1.0, math.nan, math.inf])
def test_without_a_usable_page_scale_no_thickness_can_be_judged(base, scale):
    ring, facts = base
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=scale)
    assert identity.verdict == VERDICT_UNRESOLVED and REASON_SCALE_UNAVAILABLE in identity.reason_codes


def test_a_wet_area_variant_leaves_the_lining_open_unless_an_authority_says_the_room_is_dry(base):
    ring, facts = base
    wet = [statement(70.0, 10.0, wet=6.0)]
    assert REASON_WET_AREA_STATUS in classify_ring_face_identity(ring, strip_facts=facts, statements=wet, mm_per_pt=MM_PER_PT).reason_codes
    assert REASON_WET_AREA_STATUS in classify_ring_face_identity(
        ring, strip_facts=facts, statements=wet, mm_per_pt=MM_PER_PT, room_is_wet_area=True).reason_codes
    dry = classify_ring_face_identity(ring, strip_facts=facts, statements=wet, mm_per_pt=MM_PER_PT, room_is_wet_area=False)
    assert dry.verdict == VERDICT_RESOLVED
    # the dry-room offset is the general lining, never the wet-area one
    assert {offset for _e, offset in dry.lined_edge_offsets_mm} == {10.0}


def test_unknown_unclassified_and_mixed_owners_are_each_a_distinct_unresolved_class(base):
    ring, facts = base
    wall_edge = next(i for i, o in enumerate(ring.edge_owner_ids) if o and not o[0].startswith("layered_doorway_closure:"))
    owners = list(ring.edge_owner_ids)

    def with_owner(value):
        edited = list(owners)
        edited[wall_edge] = value
        return replace(ring, edge_owner_ids=tuple(edited))

    first_owner = owners[wall_edge][0]
    unknown = classify_ring_face_identity(with_owner(("layered_wall_strip:999999",)), strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert CLASS_OWNER_UNKNOWN in unknown.reason_codes
    fill = classify_ring_face_identity(with_owner(("layered_wall_fill:7",)), strip_facts={**facts, 7: WallStripFact(7, "Enclosure_WallInternal", False, None)},
                                       statements=[statement()], mm_per_pt=MM_PER_PT)
    assert CLASS_FILL_NOT_CLASSIFIED in fill.reason_codes
    other_layer = {**facts, 999: WallStripFact(999, "Interior_Joinery", True, 4.0)}
    assert CLASS_LAYER_NOT_CLASSIFIED in classify_ring_face_identity(
        with_owner(("layered_wall_strip:999",)), strip_facts=other_layer, statements=[statement()], mm_per_pt=MM_PER_PT).reason_codes
    external = {**facts, 998: WallStripFact(998, "Enclosure_WallExternal", True, 5.0)}
    mixed = classify_ring_face_identity(
        with_owner((first_owner, "layered_wall_strip:998")), strip_facts=external, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert CLASS_OWNERS_MIXED in mixed.reason_codes
    # a malformed owner id is an unknown owner, not an exception
    assert CLASS_OWNER_UNKNOWN in classify_ring_face_identity(
        with_owner(("layered_wall_strip:abc",)), strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT).reason_codes


def test_a_ring_with_no_wall_edge_has_nothing_to_resolve(base):
    ring, facts = base
    chords_only = replace(ring, edge_owner_ids=tuple(("layered_doorway_closure:x",) for _ in ring.polygon_pdf_pts))
    identity = classify_ring_face_identity(chords_only, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    assert identity.verdict == VERDICT_UNRESOLVED and REASON_NO_WALL_EDGES in identity.reason_codes
    missing_owners = replace(ring, edge_owner_ids=())
    assert classify_ring_face_identity(missing_owners, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT).verdict == VERDICT_UNRESOLVED


def test_replay_is_deterministic_statement_order_invariant_and_translation_invariant(base):
    ring, facts = base
    a = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement(text="a" * 64), statement(text="b" * 64)], mm_per_pt=MM_PER_PT)
    b = classify_ring_face_identity(ring, strip_facts=dict(reversed(list(facts.items()))),
                                    statements=[statement(text="b" * 64), statement(text="a" * 64)], mm_per_pt=MM_PER_PT)
    assert a == b and a.verdict == VERDICT_RESOLVED
    moved_ring, moved_facts = _ring_and_facts(identity_pdf(ox=37.5, oy=12.25))
    moved = classify_ring_face_identity(moved_ring, strip_facts=moved_facts, statements=[statement(text="a" * 64), statement(text="b" * 64)], mm_per_pt=MM_PER_PT)
    assert moved.verdict == a.verdict and moved.class_lengths_pt == a.class_lengths_pt
    assert classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT).lined_edge_offsets_mm == \
        classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT).lined_edge_offsets_mm


def test_finished_polygon_insets_only_authenticated_lining_edges(base):
    ring, facts = base
    identity = classify_ring_face_identity(ring, strip_facts=facts, statements=[statement()], mm_per_pt=MM_PER_PT)
    finished = apply_lined_finished_face_polygon(
        ring.polygon_pdf_pts, identity.lined_edge_offsets_mm, MM_PER_PT,
    )
    assert finished is not None
    from shapely.geometry import Polygon
    original = Polygon(ring.polygon_pdf_pts)
    inset = Polygon(finished)
    assert inset.is_valid and inset.area < original.area
    assert apply_lined_finished_face_polygon(ring.polygon_pdf_pts, (), MM_PER_PT) == tuple(
        (float(x), float(y)) for x, y in ring.polygon_pdf_pts
    )
    assert apply_lined_finished_face_polygon(ring.polygon_pdf_pts, identity.lined_edge_offsets_mm, 0.0) is None


def test_strip_facts_carry_layer_and_thickness_and_never_mutate_the_drawings():
    data = identity_pdf(right_layer="Enclosure_WallExternal", right_pt=5.0)
    drawings = fitz.open(stream=data, filetype="pdf")[0].get_drawings()
    before = repr(drawings)
    facts = wall_strip_facts(drawings)
    assert repr(drawings) == before
    layers = {f.layer for f in facts.values()}
    assert {"Enclosure_WallInternal", "Enclosure_WallExternal"} <= layers
    assert all(f.thickness_pt is not None and f.thickness_pt > 0 for f in facts.values() if f.is_strip)
