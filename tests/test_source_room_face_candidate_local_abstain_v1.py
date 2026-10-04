"""DEF-04: a degenerate face abstains locally; shared invalid topology still fails closed."""
from __future__ import annotations

import random
from types import SimpleNamespace

import pb_source_room_face_authority as authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS,
    SOURCE_ROOM_FACE_DEGENERATE,
    SOURCE_ROOM_FACE_DUPLICATE_EDGE,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    _derive_scope,
)


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
        document_id="doc-def04",
        revision_id="rev-def04",
        source_sha256="c" * 64,
        snapshot_id="snap-def04",
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


def _two_rooms():
    # Two 10x10 rooms sharing a partition.
    return _box("room", 0.0, 0.0, 20.0, 10.0) + [
        _record("partition", (10.0, 0.0), (10.0, 10.0))
    ]


def _faces(result):
    return {row.face_id for row in result.records}


def test_thresholds_are_unchanged() -> None:
    assert authority._TINY_RELATIVE_THRESHOLD == 0.01
    assert authority._ABSOLUTE_DEGENERATE_AREA_PT2 == 1.0


def test_detached_degenerate_face_does_not_destroy_valid_rooms() -> None:
    result = _derive_scope(_scope(_two_rooms() + _box("speck", 30.0, 0.0, 30.5, 0.5)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert result.face_universe_complete is False
    assert len(result.records) == 2
    assert SOURCE_ROOM_FACE_SCOPE_RESOLVED in result.reason_codes
    assert SOURCE_ROOM_FACE_UNIVERSE_PARTIAL in result.reason_codes
    # The abstention is explicit and carries provenance; it is not silent.
    assert len(result.abstained_faces) == 1
    abstained = result.abstained_faces[0]
    assert abstained.reason == SOURCE_ROOM_FACE_DEGENERATE
    assert set(abstained.bounding_wall_ids) == {
        "speck-top",
        "speck-right",
        "speck-bottom",
        "speck-left",
    }
    assert abstained.area_page_pts2 < authority._ABSOLUTE_DEGENERATE_AREA_PT2
    assert abstained.face_id not in _faces(result)
    assert abstained.document_id == "doc-def04"
    assert abstained.decision_scope_id == "wall-source:page-1"


def test_valid_face_ids_and_records_are_unaffected_by_the_degenerate_neighbour() -> None:
    clean = _derive_scope(_scope(_two_rooms()))
    noisy = _derive_scope(_scope(_two_rooms() + _box("speck", 30.0, 0.0, 30.5, 0.5)))

    assert clean.status is EvidenceResolutionStatus.CORROBORATED
    assert clean.abstained_faces == ()
    assert clean.face_universe_complete is True
    assert noisy.face_universe_complete is False
    assert [(r.record_id, r.face_id, r.bounding_wall_ids) for r in noisy.records] == [
        (r.record_id, r.face_id, r.bounding_wall_ids) for r in clean.records
    ]


def test_sliver_strip_attached_to_valid_rooms_abstains_locally() -> None:
    # A 0.04pt wall-body strip along the top of both rooms.
    records = _two_rooms() + [
        _record("strip-top", (0.0, -0.04), (20.0, -0.04)),
        _record("strip-left", (0.0, -0.04), (0.0, 0.0)),
        _record("strip-right", (20.0, 0.0), (20.0, -0.04)),
    ]
    result = _derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    assert len(result.abstained_faces) >= 1
    assert all(a.reason == SOURCE_ROOM_FACE_DEGENERATE for a in result.abstained_faces)


def test_degenerate_face_does_not_supply_two_sided_evidence_for_a_lone_box() -> None:
    # Component A: two real rooms. Component B: a lone box plus a sliver strip.
    # The sliver must not make the lone box look like it has a two-sided
    # interior boundary, so only component A's rooms are published.
    lone = _box("lone", 40.0, 0.0, 50.0, 10.0) + [
        _record("strip-top", (40.0, -0.04), (50.0, -0.04)),
        _record("strip-left", (40.0, -0.04), (40.0, 0.0)),
        _record("strip-right", (50.0, 0.0), (50.0, -0.04)),
    ]
    result = _derive_scope(_scope(_two_rooms() + lone))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    published_walls = {w for row in result.records for w in row.bounding_wall_ids}
    assert not any(w.startswith("lone-") for w in published_walls)
    assert len(result.abstained_faces) == 1


def test_scope_with_only_degenerate_faces_still_fails_closed() -> None:
    result = _derive_scope(_scope(_box("speck", 0.0, 0.0, 0.5, 0.5)))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.scope_complete is False
    assert result.records == ()
    assert SOURCE_ROOM_FACE_DEGENERATE in result.reason_codes


def test_shared_invalid_topology_still_fails_closed_despite_valid_rooms() -> None:
    # Two different wall ids own the same exact edge: shared topology is
    # untrustworthy for every face, so the whole scope fails closed.
    records = _two_rooms() + [_record("duplicate", (0.0, 0.0), (20.0, 0.0))]
    result = _derive_scope(_scope(records + _box("speck", 30.0, 0.0, 30.5, 0.5)))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert SOURCE_ROOM_FACE_DUPLICATE_EDGE in result.reason_codes


def test_face_just_above_the_relative_threshold_is_published() -> None:
    # 10x10 room (100) and a 0.2x10 room (2.0 = 2%): both above 1% and 1pt2.
    records = _box("room", 0.0, 0.0, 10.2, 10.0) + [
        _record("partition", (10.0, 0.0), (10.0, 10.0))
    ]
    result = _derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    assert result.abstained_faces == ()


def test_face_below_the_absolute_threshold_is_abstained_not_published() -> None:
    # Two 10x10 rooms plus a 0.05x10 strip room (0.5 pt2 < 1.0 absolute).
    records = _box("room", 0.0, 0.0, 20.05, 10.0) + [
        _record("partition-a", (10.0, 0.0), (10.0, 10.0)),
        _record("partition-b", (20.0, 0.0), (20.0, 10.0)),
    ]
    result = _derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    assert len(result.abstained_faces) == 1
    assert result.abstained_faces[0].area_page_pts2 < 1.0


def test_replay_and_input_order_invariance() -> None:
    records = _two_rooms() + _box("speck", 30.0, 0.0, 30.5, 0.5)
    baseline = _derive_scope(_scope(records))
    for seed in range(8):
        shuffled = list(records)
        random.Random(seed).shuffle(shuffled)
        again = _derive_scope(_scope(shuffled))
        assert again == baseline


def test_translation_invariance_of_the_decision() -> None:
    def shifted(dx, dy):
        out = []
        for r in _two_rooms() + _box("speck", 30.0, 0.0, 30.5, 0.5):
            (a, b) = r.wall_candidate.centerline_pts
            out.append(
                _record(
                    r.wall_candidate_id,
                    (a[0] + dx, a[1] + dy),
                    (b[0] + dx, b[1] + dy),
                )
            )
        return out

    base = _derive_scope(_scope(shifted(0.0, 0.0)))
    moved = _derive_scope(_scope(shifted(137.0, -42.0)))
    assert (moved.status, len(moved.records), len(moved.abstained_faces)) == (
        base.status,
        len(base.records),
        len(base.abstained_faces),
    )
