"""Live candidate-local ownership abstention for source room faces.

Competing authenticated wall owners are localizable only through the exact
competing edge span. A strict-minority contaminated set may be withheld while
the remaining faces must independently pass the existing topology proof.
Missing ownership and polluted/non-minority scopes remain whole-scope failures.
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus


def _record(wall_id, first, second):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=(first, second)),
    )


def _scope(records):
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        document_id="doc-local-own",
        revision_id="rev-local-own",
        source_sha256="f" * 64,
        snapshot_id="snap-local-own",
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )


def _box(prefix, x0, y0, x1, y1):
    return [
        _record(f"{prefix}-top", (x0, y0), (x1, y0)),
        _record(f"{prefix}-right", (x1, y0), (x1, y1)),
        _record(f"{prefix}-bottom", (x1, y1), (x0, y1)),
        _record(f"{prefix}-left", (x0, y1), (x0, y0)),
    ]


def _rooms(count):
    # Equal 10x10 rooms sharing interior partitions.
    return _box("room", 0.0, 0.0, 10.0 * count, 10.0) + [
        _record(
            f"partition-{index}",
            (10.0 * index, 0.0),
            (10.0 * index, 10.0),
        )
        for index in range(1, count)
    ]


def _two_room_top_overlap():
    # Source overlap is 5..15, spanning rooms one and two. Depending on traversal
    # the planarizer may hang its spur on either adjacent room, so the live rule
    # must use the full authenticated source-wall overlap rather than raw face id.
    return [_record("dup-top", (5.0, 0.0), (15.0, 0.0))]


def _three_room_top_overlap():
    # Source overlap is 5..25 -> rooms one, two and three are contaminated.
    return [_record("dup-top-wide", (5.0, 0.0), (25.0, 0.0))]


def _transform(records, fn):
    return [
        _record(
            row.wall_candidate_id,
            fn(row.wall_candidate.centerline_pts[0]),
            fn(row.wall_candidate.centerline_pts[1]),
        )
        for row in records
    ]


def _whole_scope_boundary_failure(result):
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.scope_complete is False
    assert result.records == ()
    assert result.abstained_faces == ()
    assert R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED in result.reason_codes


def test_two_of_five_competing_faces_abstain_locally() -> None:
    clean = R._derive_scope(_scope(_rooms(5)))
    result = R._derive_scope(_scope(_rooms(5) + _two_room_top_overlap()))

    assert clean.status is EvidenceResolutionStatus.CORROBORATED
    assert len(clean.records) == 5

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert result.face_universe_complete is False
    assert result.reason_codes == (
        R.SOURCE_ROOM_FACE_SCOPE_RESOLVED,
        R.SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    )
    assert len(result.records) == 3
    assert len(result.abstained_faces) == 2

    assert all(
        row.reason == R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED
        for row in result.abstained_faces
    )
    assert all(
        {"room-top", "dup-top"} <= set(row.bounding_wall_ids)
        for row in result.abstained_faces
    )
    assert {row.face_id for row in result.records}.isdisjoint(
        {row.face_id for row in result.abstained_faces}
    )

    # The three unaffected rooms retain their clean face identities.
    assert {row.face_id for row in result.records} < {
        row.face_id for row in clean.records
    }
    assert all(row.area_page_pts2 == pytest.approx(100.0) for row in result.records)


def test_published_faces_are_clean_in_the_ownership_audit() -> None:
    result = R._derive_scope(_scope(_rooms(5) + _two_room_top_overlap()))
    evaluation = result.ownership_evaluation

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert evaluation.status == R.OWNERSHIP_EVALUATION_EVALUATED
    published_ids = {row.face_id for row in result.records}
    assert published_ids <= set(evaluation.owned_face_ids)
    assert published_ids.isdisjoint(evaluation.unresolved_face_ids)
    assert evaluation.competing_wall_ids == ("dup-top", "room-top")


@pytest.mark.parametrize(
    "fn",
    [
        lambda p: (p[0] + 137.0, p[1] - 42.0),
        lambda p: (-p[1], p[0]),
        lambda p: (p[0] * 2.0, p[1] * 2.0),
    ],
    ids=["translate", "rotate90", "scale2"],
)
def test_local_ownership_decision_is_similarity_invariant(fn) -> None:
    records = _rooms(5) + _two_room_top_overlap()
    base = R._derive_scope(_scope(records))
    moved = R._derive_scope(_scope(_transform(records, fn)))

    assert (
        moved.status,
        moved.scope_complete,
        len(moved.records),
        tuple(a.reason for a in moved.abstained_faces),
        moved.reason_codes,
    ) == (
        base.status,
        base.scope_complete,
        len(base.records),
        tuple(a.reason for a in base.abstained_faces),
        base.reason_codes,
    )
    assert len(base.records) == 3 and len(base.abstained_faces) == 2


def test_local_ownership_decision_is_input_order_invariant() -> None:
    records = _rooms(5) + _two_room_top_overlap()
    baseline = R._derive_scope(_scope(records))

    for seed in range(10):
        shuffled = list(records)
        random.Random(seed).shuffle(shuffled)
        assert R._derive_scope(_scope(shuffled)) == baseline


def test_three_of_five_contaminated_faces_still_fail_the_whole_scope() -> None:
    result = R._derive_scope(_scope(_rooms(5) + _three_room_top_overlap()))
    _whole_scope_boundary_failure(result)


def test_missing_owner_still_fails_the_whole_scope(monkeypatch) -> None:
    # Partition splitting requires containment lookup for top/bottom subedges.
    # Simulate source ownership disappearing for those non-exact fragments.
    monkeypatch.setattr(R, "_containing_wall_ids", lambda *_a, **_kw: ())
    result = R._derive_scope(_scope(_rooms(5)))
    _whole_scope_boundary_failure(result)
    assert result.ownership_evaluation.unowned_edge_count > 0


def test_ownership_plus_degenerate_defects_must_be_strict_minority() -> None:
    records = (
        _rooms(5)
        + _two_room_top_overlap()
        + _box("speck", 60.0, 0.0, 60.5, 0.5)
    )
    # Six discovered faces: two competing-owner faces + one degenerate face =
    # exactly half. The generalized pollution guard must publish nothing.
    result = R._derive_scope(_scope(records))
    _whole_scope_boundary_failure(result)


def test_strict_minority_combined_defects_can_still_publish_independent_rooms() -> None:
    # Six real rooms + one degenerate speck = seven discovered faces. Two rooms
    # are ownership-contaminated, so three of seven are withheld (< half),
    # leaving four real rooms with independent two-sided topology.
    records = (
        _rooms(6)
        + _two_room_top_overlap()
        + _box("speck", 70.0, 0.0, 70.5, 0.5)
    )
    result = R._derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 4
    assert len(result.abstained_faces) == 3
    assert {a.reason for a in result.abstained_faces} == {
        R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
        R.SOURCE_ROOM_FACE_DEGENERATE,
    }


def test_competing_face_cannot_supply_two_sided_topology_to_survivors() -> None:
    result = R._derive_scope(_scope(_rooms(5) + _two_room_top_overlap()))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    published = {row.face_id for row in result.records}
    abstained = {row.face_id for row in result.abstained_faces}
    assert published.isdisjoint(abstained)
    assert len(published) == 3

    # The surviving three rooms independently contain shared interior walls;
    # the two contaminated rooms are not needed for two-sided proof.
    counts = {}
    for row in result.records:
        for wall_id in row.bounding_wall_ids:
            counts[wall_id] = counts.get(wall_id, 0) + 1
    assert any(count == 2 for count in counts.values())


def test_source_overlap_span_is_exact_and_excludes_point_contact() -> None:
    horizontal = R._edge((0.0, 0.0), (10.0, 0.0))
    overlap = R._edge((5.0, 0.0), (15.0, 0.0))
    endpoint_only = R._edge((10.0, 0.0), (20.0, 0.0))
    offset = R._edge((5.0, 0.001), (15.0, 0.001))

    assert R._collinear_overlap_edge(horizontal, overlap) == R._edge(
        (5.0, 0.0), (10.0, 0.0)
    )
    assert R._edges_share_positive_collinear_span(horizontal, overlap)
    assert R._collinear_overlap_edge(horizontal, endpoint_only) is None
    assert not R._edges_share_positive_collinear_span(horizontal, endpoint_only)
    assert R._collinear_overlap_edge(horizontal, offset) is None
    assert not R._edges_share_positive_collinear_span(horizontal, offset)
