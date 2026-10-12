"""Exact duplicate source ownership stays negative without erasing other rings."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus
from test_source_room_face_local_ownership_abstain_v1 import _record, _rooms, _scope


def source_with_duplicate(count=1):
    rows = _rooms(5)
    rows[0] = SimpleNamespace(wall_candidate_id="room-top", wall_candidate=SimpleNamespace(
        centerline_pts=tuple((float(x), 0.) for x in range(0, 51, 10))))
    rows.append(SimpleNamespace(wall_candidate_id="alias", wall_candidate=SimpleNamespace(
        centerline_pts=tuple((float(x), 0.) for x in range(0, 10 * count + 1, 10)))))
    return rows


def test_exact_duplicate_has_all_owners_and_only_affected_face_is_withheld():
    rows = source_with_duplicate()
    clean = R._derive_scope(_scope(rows[:-1]))
    before = deepcopy(rows)
    out = R._derive_scope(_scope(rows))
    assert rows == before
    assert out.status is EvidenceResolutionStatus.CORROBORATED
    assert len(out.records) == 4 and len(out.abstained_faces) == 1
    assert out.face_universe_complete is False
    assert R.SOURCE_ROOM_FACE_DUPLICATE_EDGE in out.reason_codes
    withheld, = out.abstained_faces
    assert {"room-top", "alias"} <= set(withheld.bounding_wall_ids)
    baseline = {r.face_id: r for r in clean.records}
    assert all(r == baseline[r.face_id] for r in out.records)
    assert {r.face_id for r in out.records}.isdisjoint(out.ownership_evaluation.unresolved_face_ids)
    assert out.ownership_evaluation.competing_wall_ids == ("alias", "room-top")


@pytest.mark.parametrize("count", [3, 5])
def test_exact_duplicate_pollution_majority_still_blocks_every_publication(count):
    out = R._derive_scope(_scope(source_with_duplicate(count)))
    assert out.status is EvidenceResolutionStatus.ABSTAINED
    assert not out.records
    assert R.SOURCE_ROOM_FACE_DUPLICATE_EDGE in out.reason_codes


@pytest.mark.parametrize("turn,scale,shift", [(0, 1., (137., -42.)), (1, 1., (0., 0.)),
                                             (2, 2., (70., 90.)), (3, .5, (50., 40.))])
def test_duplicate_taint_transform_order_reversal_and_no_mutation(turn, scale, shift):
    def point(p):
        x, y = p
        for _ in range(turn):
            x, y = -y, x
        return x * scale + shift[0], y * scale + shift[1]
    rows = [SimpleNamespace(wall_candidate_id=r.wall_candidate_id,
        wall_candidate=SimpleNamespace(centerline_pts=tuple(point(p) for p in r.wall_candidate.centerline_pts)))
        for r in source_with_duplicate()]
    before = deepcopy(rows)
    out = R._derive_scope(_scope(rows))
    reverse = [SimpleNamespace(wall_candidate_id=r.wall_candidate_id,
        wall_candidate=SimpleNamespace(centerline_pts=tuple(reversed(r.wall_candidate.centerline_pts))))
        for r in reversed(rows)]
    assert R._derive_scope(_scope(reverse)) == out
    assert rows == before
    assert len(out.records) == 4 and len(out.abstained_faces) == 1
    assert {"room-top", "alias"} <= set(out.abstained_faces[0].bounding_wall_ids)
    assert out.face_universe_complete is False


def test_orphan_duplicate_keeps_existing_rings_and_universe_incomplete():
    rows = _rooms(5)
    baseline = R._derive_scope(_scope(rows))
    rows += [_record("orphan-a", (80., 0.), (90., 0.)),
             _record("orphan-b", (90., 0.), (80., 0.))]
    out = R._derive_scope(_scope(rows))
    assert out.records == baseline.records
    assert out.face_universe_complete is False
    assert R.SOURCE_ROOM_FACE_DUPLICATE_EDGE in out.reason_codes


def test_rechunked_competing_source_preserves_affected_region_and_all_owners():
    rows = source_with_duplicate()
    before = R._derive_scope(_scope(rows))
    rows[-1].wall_candidate.centerline_pts = ((0., 0.), (5., 0.), (10., 0.))
    after = R._derive_scope(_scope(rows))
    assert len(after.records) == len(before.records) == 4
    assert len(after.abstained_faces) == len(before.abstained_faces) == 1
    assert after.records == before.records
    a, b = after.abstained_faces[0], before.abstained_faces[0]
    assert a.area_page_pts2 == b.area_page_pts2 == 100.
    assert a.bounding_wall_ids == b.bounding_wall_ids
    assert after.face_universe_complete is False
