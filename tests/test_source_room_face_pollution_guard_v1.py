"""A degenerate face may be isolated only when it is an isolated defect.

On real drawings the linework often contains tile grids, hatch and fixtures, so
degenerate cells outnumber real rooms. Isolation would then publish the
remaining arbitrary cells as rooms. When degenerate faces are not a strict
minority of the scope, the wall-candidate pool itself is polluted and the whole
scope must abstain exactly as it did before candidate-local isolation.
"""
from __future__ import annotations

import random
from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_DEGENERATE,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
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
        document_id="doc-pollution",
        revision_id="rev-pollution",
        source_sha256="d" * 64,
        snapshot_id="snap-pollution",
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
    return _box("room", 0.0, 0.0, 20.0, 10.0) + [
        _record("partition", (10.0, 0.0), (10.0, 10.0))
    ]


def _specks(count):
    out = []
    for index in range(count):
        x = 30.0 + 2.0 * index
        out.extend(_box(f"speck{index}", x, 0.0, x + 0.5, 0.5))
    return out


def _assert_whole_scope_degenerate(result) -> None:
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.scope_complete is False
    assert result.records == ()
    assert result.abstained_faces == ()
    assert SOURCE_ROOM_FACE_DEGENERATE in result.reason_codes


def test_strict_minority_of_degenerate_faces_is_still_isolated() -> None:
    # 2 valid + 1 degenerate: the degenerate face is a strict minority.
    result = _derive_scope(_scope(_two_rooms() + _specks(1)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert SOURCE_ROOM_FACE_SCOPE_RESOLVED in result.reason_codes
    assert len(result.records) == 2
    assert len(result.abstained_faces) == 1


def test_degenerate_majority_fails_the_whole_scope() -> None:
    # 2 valid + 3 degenerate: degenerate faces dominate -> polluted pool.
    _assert_whole_scope_degenerate(_derive_scope(_scope(_two_rooms() + _specks(3))))


def test_exactly_half_degenerate_fails_the_whole_scope() -> None:
    # 2 valid + 2 degenerate: not a STRICT minority.
    _assert_whole_scope_degenerate(_derive_scope(_scope(_two_rooms() + _specks(2))))


def test_heavily_polluted_scope_publishes_no_arbitrary_cells() -> None:
    # Many valid-looking cells but far more degenerate ones, as on real sheets
    # with tile grids: nothing may be published.
    rooms = _box("hall", 0.0, 0.0, 30.0, 10.0) + [
        _record("p1", (10.0, 0.0), (10.0, 10.0)),
        _record("p2", (20.0, 0.0), (20.0, 10.0)),
    ]
    _assert_whole_scope_degenerate(_derive_scope(_scope(rooms + _specks(8))))


def test_only_degenerate_faces_still_fails_closed() -> None:
    _assert_whole_scope_degenerate(_derive_scope(_scope(_specks(3))))


def test_decision_is_input_order_invariant() -> None:
    for specks, expected_ok in ((1, True), (2, False), (3, False)):
        records = _two_rooms() + _specks(specks)
        baseline = _derive_scope(_scope(records))
        assert (baseline.status is EvidenceResolutionStatus.CORROBORATED) is expected_ok
        for seed in range(6):
            shuffled = list(records)
            random.Random(seed).shuffle(shuffled)
            assert _derive_scope(_scope(shuffled)) == baseline


def test_decision_is_translation_invariant() -> None:
    def shifted(records, dx, dy):
        out = []
        for r in records:
            a, b = r.wall_candidate.centerline_pts
            out.append(
                _record(r.wall_candidate_id, (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy))
            )
        return out

    for specks in (1, 3):
        records = _two_rooms() + _specks(specks)
        base = _derive_scope(_scope(records))
        moved = _derive_scope(_scope(shifted(records, 250.0, -90.0)))
        assert (moved.status, len(moved.records), len(moved.abstained_faces)) == (
            base.status,
            len(base.records),
            len(base.abstained_faces),
        )


def test_scope_without_degenerate_faces_is_unchanged() -> None:
    result = _derive_scope(_scope(_two_rooms()))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    assert result.abstained_faces == ()
