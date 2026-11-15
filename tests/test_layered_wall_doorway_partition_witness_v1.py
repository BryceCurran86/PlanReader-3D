"""Opt-in sliding-leaf partition witness (MAX decision 6703504968): topology only, default-off, abstains on any doubt.

A room split by a sliding-leaf front into a bedroom face and a wardrobe-alcove face has no printed figure
for either part. The PAIR does: the union's outer envelope may equal exactly one authenticated figured
(horizontal, vertical) pair. That equality is a topology cross-check; it is never a part's area, scale or
quantity, and a part is never judged by its own bounding box.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from functools import lru_cache
from types import SimpleNamespace

import fitz
import pytest
from shapely.geometry import Polygon

from pb_layered_wall_doorway_partition_witness_shadow import (
    REASON_CHORD,
    REASON_FOREIGN,
    REASON_HOLE,
    REASON_ID_COLLISION,
    REASON_MEMBERSHIP,
    REASON_MIXED,
    REASON_OPEN_MEMBER,
    REASON_OVERLAP,
    partition_groups,
)
from pb_layered_wall_doorway_room_face_scope_shadow import (
    LAYERED_RING_PARTITION_REASON,
    LAYERED_RING_SCOPE_REASON,
    RING_NOT_A_RECTANGLE_PREFIX,
    RING_PARTITION_PART_PREFIX,
    layered_ring_room_face_scope,
    layered_ring_scope_overrides,
)
from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_SLIDING_LEAF,
    KIND_STROKE,
    KIND_SWING,
    LayeredDoorwayClosure,
    build_from_pdf_bytes,
)
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_physical_net_wall_integration import (
    _collect_live_physical_net_wall_claim,
    collect_live_physical_net_wall_claim,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    SourceRoomFaceSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer

ENVELOPE = (100.0, 80.0, 250.0, 180.0)
SCOPE_KW = dict(document_id="d", revision_id="r", snapshot_id="s", page_id="1", decision_scope_id="wall-source:page-1")


def partition_pdf(
    *, ox: float = 0.0, oy: float = 0.0, alcove_stub: bool = True, bedroom_stub: bool = True,
    alcove_top_wall: bool = True, leaves: int = 2, frames: int = 2,
    horizontal_span: tuple[float, float] = (100.0, 250.0),
    vertical_spans: tuple[tuple[float, float, float], ...] = ((290.0, 80.0, 180.0),),
    labels: tuple[tuple[str, float, float], ...] = (("BED 2", 150.0, 130.0), ("ROBE", 180.0, 98.0)),
    vertical_text: dict | None = None,
    left_vertical_spans: tuple[tuple[float, float], ...] = (),
    horizontal_tick_end: float = 92.0,
) -> bytes:
    """A room (100,80)-(250,180) whose whole width is split by a wardrobe front (y 108..110).

    The front's opening is closed only by two frame boxes and two overlapping sliding leaves, so the room
    is a bedroom face (100,110)-(250,180) and an alcove face (100,80)-(250,108); each carries a wall return,
    so neither part is its bounding rectangle. The printed figures run wall face to wall face of the WHOLE
    room (3600 x 2400 at 24 mm per point). Every coordinate may be translated by (ox, oy).
    """
    doc = fitz.open()
    page = doc.new_page(width=450.0 + ox, height=350.0 + oy)
    oc = doc.add_ocg("Enclosure_WallInternal", on=True)

    def rect(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0 + ox, y0 + oy, x1 + ox, y1 + oy), color=None, fill=(0, 0, 0), oc=oc)

    def pt(x, y):
        return fitz.Point(x + ox, y + oy)

    def line(a, b, **kw):
        page.draw_line(pt(*a), pt(*b), color=(0, 0, 0), **kw)

    if alcove_top_wall:
        rect(96, 76, 254, 80)
    else:
        rect(96, 76, 150, 80)  # a gap in the top wall: the alcove leaks to the outside
    rect(96, 180, 254, 184)
    rect(96, 80, 100, 180)
    rect(250, 80, 254, 180)
    if alcove_stub:
        rect(120, 80, 122, 95)  # clear of the figure's text, which would otherwise not authenticate
    if bedroom_stub:
        rect(100, 150, 115, 154)
    rect(100, 108, 104.4, 110)
    rect(246, 108, 250, 110)
    for fx0, fx1 in [(104.4, 105.5), (244.9, 246.0)][:frames]:
        page.draw_rect(fitz.Rect(fx0 + ox, 107.72 + oy, fx1 + ox, 110.28 + oy), color=None, fill=(1, 1, 1), oc=oc)
    if leaves >= 1:
        line((105.5, 108.0), (195.0, 108.0), width=0.34, oc=oc)
    if leaves >= 2:
        line((190.0, 110.2), (244.9, 110.2), width=0.34, oc=oc)
    for text, x, y in labels:
        page.insert_text(pt(x, y), text, fontsize=10.0)
    h0, h1 = horizontal_span
    line((h0, 70.0), (h1, 70.0), width=1.0)
    line((h0, 62.0), (h0, horizontal_tick_end), width=1.0)
    line((h1, 62.0), (h1, horizontal_tick_end), width=1.0)
    page.insert_text(pt((h0 + h1) / 2.0 - 11.0, 67.0), str(round((h1 - h0) * 24)), fontsize=9.0)
    for x, y0, y1 in vertical_spans:
        line((x, y0), (x, y1), width=1.0)
        line((x - 40.0, y0), (x + 8.0, y0), width=1.0)
        line((x - 12.0, y1), (x + 8.0, y1), width=1.0)
        value = (vertical_text or {}).get((x, y0, y1), str(round((y1 - y0) * 24)))
        page.insert_text(pt(x - 3.0, (y0 + y1) / 2.0 + 17.0), value, fontsize=9.0, rotate=90)
    for y0, y1 in left_vertical_spans:  # a figure on the room's left, its ticks landing on the left wall
        line((60.0, y0), (60.0, y1), width=1.0)
        line((48.0, y0), (100.0, y0), width=1.0)
        line((48.0, y1), (100.0, y1), width=1.0)
        page.insert_text(pt(57.0, (y0 + y1) / 2.0 + 17.0), str(round((y1 - y0) * 24)), fontsize=9.0, rotate=90)
    return doc.tobytes()


def _dim(dimension_id, orientation, a, b):
    return SimpleNamespace(dimension_id=dimension_id, orientation=orientation, endpoints_pt=(a, b))


H_FULL = _dim("h", "horizontal", (100.0, 70.0), (250.0, 70.0))
V_FULL = _dim("v", "vertical", (290.0, 80.0), (290.0, 180.0))
V_BEDROOM = _dim("v-bed", "vertical", (290.0, 110.0), (290.0, 180.0))


def _rings(data: bytes):
    sha = hashlib.sha256(data).hexdigest()
    return sha, build_from_pdf_bytes(data, source_sha256=sha, page_index=0, sliding_leaf_frame_closure=True)


@lru_cache(maxsize=None)
def _base():
    data = partition_pdf()
    sha, result = _rings(data)
    bedroom = next(r for r in result.rings if r.bbox_pdf_pts[1] == 110.0)
    alcove = next(r for r in result.rings if r.bbox_pdf_pts[1] == 80.0)
    return data, sha, result, bedroom, alcove, result.closures[0]


def _scope(result, sha, dims, *, partition=True, **overrides):
    return layered_ring_room_face_scope(
        result, source_sha256=sha, corroborating_dimensions=dims, partition_witness=partition,
        **{**SCOPE_KW, **overrides},
    )


def _refused(result, sha, dims, **overrides):
    """No part of the partition becomes a record (a scope is only returned when some other ring does)."""
    scope = _scope(result, sha, dims, **overrides)
    return scope is None or not any(
        c.startswith(RING_PARTITION_PART_PREFIX) for c in scope.reason_codes
    ) and scope.records == ()


# --------------------------------------------------------------------------------------------- positive


def test_original_like_split_with_two_nonrectangular_parts_and_one_unique_union_witness():
    _data, sha, result, bedroom, alcove, closure = _base()
    assert closure.kind == KIND_SLIDING_LEAF and len(result.rings) == 2
    # neither part's own box is the printed room: each is judged only by the union
    assert bedroom.bbox_pdf_pts == (100.0, 110.0, 250.0, 180.0) and alcove.bbox_pdf_pts == (100.0, 80.0, 250.0, 108.0)
    group, = partition_groups(result, source_sha256=sha, page_index=0)
    assert group.valid and group.envelope == ENVELOPE
    assert set(group.ring_record_ids) == {bedroom.record_id, alcove.record_id}
    assert group.sliding_closure_ids == (closure.closure_id,)

    scope = _scope(result, sha, [H_FULL, V_FULL])
    assert len(scope.records) == 2 and scope.abstained_faces == ()
    codes = set(scope.reason_codes)
    assert {LAYERED_RING_SCOPE_REASON, LAYERED_RING_PARTITION_REASON, SOURCE_ROOM_FACE_UNIVERSE_PARTIAL} <= codes
    assert "face_universe_complete" not in " ".join(codes)
    for record in scope.records:
        assert f"{RING_PARTITION_PART_PREFIX}{record.record_id}" in codes
        assert f"{RING_NOT_A_RECTANGLE_PREFIX}{record.record_id}" in codes  # both parts carry a wall return
    # a part's measure stays its own polygon: the shared box is nobody's area
    box_area = 150.0 * 100.0
    assert sorted(round(r.area_page_pts2, 1) for r in scope.records) == [4170.0, 10440.0]
    assert all(r.area_page_pts2 != box_area for r in scope.records)
    assert sum(r.area_page_pts2 for r in scope.records) < box_area  # the wall front between them is not room


def test_default_off_is_byte_identical_and_a_box_that_equals_no_part_yields_nothing():
    _data, sha, result, *_ = _base()
    explicit_off = _scope(result, sha, [H_FULL, V_FULL], partition=False)
    absent = layered_ring_room_face_scope(result, source_sha256=sha, corroborating_dimensions=[H_FULL, V_FULL], **SCOPE_KW)
    # without the control neither part matches the printed room box by itself: nothing is issued
    assert explicit_off is None and absent is None
    # direct converter use without dimensions keeps every closed ring; a partition cannot be corroborated without them
    assert _scope(result, sha, None, partition=False) is not None
    assert _scope(result, sha, None, partition=True) is None
    assert _refused(result, sha, [])


def test_the_control_is_an_explicit_boolean_and_needs_the_sliding_control():
    _data, sha, result, *_ = _base()
    with pytest.raises(ValueError):
        _scope(result, sha, [H_FULL, V_FULL], partition=1)  # type: ignore[arg-type]
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(ValueError):
        layered_ring_scope_overrides(source, revision_id="r", page_ids=("1",), partition_witness=True)
    with pytest.raises(ValueError):
        layered_ring_scope_overrides(source, revision_id="r", page_ids=("1",), partition_witness=True,
                                     sliding_leaf_frame_closure=True, require_figured_box=False)
    with pytest.raises(ValueError):
        layered_ring_scope_overrides(source, revision_id="r", page_ids=("1",), partition_witness="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_partition_witness=True)
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_doorway_room_rings=True, layered_sliding_leaf_closure=True,
                                     layered_partition_witness=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim("unused.pdf", layered_partition_witness=True)
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim("unused.pdf", layered_doorway_room_rings=True,
                                             layered_sliding_leaf_closure=True, layered_partition_witness="yes")  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------- figured pair


@pytest.mark.parametrize("dims", [
    pytest.param([H_FULL, V_BEDROOM], id="bedroom_only_span_that_equals_one_part_box"),
    pytest.param([H_FULL], id="vertical_missing"),
    pytest.param([V_FULL], id="horizontal_missing"),
    pytest.param([], id="no_dimensions"),
    pytest.param([H_FULL, V_FULL, _dim("v2", "vertical", (320.0, 80.3), (320.0, 179.8))], id="two_vertical_candidates"),
    pytest.param([H_FULL, _dim("h2", "horizontal", (100.0, 50.0), (249.6, 50.0)), V_FULL], id="two_horizontal_candidates"),
    pytest.param([_dim("h-wide", "horizontal", (100.0, 70.0), (250.8, 70.0)), V_FULL], id="span_off_by_more_than_half_a_point"),
    pytest.param([_dim("h-moved", "horizontal", (140.0, 70.0), (290.0, 70.0)), _dim("v-moved", "vertical", (330.0, 80.0), (330.0, 180.0))],
                 id="wrong_viewport_translated_figures"),
])
def test_ambiguous_wrong_or_missing_union_pair_abstains_every_part(dims):
    _data, sha, result, *_ = _base()
    assert _refused(result, sha, dims)


def test_two_prints_of_the_union_height_are_one_pair():
    _data, sha, result, *_ = _base()
    scope = _scope(
        result, sha,
        [H_FULL, V_FULL, _dim("v2", "vertical", (320.0, 80.0), (320.0, 180.0))],
    )
    assert scope is not None and len(scope.records) == 2


def test_a_part_with_a_matching_own_box_is_still_judged_only_by_its_group():
    # the bedroom's own box (100,110,250,180) equals the printed pair H_FULL x V_BEDROOM: the group rule ignores that
    _data, sha, result, _bedroom, *_ = _base()
    assert layered_ring_room_face_scope(
        result, source_sha256=sha, corroborating_dimensions=[H_FULL, V_BEDROOM], **SCOPE_KW
    ).records[0].record_id is not None  # without the control the bedroom IS admitted by its own box
    assert _refused(result, sha, [H_FULL, V_BEDROOM])


def test_wrong_page_abstains_even_when_the_pair_matches():
    _data, sha, result, *_ = _base()
    assert not _refused(result, sha, [H_FULL, V_FULL])
    assert _refused(result, sha, [H_FULL, V_FULL], page_id="2")  # rings belong to page 1
    assert _refused(result, sha, [H_FULL, V_FULL], page_id="x")


# --------------------------------------------------------------------------------------------- membership


def _with(result, *, rings=None, closures=None):
    return replace(result, rings=tuple(rings if rings is not None else result.rings),
                   closures=tuple(closures if closures is not None else result.closures))


def _reason(result, sha):
    groups = partition_groups(result, source_sha256=sha, page_index=0)
    assert len(groups) == 1 and not groups[0].valid
    return groups[0].reason


def _chord_owner(closure):
    return f"layered_doorway_closure:{closure.closure_id}"


def test_omitted_robe_the_alcove_leaks_so_the_bedroom_has_no_partner():
    data = partition_pdf(alcove_top_wall=False)
    sha, result = _rings(data)
    assert len(result.rings) == 1 and len(result.closures) == 1  # the alcove is no closed face of its own
    assert _reason(result, sha) == REASON_MEMBERSHIP
    assert _refused(result, sha, [H_FULL, V_FULL])


@pytest.mark.parametrize("kwargs", [{"leaves": 1}, {"leaves": 0}, {"frames": 1}, {"frames": 0}], ids=lambda k: str(k))
def test_altered_frame_or_leaf_leaves_the_front_open_so_no_partition_exists(kwargs):
    sha, result = _rings(partition_pdf(**kwargs))
    assert result.closures == () and partition_groups(result, source_sha256=sha, page_index=0) == ()
    assert _refused(result, sha, [H_FULL, V_FULL])


def test_a_third_ring_on_the_same_chord_is_an_extra_neighbour():
    _data, sha, result, bedroom, alcove, _closure = _base()
    extra = replace(alcove, record_id="e" * 32)
    assert _reason(_with(result, rings=[bedroom, alcove, extra]), sha) == REASON_MEMBERSHIP
    assert _refused(_with(result, rings=[bedroom, alcove, extra]), sha, [H_FULL, V_FULL])


def test_copied_foreign_sha_or_page_refuses_the_group():
    _data, sha, result, bedroom, alcove, _closure = _base()
    foreign_sha = replace(alcove, source_sha256="cd" * 32)
    assert _reason(_with(result, rings=[bedroom, foreign_sha]), sha) == REASON_FOREIGN
    foreign_page = replace(alcove, page_index=1)
    assert _reason(_with(result, rings=[bedroom, foreign_page]), sha) == REASON_FOREIGN
    assert _refused(_with(result, rings=[bedroom, foreign_sha]), sha, [H_FULL, V_FULL])
    # a ring set built for another source cannot be corroborated under this source's identity either
    assert partition_groups(result, source_sha256="cd" * 32, page_index=0)[0].reason == REASON_FOREIGN


def test_conflicting_same_id_rings_are_quarantined_and_input_order_never_picks_provenance():
    _data, sha, result, bedroom, alcove, _closure = _base()
    foreign = replace(alcove, source_sha256="cd" * 32)  # the SAME record_id, a foreign source
    assert foreign.record_id == alcove.record_id
    for order in ([bedroom, foreign, alcove], [bedroom, alcove, foreign], [foreign, bedroom, alcove],
                  [alcove, foreign, bedroom], [foreign, alcove, bedroom], [alcove, bedroom, foreign]):
        variant = _with(result, rings=order)
        assert _reason(variant, sha) == REASON_ID_COLLISION
        assert _refused(variant, sha, [H_FULL, V_FULL])
    # even an exact copy is refused: no order decides which of two same-id records is the source's
    assert _reason(_with(result, rings=[bedroom, alcove, alcove]), sha) == REASON_ID_COLLISION
    # a record that is not duplicated stays admitted
    assert not _refused(result, sha, [H_FULL, V_FULL])


def test_competing_same_id_chords_are_quarantined_in_both_orders():
    _data, sha, result, _bedroom, _alcove, closure = _base()
    lo, hi = closure.gap_interval
    shifted = replace(closure, gap_interval=(lo + 3.0, hi))
    swing_copy = replace(closure, kind=KIND_SWING)
    for competing in (shifted, swing_copy, closure):
        for order in ([competing, closure], [closure, competing]):
            variant = _with(result, closures=order)
            assert _reason(variant, sha) == REASON_ID_COLLISION
            assert _refused(variant, sha, [H_FULL, V_FULL])


def test_a_duplicated_swing_chord_bordering_a_member_is_quarantined_too():
    _data, sha, result, bedroom, alcove, closure = _base()
    swing = replace(closure, closure_id="s" * 24, kind=KIND_SWING)
    touching = replace(bedroom, bounding_closure_ids=tuple(sorted((*bedroom.bounding_closure_ids, swing.closure_id))))
    for order in ([closure, swing, swing], [swing, closure, swing], [swing, swing, closure]):
        variant = _with(result, rings=[touching, alcove], closures=order)
        assert _reason(variant, sha) == REASON_ID_COLLISION
        assert _refused(variant, sha, [H_FULL, V_FULL])


def test_shared_chord_missing_on_one_side_moved_or_on_the_same_face_line_refuses():
    _data, sha, result, bedroom, alcove, closure = _base()
    # missing: the alcove's chord edges are re-owned as plain wall
    owners = tuple(("layered_wall_strip:9",) if o and o[0] == _chord_owner(closure) else o for o in alcove.edge_owner_ids)
    assert owners != alcove.edge_owner_ids
    missing = replace(alcove, edge_owner_ids=owners)
    assert _reason(_with(result, rings=[bedroom, missing]), sha) == REASON_CHORD
    # moved: the closure interval no longer equals the edges of either ring
    lo, hi = closure.gap_interval
    moved = replace(closure, gap_interval=(lo + 3.0, hi))
    assert _reason(_with(result, closures=[moved]), sha) == REASON_CHORD
    shifted_band = replace(closure, band=(closure.band[0] + 2.0, closure.band[1] + 2.0))
    assert _reason(_with(result, closures=[shifted_band]), sha) == REASON_CHORD
    # both rings' chord edges on the SAME face line: not a chord with a ring on each side
    flat = tuple((x, 110.0 if abs(y - 108.0) < 1e-6 else y) for x, y in alcove.polygon_pdf_pts)
    assert flat != alcove.polygon_pdf_pts
    assert _reason(_with(result, rings=[bedroom, replace(alcove, polygon_pdf_pts=flat)]), sha) == REASON_CHORD
    for variant in (_with(result, rings=[bedroom, missing]), _with(result, closures=[moved])):
        assert _refused(variant, sha, [H_FULL, V_FULL])


def _alcove_with_chord_pieces(alcove, closure, inserted_points, inserted_owners):
    """The alcove with its one chord edge replaced by the given vertices and per-edge owners."""
    owner = (_chord_owner(closure),)
    index, = [i for i, o in enumerate(alcove.edge_owner_ids) if tuple(o) == owner]
    points = list(alcove.polygon_pdf_pts)
    assert points[index] == (104.4, 108.0) and points[(index + 1) % len(points)] == (246.0, 108.0)
    owners = list(alcove.edge_owner_ids)
    return replace(
        alcove,
        polygon_pdf_pts=tuple(points[:index + 1] + inserted_points + points[index + 1:]),
        edge_owner_ids=tuple(owners[:index] + inserted_owners + owners[index + 1:]),
    )


def test_chord_edges_must_cover_the_interval_on_one_face_line_within_representation_noise():
    _data, sha, result, bedroom, alcove, closure = _base()
    chord, wall = (_chord_owner(closure),), ("layered_wall_strip:9",)
    # a piece of the interval owned by something else: not the same chord
    gapped = _alcove_with_chord_pieces(alcove, closure, [(150.0, 108.0), (200.0, 108.0)], [chord, wall, chord])
    assert _reason(_with(result, rings=[bedroom, gapped]), sha) == REASON_CHORD
    # the chord edges on two lines a point apart: not one face line of the band
    jogged = _alcove_with_chord_pieces(
        alcove, closure, [(170.0, 108.0), (170.0, 107.0), (246.0, 107.0)], [chord, wall, chord, wall])
    assert _reason(_with(result, rings=[bedroom, jogged]), sha) == REASON_CHORD
    # representation noise (far below the 0.05 pt bound) is not a reason to refuse
    jittered = _alcove_with_chord_pieces(
        alcove, closure, [(170.0, 108.0), (170.0, 107.99), (246.0, 107.99)], [chord, wall, chord, wall])
    noisy_closure = replace(closure, band=(closure.band[0] + 0.004, closure.band[1] - 0.004),
                            gap_interval=(closure.gap_interval[0] + 0.004, closure.gap_interval[1] - 0.004))
    for variant in (_with(result, rings=[bedroom, jittered]), _with(result, closures=[noisy_closure])):
        group, = partition_groups(variant, source_sha256=sha, page_index=0)
        assert group.valid, group.reason
    # ...but a fifth of a point is
    off = replace(closure, band=(closure.band[0] + 0.2, closure.band[1] + 0.2))
    assert _reason(_with(result, closures=[off]), sha) == REASON_CHORD
    off_interval = replace(closure, gap_interval=(closure.gap_interval[0] + 0.2, closure.gap_interval[1]))
    assert _reason(_with(result, closures=[off_interval]), sha) == REASON_CHORD


def test_chord_edges_a_little_over_the_noise_bound_apart_are_not_one_face_line():
    _data, sha, result, bedroom, alcove, closure = _base()
    chord, wall = (_chord_owner(closure),), ("layered_wall_strip:9",)
    # 0.08 pt apart: their mean sits inside the noise bound of the face, so only the one-line rule can refuse it
    jogged = _alcove_with_chord_pieces(
        alcove, closure, [(170.0, 108.0), (170.0, 108.08), (246.0, 108.08)], [chord, wall, chord, wall])
    assert _reason(_with(result, rings=[bedroom, jogged]), sha) == REASON_CHORD


@pytest.mark.parametrize("kind", [KIND_SWING, KIND_STROKE])
def test_a_swing_or_stroke_doorway_never_defines_a_partition_group(kind):
    _data, sha, result, _bedroom, _alcove, closure = _base()
    ordinary_doorway = _with(result, closures=[replace(closure, kind=kind)])
    assert partition_groups(ordinary_doorway, source_sha256=sha, page_index=0) == ()
    # two rooms joined by an ordinary doorway are each judged by their own box, and neither is the printed room
    assert _scope(ordinary_doorway, sha, [H_FULL, V_FULL]) is None


def test_an_invalid_group_is_never_corroborated_even_by_a_degenerate_figure_pair():
    _data, sha, result, bedroom, alcove, _closure = _base()
    refused = _with(result, rings=[bedroom, replace(alcove, source_sha256="cd" * 32)])
    zero_pair = [_dim("h0", "horizontal", (0.0, 0.0), (0.0, 0.0)), _dim("v0", "vertical", (0.0, 0.0), (0.0, 0.0))]
    assert _refused(refused, sha, zero_pair)


def test_live_chain_a_part_whose_own_box_equals_another_printed_pair_still_has_no_documented_area():
    # a second printed figure runs exactly over the bedroom part: the union pair is still unique, but the
    # part's own box now equals a pair, the hazard of reading a width x depth as a part's area
    data = partition_pdf(alcove_stub=False, bedroom_stub=False, left_vertical_spans=((110.0, 180.0),),
                         horizontal_tick_end=190.0)
    source, _published, rooms = _compose(data, partition=True)
    assert len(rooms.rooms) == 2
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert area.records == ()
    assert "same_view_layered_ring_partition_part" in {c for _r, c in area.unresolved_first_failure_codes}


def test_the_partition_control_is_refused_without_sliding_before_any_source_is_opened():
    with pytest.raises(ValueError, match="partition witness"):
        collect_live_physical_net_wall_claim(
            "does-not-exist.pdf", recover_additional_opening_areas=True, layered_partition_witness=True)
    with pytest.raises(ValueError, match="partition witness"):
        _collect_live_physical_net_wall_claim("does-not-exist.pdf", layered_partition_witness=True)


def test_overlapping_rings_refuse():
    _data, sha, result, bedroom, alcove, _closure = _base()
    points = list(bedroom.polygon_pdf_pts)
    assert (100.0, 110.0) in points
    points[points.index((100.0, 110.0))] = (100.0, 100.0)  # bulges into the alcove away from the chord
    overlapping = replace(bedroom, polygon_pdf_pts=tuple(points))
    assert _reason(_with(result, rings=[overlapping, alcove]), sha) == REASON_OVERLAP
    assert _refused(_with(result, rings=[overlapping, alcove]), sha, [H_FULL, V_FULL])


def test_a_member_that_is_open_holed_or_self_touching_refuses():
    _data, sha, result, bedroom, alcove, _closure = _base()
    assert _reason(_with(result, rings=[bedroom, replace(alcove, status=EvidenceResolutionStatus.ABSTAINED,
                                                         reason_codes=("open_wall_gap_unresolved",))]), sha) == REASON_OPEN_MEMBER
    assert _reason(_with(result, rings=[bedroom, replace(alcove, hole_count=1)]), sha) == REASON_HOLE
    points = list(alcove.polygon_pdf_pts)
    i, j = points.index((122.0, 95.0)), points.index((120.0, 95.0))
    points[i], points[j] = points[j], points[i]  # the wall return's tip now crosses itself; every chord edge is intact
    crossing = replace(alcove, polygon_pdf_pts=tuple(points))
    assert not Polygon(crossing.polygon_pdf_pts).is_valid
    assert _reason(_with(result, rings=[bedroom, crossing]), sha) == REASON_MEMBERSHIP


def test_a_swing_or_stroke_chord_joining_two_members_is_not_a_partition_edge():
    _data, sha, result, bedroom, alcove, closure = _base()
    swing = replace(closure, closure_id="s" * 24, kind=KIND_SWING)
    mixed_bedroom = replace(bedroom, bounding_closure_ids=tuple(sorted((*bedroom.bounding_closure_ids, swing.closure_id))))
    mixed_alcove = replace(alcove, bounding_closure_ids=tuple(sorted((*alcove.bounding_closure_ids, swing.closure_id))))
    mixed = _with(result, rings=[mixed_bedroom, mixed_alcove], closures=[closure, swing])
    assert _reason(mixed, sha) == REASON_MIXED
    assert _refused(mixed, sha, [H_FULL, V_FULL])


# ----------------------------- fabricated multi-part groups (an extra component, an enclosed void)


def _owners(points, closures):
    out = []
    for a, b in zip(points, points[1:] + points[:1]):
        owner = ("layered_wall_strip:1",)
        for c in closures:
            lo, hi = c.gap_interval
            if c.horizontal and abs(a[1] - b[1]) < 1e-9 and any(abs(a[1] - f) < 1e-9 for f in c.band):
                if lo - 1e-9 <= min(a[0], b[0]) and max(a[0], b[0]) <= hi + 1e-9:
                    owner = (_chord_owner(c),)
            if not c.horizontal and abs(a[0] - b[0]) < 1e-9 and any(abs(a[0] - f) < 1e-9 for f in c.band):
                if lo - 1e-9 <= min(a[1], b[1]) and max(a[1], b[1]) <= hi + 1e-9:
                    owner = (_chord_owner(c),)
        out.append(owner)
    return tuple(out)


def _chord(name, band, gap):
    return LayeredDoorwayClosure(closure_id=name * 24, kind=KIND_SLIDING_LEAF, horizontal=True, band=band,
                                 gap_interval=gap, native_path_indices=(), wall_path_indices=())


def _ring_from(template, name, points, closures):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return replace(
        template, record_id=name * 32, polygon_pdf_pts=tuple(points), hole_count=0,
        bbox_pdf_pts=(min(xs), min(ys), max(xs), max(ys)),
        bounding_closure_ids=tuple(sorted(c.closure_id for c in closures if any(
            o == (_chord_owner(c),) for o in _owners(list(points), [c])))),
        edge_owner_ids=_owners(list(points), closures),
    )


def _chain(extra_width=0.0):
    """A (0..30 x 0..10) joined by chords to B (0..10 x 14..40) and to C (20..30+extra x 14..40)."""
    _data, sha, result, bedroom, *_ = _base()
    c1 = _chord("a", (10.0, 14.0), (2.0, 8.0))
    c2 = _chord("b", (10.0, 14.0), (22.0, 28.0))
    right = 30.0 + extra_width
    a = _ring_from(bedroom, "1", [(0.0, 0.0), (30.0, 0.0), (30.0, 10.0), (28.0, 10.0), (22.0, 10.0), (8.0, 10.0), (2.0, 10.0), (0.0, 10.0)], [c1, c2])
    b = _ring_from(bedroom, "2", [(0.0, 14.0), (2.0, 14.0), (8.0, 14.0), (10.0, 14.0), (10.0, 40.0), (0.0, 40.0)], [c1, c2])
    c = _ring_from(bedroom, "3", [(20.0, 14.0), (22.0, 14.0), (28.0, 14.0), (30.0, 14.0), (right, 14.0), (right, 40.0), (20.0, 40.0)], [c1, c2])
    return sha, replace(result, rings=(a, b, c), closures=(c1, c2))


def test_a_three_part_chain_is_one_group_and_an_extra_component_widens_the_envelope():
    sha, chain = _chain()
    group, = partition_groups(chain, source_sha256=sha, page_index=0)
    assert group.valid and len(group.ring_record_ids) == 3 and len(group.sliding_closure_ids) == 2
    assert group.envelope == (0.0, 0.0, 30.0, 40.0)
    pair = [_dim("h", "horizontal", (0.0, -9.0), (30.0, -9.0)), _dim("v", "vertical", (45.0, 0.0), (45.0, 40.0))]
    assert len(_scope(chain, sha, pair).records) == 3
    # the same printed room with one extra component attached beyond it: the union is wider than the pair
    sha_wide, wide = _chain(extra_width=10.0)
    wide_group, = partition_groups(wide, source_sha256=sha_wide, page_index=0)
    assert wide_group.valid and wide_group.envelope == (0.0, 0.0, 40.0, 40.0)
    assert _refused(wide, sha_wide, pair)
    assert len(_scope(wide, sha_wide, [_dim("h", "horizontal", (0.0, -9.0), (40.0, -9.0)), pair[1]]).records) == 3


def test_an_unexplained_enclosed_void_between_the_parts_refuses():
    sha, chain = _chain()
    a, b, c = chain.rings
    c1, c2 = chain.closures
    c3 = _chord("c", (40.0, 44.0), (2.0, 8.0))
    c4 = _chord("d", (40.0, 44.0), (22.0, 28.0))
    closures = [c1, c2, c3, c4]
    b = _ring_from(b, "2", [(0.0, 14.0), (2.0, 14.0), (8.0, 14.0), (10.0, 14.0), (10.0, 40.0), (8.0, 40.0), (2.0, 40.0), (0.0, 40.0)], closures)
    c = _ring_from(c, "3", [(20.0, 14.0), (22.0, 14.0), (28.0, 14.0), (30.0, 14.0), (30.0, 40.0), (28.0, 40.0), (22.0, 40.0), (20.0, 40.0)], closures)
    d = _ring_from(a, "4", [(0.0, 44.0), (2.0, 44.0), (8.0, 44.0), (22.0, 44.0), (28.0, 44.0), (30.0, 44.0), (30.0, 54.0), (0.0, 54.0)], closures)
    ring_a = _ring_from(a, "1", [(0.0, 0.0), (30.0, 0.0), (30.0, 10.0), (28.0, 10.0), (22.0, 10.0), (8.0, 10.0), (2.0, 10.0), (0.0, 10.0)], closures)
    cycle = replace(chain, rings=(ring_a, b, c, d), closures=tuple(closures))
    assert _reason(cycle, sha) == REASON_HOLE
    assert _refused(cycle, sha, [_dim("h", "horizontal", (0.0, -9.0), (30.0, -9.0)), _dim("v", "vertical", (45.0, 0.0), (45.0, 54.0))])


# --------------------------------------------------------------------------------------------- invariances


def _snapshot(result):
    return (
        tuple((r.record_id, r.polygon_pdf_pts, r.edge_owner_ids, r.bounding_closure_ids, r.status, r.hole_count)
              for r in result.rings),
        result.closures,
    )


def test_replay_is_deterministic_input_order_invariant_and_never_mutates_the_input():
    _data, sha, result, bedroom, alcove, _closure = _base()
    frozen = _snapshot(result)
    first = _scope(result, sha, [H_FULL, V_FULL])
    again = _scope(result, sha, [V_FULL, H_FULL, H_FULL])
    reordered = _scope(_with(result, rings=[alcove, bedroom]), sha, [H_FULL, V_FULL])
    assert first == again == reordered
    assert [r.record_id for r in first.records] == sorted(r.record_id for r in first.records)
    assert _snapshot(result) == frozen
    # the partition identity is bound into the record id: the same ring is a different record without it
    plain = layered_ring_room_face_scope(result, source_sha256=sha, **SCOPE_KW)
    assert {r.record_id for r in plain.records}.isdisjoint({r.record_id for r in first.records})


def test_translation_keeps_the_outcome_and_the_group_envelope():
    outcomes = []
    for ox, oy in ((0.0, 0.0), (37.5, 12.25), (200.0, 90.0)):
        data = partition_pdf(ox=ox, oy=oy)
        sha, result = _rings(data)
        group, = partition_groups(result, source_sha256=sha, page_index=0)
        assert group.valid and group.envelope == (100.0 + ox, 80.0 + oy, 250.0 + ox, 180.0 + oy)
        dims = [_dim("h", "horizontal", (100.0 + ox, 70.0 + oy), (250.0 + ox, 70.0 + oy)),
                _dim("v", "vertical", (290.0 + ox, 80.0 + oy), (290.0 + ox, 180.0 + oy))]
        scope = _scope(result, sha, dims)
        outcomes.append(sorted(round(r.area_page_pts2, 1) for r in scope.records))
        # the unshifted figures do not corroborate the shifted room
        if (ox, oy) != (0.0, 0.0):
            assert _refused(result, sha, [H_FULL, V_FULL])
    assert outcomes == [[4170.0, 10440.0]] * 3


# --------------------------------------------------------------------------------------------- live chain


def _compose(data: bytes, *, partition: bool, sliding: bool = True):
    source = SourceVisibilityProducer(producer_method="layered-partition-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-partition-doc", source_bytes=data,
        source_locator="memory://layered-partition.pdf", page_ids=("1",),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=("1",), evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
        layered_doorway_room_rings=True,
        **({"layered_sliding_leaf_closure": True} if sliding else {}),
        **({"layered_partition_witness": True} if partition else {}),
    )
    return source, published, rooms


def _scope_of(rooms, room):
    return rooms.room_face_authority_binding_for(room).authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id))


def test_live_chain_two_parts_become_rooms_with_their_own_labels_and_no_area_from_the_shared_pair():
    data = partition_pdf()
    # sliding control alone: neither part's own box is the printed room, so nothing replaces the page scope
    _source, _published, without = _compose(data, partition=False)
    assert not any("layered" in " ".join(r.bounding_wall_ids) for r in without.rooms)
    source, _published, rooms = _compose(data, partition=True)
    assert len(rooms.rooms) == 2
    labels = {r.room_label for r in rooms.rooms}
    assert labels == {"BED 2", "ROBE"}
    scope = _scope_of(rooms, rooms.rooms[0])
    assert LAYERED_RING_PARTITION_REASON in scope.reason_codes and SOURCE_ROOM_FACE_UNIVERSE_PARTIAL in scope.reason_codes
    for room in rooms.rooms:
        assert f"{RING_PARTITION_PART_PREFIX}{room.source_room_face_record_id}" in scope.reason_codes
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert area.records == ()
    assert {c for _r, c in area.unresolved_first_failure_codes} == {"same_view_layered_ring_partition_part"}


def test_live_chain_a_true_rectangle_part_also_loses_the_documented_route():
    data = partition_pdf(alcove_stub=False, bedroom_stub=False)
    source, _published, rooms = _compose(data, partition=True)
    assert len(rooms.rooms) == 2
    scope = _scope_of(rooms, rooms.rooms[0])
    assert not any(c.startswith(RING_NOT_A_RECTANGLE_PREFIX) for c in scope.reason_codes)
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert area.records == ()  # a box that matches the union never becomes a part's area
    assert {c for _r, c in area.unresolved_first_failure_codes} == {"same_view_layered_ring_partition_part"}


def test_live_chain_competing_labels_stay_unresolved_and_never_choose_nearest_or_first():
    data = partition_pdf(labels=(("BED 2", 150.0, 130.0), ("STUDY", 150.0, 160.0), ("ROBE", 180.0, 98.0)))
    _source, _published, rooms = _compose(data, partition=True)
    assert len(rooms.rooms) == 2
    assert "ROBE" in {r.room_label for r in rooms.rooms}
    assert not {"BED 2", "STUDY"} & {r.room_label for r in rooms.rooms}  # two competing names: neither is chosen


@pytest.mark.parametrize("kwargs", [
    pytest.param({"vertical_spans": ((290.0, 80.0, 180.0), (320.0, 80.3, 179.8))}, id="two_vertical_figures_with_the_union_span"),
    pytest.param({"vertical_spans": ((290.0, 110.0, 180.0),)}, id="only_the_bedroom_span_is_printed"),
    pytest.param({"horizontal_span": (140.0, 290.0)}, id="horizontal_figure_in_the_wrong_place"),
    pytest.param({"alcove_top_wall": False}, id="omitted_robe"),
    pytest.param({"leaves": 1}, id="altered_leaf"),
    pytest.param({"frames": 1}, id="altered_frame"),
])
def test_live_chain_every_negative_issues_no_partition_override(kwargs):
    data = partition_pdf(**kwargs)
    source = SourceVisibilityProducer(producer_method="layered-partition-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-partition-doc", source_bytes=data,
        source_locator="memory://layered-partition.pdf", page_ids=("1",),
    )
    assert layered_ring_scope_overrides(
        source, revision_id=published.revision.revision_id, page_ids=("1",),
        sliding_leaf_frame_closure=True, partition_witness=True,
    ) == {}


def test_live_chain_positive_issues_one_sealed_override_and_the_union_pair_is_unique():
    data = partition_pdf()
    source = SourceVisibilityProducer(producer_method="layered-partition-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-partition-doc", source_bytes=data,
        source_locator="memory://layered-partition.pdf", page_ids=("1",),
    )
    kwargs = dict(revision_id=published.revision.revision_id, page_ids=("1",), sliding_leaf_frame_closure=True)
    assert layered_ring_scope_overrides(source, **kwargs) == {}
    issued = layered_ring_scope_overrides(source, partition_witness=True, **kwargs)
    assert len(issued) == 1
    override, = issued.values()
    assert LAYERED_RING_PARTITION_REASON in override.scope.reason_codes and len(override.scope.records) == 2


def test_a_stale_or_inconsistent_scale_cannot_turn_a_partition_part_into_a_quantity():
    # the vertical figure's printed value disagrees with its span at the horizontal figure's scale
    data = partition_pdf(vertical_text={(290.0, 80.0, 180.0): "1500"})
    source, _published, rooms = _compose(data, partition=True)
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    assert area.records == ()


def test_whole_claim_plumbs_the_option_to_two_rooms_and_issues_no_quantity_or_customer_row(tmp_path):
    path = tmp_path / "partition_room.pdf"
    path.write_bytes(partition_pdf())
    common = dict(pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,), layered_doorway_room_rings=True)
    sliding_only = collect_live_physical_net_wall_claim(path, layered_sliding_leaf_closure=True, **common)
    assert not any(r.bounding_wall_ids and r.bounding_wall_ids[0].startswith("layered_") for r in sliding_only.canonical_rooms)
    on = collect_live_physical_net_wall_claim(
        path, layered_sliding_leaf_closure=True, layered_partition_witness=True, **common)
    assert len(on.canonical_rooms) == 2
    assert all(r.bounding_wall_ids and r.bounding_wall_ids[0].startswith("layered_") for r in on.canonical_rooms)
    # the shared pair is topology only: nothing is measured, published or projected for either part
    assert on.room_area_quantity_evidence == () and publish_live_floor_area_quantities(on) == ()
    assert {code for _room, code in on.same_view_room_area_first_failure_codes} == {"same_view_layered_ring_partition_part"}
