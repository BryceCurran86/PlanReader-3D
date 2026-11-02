"""Owner directive 2026-11-02: two openings with DIFFERENT source observations but OVERLAPPING original aperture extents
must not be classified DISTINCT. The source geometry and its physical partition decide, not the ids.

Written failing first: compare_identity (and the receipt) called any pair that shared no observation DISTINCT."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,
    _StructureFrame,
    _apertures_overlap,
    _source_member_partition_detail,
)
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import OTHER_WALL, PLAIN, _fixture, _ids, _selector

CORR = EvidenceResolutionStatus.CORROBORATED
CONF = EvidenceResolutionStatus.CONFLICT

# the SAME stretch of wall read twice: two complete six-line structures that share no line and whose gaps and depth overlap
TWO_READINGS = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
    ((20.0, 100.5), (102.0, 100.5)), ((142.0, 100.5), (220.0, 100.5)),
    ((20.0, 110.5), (102.0, 110.5)), ((142.0, 110.5), (220.0, 110.5)),
    ((102.0, 100.5), (102.0, 110.5)), ((142.0, 100.5), (142.0, 110.5)),
)
# two openings in one wall line with nothing in common and a stretch of plain wall between them
APART_PAIR = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (180.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (180.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
    ((200.0, 100.0), (240.0, 100.0)), ((280.0, 100.0), (320.0, 100.0)),
    ((200.0, 110.0), (240.0, 110.0)), ((280.0, 110.0), (320.0, 110.0)),
    ((240.0, 100.0), (240.0, 110.0)), ((280.0, 100.0), (280.0, 110.0)),
)


@pytest.mark.parametrize("producer_owned", [True, False])
@pytest.mark.parametrize("kw", POSES)
def test_openings_with_different_observations_but_overlapping_extents_are_not_distinct(kw, producer_owned):
    physical, published, ids, kw = _fixture(TWO_READINGS, producer_owned=producer_owned, **kw)
    members = _ids(ids, TWO_READINGS, kw)
    left, right = _selector(published, members[4]), _selector(published, members[10])
    first, second = physical.prove_existence(left), physical.prove_existence(right)
    assert first.status is CORR and second.status is CORR
    assert first.existence_record.record_id != second.existence_record.record_id
    assert not set(first.existence_record.source_observation_ids) & set(second.existence_record.source_observation_ids)
    for pair in ((left, right), (right, left)):
        result = physical.compare_identity(*pair)
        assert result.status is CONF and not result.proven_same
        assert result.physical_opening_identity != PHYSICAL_OPENING_IDENTITIES_DISTINCT
        assert result.reason_codes == (PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,)
    receipt = physical.partition_receipt(left, right)
    assert receipt.status is CONF and receipt.partition == "overlapping_extent" and not receipt.is_physically_distinct
    assert receipt.basis == "native_aperture_extents" and receipt.shared_source_observation_ids == ()
    assert len(receipt.left_extent) == len(receipt.right_extent) == 4
    assert receipt == physical.partition_receipt(right, left) and physical.verify_partition_receipt(receipt, right, left)


@pytest.mark.parametrize("kw", POSES)
def test_openings_with_nothing_in_common_and_separate_extents_stay_distinct(kw):
    physical, published, ids, kw = _fixture(APART_PAIR, **kw)
    members = _ids(ids, APART_PAIR, kw)
    left, right = _selector(published, members[4]), _selector(published, members[10])
    first, second = physical.prove_existence(left), physical.prove_existence(right)
    assert first.status is CORR and second.status is CORR
    result = physical.compare_identity(left, right)
    assert result.status is CORR and result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    receipt = physical.partition_receipt(left, right)
    assert receipt.partition == "disjoint" and receipt.is_physically_distinct and receipt.basis == "native_aperture_extents"
    assert receipt.left_extent[1] <= receipt.right_extent[0] + 1e-5 or receipt.right_extent[1] <= receipt.left_extent[0] + 1e-5


def test_the_same_gap_in_walls_at_different_depths_is_two_openings():
    physical, published, ids, kw = _fixture(PLAIN + OTHER_WALL)
    plain, other = _ids(ids, PLAIN, kw), _ids(ids, OTHER_WALL, kw)
    left, right = _selector(published, plain[4]), _selector(published, other[4])
    assert physical.compare_identity(left, right).physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    receipt = physical.partition_receipt(left, right)
    assert receipt.partition == "disjoint" and receipt.basis == "native_aperture_extents"


def test_extents_that_cannot_be_read_are_unproven_even_when_no_observation_is_shared():
    assert _source_member_partition_detail(("a", "b"), ("c", "d"), {})[:2] == ("unproven", "native_aperture_extents")
    one_sided = _source_member_partition_detail(("a",), ("b",), {}, left_box=(0, 0, 10, 10), right_box=None)
    assert one_sided[:2] == ("unproven", "raster_aperture_box")


def test_raster_boxes_decide_with_or_without_shared_observations():
    overlapping = (0, 0, 10, 10), (5, 5, 15, 15)
    apart = (0, 0, 10, 10), (20, 0, 30, 10)
    for shared_ids in (("a",), ("z",)):                                   # ("a",) vs ("a",...) share; ("z",) does not
        left_ids, right_ids = ("a", "b"), (shared_ids[0], "c")
        assert _source_member_partition_detail(left_ids, right_ids, {}, left_box=overlapping[0], right_box=overlapping[1])[0] == (
            "overlapping_extent")
    assert _source_member_partition_detail(("a",), ("b",), {}, left_box=apart[0], right_box=apart[1]) == (
        "disjoint", "raster_aperture_box", apart[0], apart[1])
    assert _source_member_partition_detail(("a", "b"), ("a", "c"), {}, left_box=apart[0], right_box=apart[1])[0] == "partitioned"


def _frame(direction, normal, start, end, low, high):
    return _StructureFrame(direction, normal, start, end, (low, high), ((), ()))


def test_apertures_in_the_same_wall_band_overlap_by_gap_and_depth_and_other_orientations_by_area():
    d, n = (1.0, 0.0), (0.0, 1.0)
    base = _frame(d, n, 100.0, 140.0, 100.0, 110.0)
    assert _apertures_overlap(base, _frame(d, n, 102.0, 142.0, 100.5, 110.5))             # same stretch, same depth
    assert _apertures_overlap(base, _frame(d, n, 120.0, 160.0, 105.0, 115.0))
    assert _apertures_overlap(base, _frame(d, n, 100.0, 140.0, 110.0, 115.0))             # stacked layer of the same gap
    assert not _apertures_overlap(base, _frame(d, n, 140.0, 180.0, 100.0, 110.0))         # next gap along the wall
    assert not _apertures_overlap(base, _frame(d, n, 100.0, 140.0, 300.0, 305.0))         # same gap in a wall far away
    assert not _apertures_overlap(base, _frame(d, n, 100.0, 140.0, 112.0, 120.0))         # separated depth, no shared band
    flipped = _frame((-1.0, 0.0), (0.0, -1.0), -140.0, -100.0, -110.0, -100.0)            # the same aperture, axes reversed
    assert _apertures_overlap(base, flipped)
    vertical = lambda x0, x1, y0, y1: _frame((0.0, 1.0), (-1.0, 0.0), y0, y1, -x1, -x0)    # a wall running the other way
    assert _apertures_overlap(base, vertical(115.0, 125.0, 95.0, 115.0))                  # crosses the aperture
    assert not _apertures_overlap(base, vertical(300.0, 310.0, 95.0, 115.0))
