"""MAX decision 6549912542: a producer-owned, re-provable pairwise partition receipt for the composer.

The composer must never take a partition from a caller. It asks the authority, which re-proves both existence records
from the source, and it can verify a receipt only by the authority recomputing it."""
from __future__ import annotations

from dataclasses import fields, replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,
    PhysicalOpeningPartitionReceipt,
    _source_member_partition,
    _source_member_partition_detail,
)
from test_physical_opening_identity_partition_v1 import SHARED_JAMB, TWO_WINDOWS
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import LAYERED, OTHER_WALL, PLAIN, _fixture, _ids, _selector

CORR = EvidenceResolutionStatus.CORROBORATED
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT


def _two_windows(kw, producer_owned=True):
    physical, published, ids, kw = _fixture(TWO_WINDOWS, producer_owned=producer_owned, **kw)
    members = _ids(ids, TWO_WINDOWS, kw)
    return physical, published, members, _selector(published, members[6]), _selector(published, members[9])


@pytest.mark.parametrize("producer_owned", [True, False])
@pytest.mark.parametrize("kw", POSES)
def test_adjacent_openings_sharing_wall_support_get_a_partitioned_receipt_in_every_pose(kw, producer_owned):
    physical, published, members, left, right = _two_windows(kw, producer_owned)
    first, second = physical.prove_existence(left).existence_record, physical.prove_existence(right).existence_record
    receipt = physical.partition_receipt(left, right)
    assert receipt.status is CORR and receipt.partition == "partitioned" and receipt.basis == "native_gap_intervals"
    assert receipt.is_physically_distinct and not receipt.grants_quantity and not receipt.grants_firm_authority
    assert {receipt.left_record_id, receipt.right_record_id} == {first.record_id, second.record_id}
    assert set(receipt.shared_source_observation_ids) == set(first.source_observation_ids) & set(second.source_observation_ids)
    assert len(receipt.shared_source_observation_ids) == 2
    assert (receipt.document_id, receipt.revision_id, receipt.source_sha256, receipt.snapshot_id, receipt.page_id) == (
        first.document_id, first.revision_id, first.source_sha256, first.snapshot_id, first.page_id)
    assert (receipt.producer_method, receipt.producer_version, receipt.producer_generation) == (
        first.producer_method, first.producer_version, first.producer_generation)
    assert len(receipt.left_extent) == len(receipt.right_extent) == 2
    assert min(receipt.left_extent[1], receipt.right_extent[1]) <= max(receipt.left_extent[0], receipt.right_extent[0]) + 1e-5
    # the receipt agrees with the identity verdict it is derived with
    assert physical.compare_identity(left, right).physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT


@pytest.mark.parametrize("kw", [{}, {"mirror": True, "offset": (300.0, 0.0)}])
def test_the_receipt_does_not_depend_on_the_order_of_the_two_selectors(kw):
    physical, published, members, left, right = _two_windows(kw)
    forward, backward = physical.partition_receipt(left, right), physical.partition_receipt(right, left)
    assert forward == backward and forward.receipt_id == backward.receipt_id
    assert physical.partition_receipt(left, right) == forward                      # replay


@pytest.mark.parametrize("kw", [{}, {"angle_deg": 90.0, "offset": (350.0, 20.0)}])
def test_layers_of_one_gap_get_a_conflict_receipt_that_is_not_distinct(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    left, right = _selector(published, members[6]), _selector(published, members[8])
    receipt = physical.partition_receipt(left, right)
    assert receipt.status is CONF and receipt.partition == "overlapping_extent" and not receipt.is_physically_distinct
    assert receipt.reason_codes == (PHYSICAL_OPENING_IDENTITY_SHARED_MEMBERS_OVERLAPPING_EXTENT,)
    assert receipt.shared_source_observation_ids


def test_openings_sharing_nothing_are_disjoint_and_one_opening_compared_with_itself_is_the_same_record():
    physical, published, ids, kw = _fixture(PLAIN + OTHER_WALL)
    plain, other = _ids(ids, PLAIN, kw), _ids(ids, OTHER_WALL, kw)
    disjoint = physical.partition_receipt(_selector(published, plain[4]), _selector(published, other[4]))
    assert disjoint.status is CORR and disjoint.partition == "disjoint" and disjoint.is_physically_distinct
    assert disjoint.basis == "no_shared_source_members" and disjoint.shared_source_observation_ids == ()
    same = physical.partition_receipt(_selector(published, plain[4]), _selector(published, plain[5]))
    assert same.status is CORR and same.partition == "same_record" and not same.is_physically_distinct
    assert same.left_record_id == same.right_record_id


def test_a_pair_without_proven_existence_or_in_another_snapshot_gets_no_partition():
    stray = (((300.0, 400.0), (380.0, 400.0)),)                       # a line that belongs to no opening
    physical, published, ids, kw = _fixture(PLAIN + stray)
    _other_physical, other_published, other_ids, other_kw = _fixture(PLAIN)
    members, foreign = _ids(ids, PLAIN, kw), _ids(other_ids, PLAIN, other_kw)
    stray_id = _ids(ids, stray, kw)[0]
    for right in (_selector(other_published, foreign[4]), _selector(published, stray_id)):
        receipt = physical.partition_receipt(_selector(published, members[4]), right)
        assert receipt.status in {ABST, CONF} and receipt.partition == "not_applicable"
        assert not receipt.is_physically_distinct and receipt.left_record_id == receipt.right_record_id == ""
        assert receipt.shared_source_observation_ids == () and receipt.reason_codes


def test_only_the_authority_issues_receipts_and_a_tampered_or_foreign_receipt_does_not_verify():
    physical, published, members, left, right = _two_windows({})
    receipt = physical.partition_receipt(left, right)
    assert physical.verify_partition_receipt(receipt, left, right) and physical.verify_partition_receipt(receipt, right, left)
    names = {f.name for f in fields(PhysicalOpeningPartitionReceipt)}
    kwargs = {n: getattr(receipt, n) for n in names if n != "_seal"}
    with pytest.raises(TypeError):
        PhysicalOpeningPartitionReceipt(**kwargs)                                    # no seal: a caller cannot mint one
    with pytest.raises(TypeError):
        PhysicalOpeningPartitionReceipt(**kwargs, _seal=object())
    forged = replace(receipt, partition="disjoint")
    assert not physical.verify_partition_receipt(forged, left, right)
    assert not physical.verify_partition_receipt(replace(receipt, shared_source_observation_ids=()), left, right)
    assert not physical.verify_partition_receipt("not a receipt", left, right)
    layered, layered_published, layered_ids, layered_kw = _fixture(LAYERED)
    layered_members = _ids(layered_ids, LAYERED, layered_kw)
    assert not layered.verify_partition_receipt(
        receipt, _selector(layered_published, layered_members[6]), _selector(layered_published, layered_members[8]))


def test_asking_for_a_receipt_changes_nothing_else():
    physical, published, members, left, right = _two_windows({})
    before = (physical.prove_existence(left), physical.prove_existence(right), physical.compare_identity(left, right))
    physical.partition_receipt(left, right)
    physical.verify_partition_receipt(physical.partition_receipt(left, right), left, right)
    assert (physical.prove_existence(left), physical.prove_existence(right), physical.compare_identity(left, right)) == before


def test_the_detail_behind_the_verdict_names_the_basis_and_the_extents():
    physical, published, ids, kw = _fixture(TWO_WINDOWS)
    members = _ids(ids, TWO_WINDOWS, kw)
    failure, _s, _r, by_id, _x = physical._seeded_universe(_selector(published, members[6]), members)
    assert failure is None
    first = tuple(sorted({members[0], members[1], members[3], members[4], members[6], members[7]}))
    second = tuple(sorted({members[1], members[2], members[4], members[5], members[8], members[9]}))
    verdict, basis, left_extent, right_extent = _source_member_partition_detail(first, second, by_id)
    assert (verdict, basis) == ("partitioned", "native_gap_intervals")
    assert _source_member_partition(first, second, by_id) == verdict
    assert left_extent[1] <= right_extent[0] + 1e-5 or right_extent[1] <= left_extent[0] + 1e-5
    boxed = _source_member_partition_detail(("a", "b"), ("a", "c"), {}, left_box=(0, 0, 10, 10), right_box=(20, 0, 30, 10))
    assert boxed == ("partitioned", "raster_aperture_box", (0, 0, 10, 10), (20, 0, 30, 10))
    assert _source_member_partition_detail(("a",), ("b",), {})[:2] == ("disjoint", "no_shared_source_members")


def test_a_shared_jamb_is_unproven_not_partitioned():
    physical, published, ids, kw = _fixture(SHARED_JAMB)
    members = _ids(ids, SHARED_JAMB, kw)
    failure, _s, _r, by_id, _x = physical._seeded_universe(_selector(published, members[4]), members)
    assert failure is None
    first = tuple(sorted(members[:6]))
    second = tuple(sorted(members[6:11] + [members[5]]))
    verdict, basis, _l, _r2 = _source_member_partition_detail(first, second, by_id)
    assert verdict == "unproven" and basis == "native_gap_intervals"
