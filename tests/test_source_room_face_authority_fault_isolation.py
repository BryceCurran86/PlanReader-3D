"""A degenerate room-face candidate is isolated; it does not poison independent faces.

Before this isolation, one tiny planar face made ``SourceRoomFaceAuthority`` abstain the
whole page scope. Planar faces are disjoint cells, so a degenerate cell cannot change an
unrelated face. What it can mean is that the walls around it are locally inconsistent,
so a face that shares a boundary edge with it may be an incomplete fragment of a larger
room. These tests pin the isolation contract:

* a degenerate face never publishes and keeps its provenance as a withheld candidate;
* faces sharing a boundary edge with it are withheld too (independence unproven);
* withheld faces never corroborate other faces (the multi-room component gate counts
  independent faces only);
* isolation only applies to an isolated defect (strict minority of degenerate faces);
* ownership violations still abstain the whole scope;
* scopes without a degenerate face are unchanged.

Synthetic wall geometry only; no project, file name, page, label or quantity is used.
"""
from __future__ import annotations

import copy
import random
from types import SimpleNamespace

import fitz
import pytest

import pb_source_room_face_authority as rfa
from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_RESOLVED,
    compose_live_canonical_rooms,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
    SOURCE_ROOM_FACE_CANDIDATES_WITHHELD,
    SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS,
    SOURCE_ROOM_FACE_DEGENERATE,
    SOURCE_ROOM_FACE_DUPLICATE_EDGE,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SOURCE_ROOM_FACE_SHARED_DEFECT,
    SourceRoomFaceSelector,
    _derive_scope,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer

SIZE = 100.0
CORROBORATED = EvidenceResolutionStatus.CORROBORATED
ABSTAINED = EvidenceResolutionStatus.ABSTAINED


def rec(wall_id, first, second):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=(first, second)),
    )


def scope_of(records):
    return SimpleNamespace(
        status=CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        document_id="doc-fault-isolation",
        revision_id="rev-fault-isolation",
        source_sha256="c" * 64,
        snapshot_id="snap-fault-isolation",
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )


def box(prefix, x0, y0, x1, y1):
    return [
        rec(f"{prefix}-n", (x0, y0), (x1, y0)),
        rec(f"{prefix}-e", (x1, y0), (x1, y1)),
        rec(f"{prefix}-s", (x1, y1), (x0, y1)),
        rec(f"{prefix}-w", (x0, y1), (x0, y0)),
    ]


def room_row(prefix, count, *, x0=0.0, y0=0.0):
    """``count`` rooms of SIZE x SIZE sharing partitions, one connected wall network."""
    x1 = x0 + count * SIZE
    records = [
        rec(f"{prefix}-top", (x0, y0), (x1, y0)),
        rec(f"{prefix}-bottom", (x1, y0 + SIZE), (x0, y0 + SIZE)),
        rec(f"{prefix}-west", (x0, y0 + SIZE), (x0, y0)),
        rec(f"{prefix}-east", (x1, y0), (x1, y0 + SIZE)),
    ]
    for index in range(1, count):
        x = x0 + index * SIZE
        records.append(rec(f"{prefix}-part{index}", (x, y0), (x, y0 + SIZE)))
    return records


def sliver_island(prefix, x0, y0, *, length=SIZE, thickness=0.5):
    """A free-standing thin box: area length*thickness, far below 1% of a room."""
    return box(prefix, x0, y0, x0 + length, y0 + thickness)


def sliver_beyond_east_end(prefix, count, *, thickness=0.5):
    """A thin strip sharing the east end wall of ``room_row(.., count)``."""
    x1 = count * SIZE
    return [
        rec(f"{prefix}-top", (x1, 0.0), (x1 + thickness, 0.0)),
        rec(f"{prefix}-bottom", (x1 + thickness, SIZE), (x1, SIZE)),
        rec(f"{prefix}-east", (x1 + thickness, 0.0), (x1 + thickness, SIZE)),
    ]


def sliver_along_bottom(prefix, count, *, thickness=0.25):
    """A thin strip sharing the bottom edge of every room of ``room_row(.., count)``."""
    x1 = count * SIZE
    return [
        rec(f"{prefix}-west", (0.0, SIZE), (0.0, SIZE + thickness)),
        rec(f"{prefix}-east", (x1, SIZE), (x1, SIZE + thickness)),
        rec(f"{prefix}-lower", (0.0, SIZE + thickness), (x1, SIZE + thickness)),
    ]


def stray_line_inside_room(prefix, room_index, *, offset=0.25):
    """A stray authenticated line close to a room's north wall: it splits off a sliver."""
    x0 = room_index * SIZE
    return [rec(f"{prefix}-line", (x0, offset), (x0 + SIZE, offset))]


def derive(records):
    return _derive_scope(scope_of(records))


def areas(result):
    return sorted(round(record.area_page_pts2, 3) for record in result.records)


def withheld_reasons(result):
    return sorted(candidate.reason_code for candidate in result.withheld_candidates)


# --------------------------------------------------------------------------------------
# 1. one degenerate face does not destroy unrelated valid room faces
# --------------------------------------------------------------------------------------


def test_degenerate_island_does_not_destroy_unrelated_valid_faces():
    baseline = derive(room_row("row", 3))
    assert baseline.status is CORROBORATED and len(baseline.records) == 3

    result = derive(room_row("row", 3) + sliver_island("sliver", 0.0, 500.0))

    assert result.status is CORROBORATED
    assert result.scope_complete is True
    assert result.records == baseline.records
    assert result.face_universe_complete is False
    assert result.reason_codes == (
        SOURCE_ROOM_FACE_SCOPE_RESOLVED,
        SOURCE_ROOM_FACE_CANDIDATES_WITHHELD,
    )
    assert withheld_reasons(result) == [SOURCE_ROOM_FACE_DEGENERATE]
    (candidate,) = result.withheld_candidates
    assert candidate.area_page_pts2 == pytest.approx(50.0)
    assert candidate.caused_by_face_ids == ()
    assert candidate.face_id not in {record.face_id for record in result.records}


def test_original_failure_mode_one_tiny_face_no_longer_rejects_the_page_scope():
    # Same geometry that used to abstain the whole scope with SOURCE_ROOM_FACE_DEGENERATE.
    result = derive(room_row("row", 4) + sliver_island("sliver", 0.0, 500.0))
    assert result.status is CORROBORATED
    assert len(result.records) == 4
    assert SOURCE_ROOM_FACE_DEGENERATE not in result.reason_codes


# --------------------------------------------------------------------------------------
# 2. faces that share an edge with a degenerate face are withheld; far faces survive
# --------------------------------------------------------------------------------------


def test_face_sharing_an_edge_with_a_degenerate_face_is_withheld_far_faces_survive():
    records = room_row("row", 4) + sliver_beyond_east_end("sliver", 4)
    result = derive(records)

    assert result.status is CORROBORATED
    assert len(result.records) == 3
    assert withheld_reasons(result) == sorted(
        [SOURCE_ROOM_FACE_DEGENERATE, SOURCE_ROOM_FACE_SHARED_DEFECT]
    )
    sliver = next(c for c in result.withheld_candidates if c.reason_code == SOURCE_ROOM_FACE_DEGENERATE)
    neighbour = next(c for c in result.withheld_candidates if c.reason_code == SOURCE_ROOM_FACE_SHARED_DEFECT)
    assert neighbour.caused_by_face_ids == (sliver.face_id,)
    assert neighbour.area_page_pts2 == pytest.approx(SIZE * SIZE)
    # the neighbour is the room at the east end; the published rooms are the other three
    assert max(x for x, _y in neighbour.polygon_pdf_pts) == pytest.approx(4 * SIZE)
    assert min(x for x, _y in neighbour.polygon_pdf_pts) == pytest.approx(3 * SIZE)
    for record in result.records:
        assert max(x for x, _y in record.polygon_pdf_pts) <= 3 * SIZE + 1e-9


def test_stray_line_that_splits_a_sliver_off_a_room_withholds_the_remaining_fragment():
    # The stray line cuts a 25 pt^2 sliver off the last room. The remaining 9,975 pt^2
    # face looks valid but is an incomplete fragment of that room, so it must not publish.
    # The room across the partition also touches the sliver (at its corner), so its
    # independence cannot be proven either; the two rooms further away are untouched.
    baseline = derive(room_row("row", 4))
    result = derive(room_row("row", 4) + stray_line_inside_room("stray", 3))

    assert result.status is CORROBORATED
    assert len(result.records) == 2
    assert result.records == tuple(
        record for record in baseline.records if max(x for x, _y in record.polygon_pdf_pts) <= 2 * SIZE + 1e-9
    )
    assert withheld_reasons(result) == sorted(
        [SOURCE_ROOM_FACE_DEGENERATE, SOURCE_ROOM_FACE_SHARED_DEFECT, SOURCE_ROOM_FACE_SHARED_DEFECT]
    )
    fragment = max(
        (c for c in result.withheld_candidates if c.reason_code == SOURCE_ROOM_FACE_SHARED_DEFECT),
        key=lambda c: min(x for x, _y in c.polygon_pdf_pts),
    )
    assert fragment.area_page_pts2 == pytest.approx(SIZE * SIZE - 25.0)
    assert len(fragment.caused_by_face_ids) == 1


def test_withheld_faces_never_corroborate_the_component_gate():
    # Two rooms plus a sliver beside the second: only one independent face is left, and
    # one face alone is a box, not multi-room topology. Nothing publishes.
    result = derive(room_row("row", 2) + sliver_beyond_east_end("sliver", 2))
    assert result.status is ABSTAINED
    assert result.scope_complete is False
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_DEGENERATE,)


def test_a_sliver_touching_every_room_leaves_no_independent_face_and_fails_closed():
    result = derive(room_row("row", 3) + sliver_along_bottom("sliver", 3))
    assert result.status is ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_DEGENERATE,)


# --------------------------------------------------------------------------------------
# 3. genuinely invalid shared topology still fails closed
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "islands, publishes",
    [(0, True), (1, True), (2, True), (3, False), (4, False), (5, False)],
)
def test_isolation_requires_degenerate_faces_to_be_a_strict_minority(islands, publishes):
    # three valid rooms; "islands" free-standing slivers. Degenerate faces must be fewer than
    # half of all bounded faces: 3 rooms + 3 slivers is exactly half and abstains.
    records = room_row("row", 3)
    for index in range(islands):
        records += sliver_island(f"sliver{index}", 0.0, 500.0 + index * 40.0)
    result = derive(records)
    if publishes:
        assert result.status is CORROBORATED
        assert len(result.records) == 3
        assert result.face_universe_complete is (islands == 0)
    else:
        assert result.status is ABSTAINED
        assert result.records == ()
        assert result.reason_codes == (SOURCE_ROOM_FACE_DEGENERATE,)


def test_duplicate_boundary_ownership_still_abstains_the_whole_scope():
    records = room_row("row", 3) + box("dup-a", 0.0, 500.0, 200.0, 600.0)
    records += [rec("dup-b-n", (0.0, 500.0), (200.0, 500.0))]  # a second wall on the same edge
    result = derive(records)
    assert result.status is ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_DUPLICATE_EDGE,)


def test_unresolved_boundary_ownership_still_abstains_the_whole_scope(monkeypatch):
    real = rfa._unique_containing_wall_owner
    seen = {"calls": 0}

    def losing_one_edge(edge, *, edge_owner, wall_edges):
        seen["calls"] += 1
        return None if seen["calls"] == 3 else real(edge, edge_owner=edge_owner, wall_edges=wall_edges)

    monkeypatch.setattr(rfa, "_unique_containing_wall_owner", losing_one_edge)
    result = derive(room_row("row", 3) + sliver_island("sliver", 0.0, 500.0))
    assert result.status is ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,)


def test_incomplete_or_uncorroborated_wall_scopes_still_abstain():
    scope = scope_of(room_row("row", 3))
    scope.scope_complete = False
    assert _derive_scope(scope).status is ABSTAINED
    scope = scope_of(room_row("row", 3))
    scope.status = EvidenceResolutionStatus.CANDIDATE
    assert _derive_scope(scope).status is ABSTAINED


def test_a_lone_box_still_cannot_mint_room_authority_even_with_an_isolated_defect():
    # one valid room + one degenerate island = 50% degenerate: the box gate and the strict
    # minority rule both keep this closed.
    result = derive(box("lone", 0.0, 0.0, SIZE, SIZE) + sliver_island("sliver", 0.0, 500.0))
    assert result.status is ABSTAINED
    assert result.records == ()


# --------------------------------------------------------------------------------------
# 4. candidate provenance survives filtering
# --------------------------------------------------------------------------------------


def test_published_records_and_withheld_candidates_keep_exact_provenance():
    baseline = derive(room_row("row", 3))
    result = derive(room_row("row", 3) + sliver_island("sliver", 0.0, 500.0))

    for kept, original in zip(result.records, baseline.records):
        assert kept.face_id == original.face_id
        assert kept.record_id == original.record_id
        assert kept.polygon_pdf_pts == original.polygon_pdf_pts
        assert kept.bounding_wall_ids == original.bounding_wall_ids
        assert kept.area_page_pts2 == original.area_page_pts2
        assert (kept.document_id, kept.revision_id, kept.source_sha256, kept.snapshot_id, kept.page_id, kept.decision_scope_id) == (
            "doc-fault-isolation", "rev-fault-isolation", "c" * 64, "snap-fault-isolation", "1", "wall-source:page-1",
        )
    (candidate,) = result.withheld_candidates
    assert set(candidate.bounding_wall_ids) == {"sliver-n", "sliver-e", "sliver-s", "sliver-w"}
    assert len(candidate.polygon_pdf_pts) == 4
    assert candidate.candidate_id.startswith("source_room_face_withheld_")
    assert candidate.face_id.startswith("source_room_face_")
    assert derive(room_row("row", 3) + sliver_island("sliver", 0.0, 500.0)).withheld_candidates == result.withheld_candidates


# --------------------------------------------------------------------------------------
# 5. ABSTAIN / CONFLICT evidence can never destroy valid output; clean scopes unchanged
# --------------------------------------------------------------------------------------


def test_scopes_without_a_degenerate_face_are_unchanged():
    result = derive(room_row("row", 2))
    assert result.status is CORROBORATED
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_RESOLVED,)
    assert result.face_universe_complete is True
    assert result.withheld_candidates == ()
    assert areas(result) == [SIZE * SIZE, SIZE * SIZE]
    lone = derive(box("lone", 0.0, 0.0, SIZE, SIZE))
    assert lone.status is ABSTAINED
    assert lone.reason_codes == (SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS,)


def test_adding_isolated_junk_never_changes_or_removes_valid_faces_seeded_property():
    rng = random.Random(20261004)
    for _ in range(25):
        rooms = rng.randint(2, 5)
        junk = rng.randint(0, rooms - 1)  # strict minority: junk < rooms
        valid = room_row("row", rooms)
        baseline = derive(valid)
        records = list(valid)
        for index in range(junk):
            records += sliver_island(
                f"junk{index}",
                rng.uniform(-50.0, 50.0),
                400.0 + 60.0 * index + rng.uniform(0.0, 20.0),
                length=rng.uniform(40.0, 150.0),
                thickness=rng.uniform(0.2, 0.6),
            )
        result = derive(records)
        assert result.status is CORROBORATED
        assert result.records == baseline.records
        assert len(result.withheld_candidates) == junk


# --------------------------------------------------------------------------------------
# 6. metamorphic and invariance
# --------------------------------------------------------------------------------------


def transformed(records, fn):
    return [
        rec(r.wall_candidate_id, fn(*r.wall_candidate.centerline_pts[0]), fn(*r.wall_candidate.centerline_pts[1]))
        for r in records
    ]


def mixed_scope():
    return room_row("row", 4) + sliver_beyond_east_end("sliver", 4) + sliver_island("island", 0.0, 500.0)


def summary(result):
    return (
        result.status,
        len(result.records),
        areas(result),
        sorted((c.reason_code, round(c.area_page_pts2, 3)) for c in result.withheld_candidates),
    )


def test_translation_keeps_isolation():
    base = derive(mixed_scope())
    moved = derive(transformed(mixed_scope(), lambda x, y: (x + 137.5, y - 42.25)))
    assert summary(moved) == summary(base)


@pytest.mark.parametrize(
    "fn",
    [lambda x, y: (-y, x), lambda x, y: (-x, -y), lambda x, y: (y, -x)],
    ids=["quarter", "half", "three-quarter"],
)
def test_quarter_turns_keep_isolation(fn):
    assert summary(derive(transformed(mixed_scope(), fn))) == summary(derive(mixed_scope()))


def test_uniform_scale_keeps_isolation():
    assert summary(derive(transformed(mixed_scope(), lambda x, y: (x * 4.0, y * 4.0)))) == (
        lambda s: (s[0], s[1], [a * 16.0 for a in s[2]], [(r, a * 16.0) for r, a in s[3]])
    )(summary(derive(mixed_scope())))


def test_input_order_does_not_change_the_result():
    records = mixed_scope()
    shuffled = list(records)
    random.Random(7).shuffle(shuffled)
    assert derive(shuffled) == derive(records)


def test_splitting_walls_into_collinear_pieces_does_not_change_published_geometry():
    records = mixed_scope()
    split = []
    for r in records:
        (ax, ay), (bx, by) = r.wall_candidate.centerline_pts
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        if (ax, ay) == (mx, my) or (bx, by) == (mx, my):
            split.append(r)
            continue
        split.append(rec(r.wall_candidate_id + "-a", (ax, ay), (mx, my)))
        split.append(rec(r.wall_candidate_id + "-b", (mx, my), (bx, by)))
    assert summary(derive(split)) == summary(derive(records))


def test_unrelated_far_content_does_not_change_other_faces():
    base = derive(room_row("row", 3) + sliver_island("sliver", 0.0, 500.0))
    wider = derive(
        room_row("row", 3)
        + sliver_island("sliver", 0.0, 500.0)
        + room_row("far", 2, x0=5000.0, y0=5000.0)
    )
    assert wider.status is CORROBORATED
    assert set(base.records) <= set(wider.records)
    assert len(wider.records) == len(base.records) + 2


def test_replay_is_deterministic_and_never_mutates_the_input_scope():
    scope = scope_of(mixed_scope())
    before = copy.deepcopy(scope)
    first = _derive_scope(scope)
    second = _derive_scope(scope)
    assert first == second
    assert scope.records == before.records
    assert [(r.wall_candidate_id, r.wall_candidate.centerline_pts) for r in scope.records] == [
        (r.wall_candidate_id, r.wall_candidate.centerline_pts) for r in before.records
    ]


# --------------------------------------------------------------------------------------
# 7. the real producer chain: PDF -> wall scope -> room faces -> canonical rooms
# --------------------------------------------------------------------------------------


def _pdf_with_island(island_width, island_height) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    x0, y0 = 40.0, 60.0
    lines = [
        ((x0, y0), (x0 + 300, y0)),
        ((x0 + 300, y0 + SIZE), (x0, y0 + SIZE)),
        ((x0, y0 + SIZE), (x0, y0)),
        ((x0 + 300, y0), (x0 + 300, y0 + SIZE)),
        ((x0 + 100, y0), (x0 + 100, y0 + SIZE)),
        ((x0 + 200, y0), (x0 + 200, y0 + SIZE)),
    ]
    ax, ay = 150.0, 220.0
    lines += [
        ((ax, ay), (ax + island_width, ay)),
        ((ax + island_width, ay), (ax + island_width, ay + island_height)),
        ((ax + island_width, ay + island_height), (ax, ay + island_height)),
        ((ax, ay + island_height), (ax, ay)),
    ]
    for first, second in lines:
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _live_chain(payload: bytes):
    source = SourceVisibilityProducer(producer_method="fault-isolation-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="fault-isolation-doc",
        source_bytes=payload,
        source_locator="memory://fault-isolation.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    faces = build_source_room_face_authority(composition.physical_wall_candidate_authority).resolve_scope(
        SourceRoomFaceSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=composition
    )
    return faces, rooms


def test_real_producer_chain_publishes_independent_rooms_around_a_degenerate_island():
    faces, rooms = _live_chain(_pdf_with_island(16.0, 5.0))

    assert faces.status is CORROBORATED and faces.scope_complete is True
    assert len(faces.records) == 3
    assert faces.face_universe_complete is False
    assert [c.reason_code for c in faces.withheld_candidates] == [SOURCE_ROOM_FACE_DEGENERATE]
    assert rooms.status is CORROBORATED
    assert len(rooms.rooms) == 3
    assert rooms.reason_codes == (LIVE_CANONICAL_ROOM_RESOLVED, SOURCE_ROOM_FACE_CANDIDATES_WITHHELD)
    assert {room.source_room_face_record_id for room in rooms.rooms} == {r.record_id for r in faces.records}
    assert all(room.geometry_complete and not room.metric_geometry_complete for room in rooms.rooms)


def test_real_producer_chain_without_a_degenerate_face_is_unchanged():
    faces, rooms = _live_chain(_pdf_with_island(60.0, 60.0))
    assert faces.status is CORROBORATED
    assert faces.face_universe_complete is True
    assert faces.withheld_candidates == ()
    assert faces.reason_codes == (SOURCE_ROOM_FACE_SCOPE_RESOLVED,)
    assert rooms.reason_codes == (LIVE_CANONICAL_ROOM_RESOLVED,)
