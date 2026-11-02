"""MAX handoffs 6543274611 / 6543894483 / 6544665680: records that share source members are neither SAME nor DISTINCT
unless a physical partition is proven from the source.

Written failing first: compare_identity returned CORROBORATED DISTINCT for any two records with different ids."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,
    _source_member_partition,
)
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import LAYERED, OTHER_WALL, PLAIN, _fixture, _ids, _selector

CORR = EvidenceResolutionStatus.CORROBORATED
CONF = EvidenceResolutionStatus.CONFLICT

# two windows in ONE wall: the pieces of both faces between them are support both openings rest on
TWO_WINDOWS = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (200.0, 100.0)), ((240.0, 100.0), (320.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (200.0, 110.0)), ((240.0, 110.0), (320.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
    ((200.0, 100.0), (200.0, 110.0)), ((240.0, 100.0), (240.0, 110.0)),
)
# two readings whose gaps touch at x=140 and that rest on the SAME jamb line there: a jamb is not wall support
SHARED_JAMB = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
    ((20.0, 120.0), (140.0, 120.0)), ((180.0, 120.0), (260.0, 120.0)),
    ((20.0, 130.0), (140.0, 130.0)), ((180.0, 130.0), (260.0, 130.0)),
    ((180.0, 120.0), (180.0, 130.0)),
)


@pytest.mark.parametrize("producer_owned", [True, False])
@pytest.mark.parametrize("kw", POSES)
def test_two_openings_sharing_wall_support_between_them_stay_distinct(kw, producer_owned):
    physical, published, ids, kw = _fixture(TWO_WINDOWS, producer_owned=producer_owned, **kw)
    members = _ids(ids, TWO_WINDOWS, kw)
    left, right = _selector(published, members[6]), _selector(published, members[9])
    first, second = physical.prove_existence(left), physical.prove_existence(right)
    assert first.status is CORR and second.status is CORR
    shared = set(first.existence_record.source_observation_ids) & set(second.existence_record.source_observation_ids)
    assert len(shared) == 2                       # the pieces of both faces between the two gaps
    result = physical.compare_identity(left, right)
    assert result.status is CORR and result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert result.reason_codes == (PHYSICAL_OPENING_IDENTITY_RESOLVED,) and not result.proven_same
    swapped = physical.compare_identity(right, left)
    assert swapped.status is CORR and swapped.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT


@pytest.mark.parametrize("kw", POSES)
def test_layer_records_of_one_gap_share_support_and_extent_so_they_are_neither_same_nor_distinct(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    left, right = _selector(published, members[6]), _selector(published, members[8])
    a, b = physical.prove_existence(left), physical.prove_existence(right)
    assert a.status is CORR and b.status is CORR and a.existence_record.record_id != b.existence_record.record_id
    assert set(a.existence_record.source_observation_ids) & set(b.existence_record.source_observation_ids)
    for pair in ((left, right), (right, left)):
        result = physical.compare_identity(*pair)
        assert result.status is CONF and not result.proven_same
        assert result.physical_opening_identity != PHYSICAL_OPENING_IDENTITIES_DISTINCT
        assert result.reason_codes == (PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,)


def test_a_seeded_record_for_merged_layers_overlaps_the_page_record_for_one_layer():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[6])
    page = physical.prove_existence(selector)
    seeded = physical.prove_seeded_existence(selector, members)
    assert page.status is CORR and seeded.status is CORR
    assert page.existence_record.record_id != seeded.existence_record.record_id
    failure, _source, _records, by_id, _restricted = physical._seeded_universe(selector, members)
    assert failure is None
    assert _source_member_partition(
        page.existence_record.source_observation_ids, seeded.existence_record.source_observation_ids, by_id,
    ) == "overlapping_extent"


def test_disjoint_openings_and_one_opening_compared_with_itself_are_unchanged():
    physical, published, ids, kw = _fixture(PLAIN + OTHER_WALL)
    plain = _ids(ids, PLAIN, kw)
    other = _ids(ids, OTHER_WALL, kw)
    left, right = _selector(published, plain[4]), _selector(published, other[4])
    distinct = physical.compare_identity(left, right)
    assert distinct.status is CORR and distinct.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    same = physical.compare_identity(left, _selector(published, plain[5]))
    assert same.status is CORR and same.proven_same and same.reason_codes == (PHYSICAL_OPENING_IDENTITY_RESOLVED,)


def test_the_partition_rule_on_sources_with_nothing_in_common_or_nothing_readable():
    physical, published, ids, kw = _fixture(TWO_WINDOWS)
    members = _ids(ids, TWO_WINDOWS, kw)
    selector = _selector(published, members[6])
    failure, _source, _records, by_id, _restricted = physical._seeded_universe(selector, members)
    assert failure is None
    left = members[:2] + members[3:5] + members[6:8]
    # no shared line and no readable extent for the other side: the partition is unproven, not "disjoint"
    assert _source_member_partition(left, members[2:3] + members[5:6] + members[8:10], by_id) == "unproven"
    assert _source_member_partition(tuple(members[:5]), tuple(members[3:8]), by_id) == "unproven"   # < 6 lines: no frame
    assert _source_member_partition(tuple(left), tuple(left), by_id) == "overlapping_extent"
    # the two windows' real six-line supports share the two middle pieces and have separate gaps
    first = tuple(sorted(set(members[:2]) | {members[3], members[4], members[6], members[7]}))
    second = tuple(sorted({members[1], members[2], members[4], members[5], members[8], members[9]}))
    assert set(first) & set(second) == {members[1], members[4]}
    assert _source_member_partition(first, second, by_id) == "partitioned"


def test_a_record_that_carries_its_own_source_measured_box_is_partitioned_by_that_box():
    shared = ("a", "b", "c")
    own = {"left_ids": ("a", "b", "x"), "right_ids": ("a", "b", "y")}
    apart = _source_member_partition(**own, records_by_id={}, left_box=(0, 0, 10, 10), right_box=(20, 0, 30, 10))
    touching = _source_member_partition(**own, records_by_id={}, left_box=(0, 0, 10, 10), right_box=(10, 0, 20, 10))
    overlapping = _source_member_partition(**own, records_by_id={}, left_box=(0, 0, 10, 10), right_box=(5, 2, 15, 8))
    contained = _source_member_partition(**own, records_by_id={}, left_box=(0, 0, 10, 10), right_box=(2, 2, 8, 8))
    one_sided = _source_member_partition(**own, records_by_id={}, left_box=(0, 0, 10, 10), right_box=None)
    assert (apart, touching, overlapping, contained, one_sided) == (
        "partitioned", "partitioned", "overlapping_extent", "overlapping_extent", "unproven")
    # the boxes decide even when no observation is shared
    assert _source_member_partition(("a", "b"), ("c", "d"), {}, left_box=(0, 0, 10, 10), right_box=(5, 5, 15, 15)) == (
        "overlapping_extent")
    assert _source_member_partition(("a", "b"), ("c", "d"), {}, left_box=(0, 0, 10, 10), right_box=(20, 0, 30, 10)) == "disjoint"
    assert shared


def test_a_shared_jamb_is_not_wall_support_even_when_the_gaps_only_touch():
    physical, published, ids, kw = _fixture(SHARED_JAMB)
    members = _ids(ids, SHARED_JAMB, kw)
    selector = _selector(published, members[4])
    failure, _source, _records, by_id, _restricted = physical._seeded_universe(selector, members)
    assert failure is None
    first = tuple(sorted(members[:6]))                                   # gap between x=100 and x=140
    second = tuple(sorted(members[6:11] + [members[5]]))                 # gap between x=140 and x=180, resting on the SAME jamb
    assert set(first) & set(second) == {members[5]}
    assert _source_member_partition(first, second, by_id) == "unproven"
