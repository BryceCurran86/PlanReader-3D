"""Whole-W4 raster opening frames require exact original host identity receipts.

These source-neutral tests use the genuine single-wall host/frame producer
path and cannot publish customer quantities or benchmark scores.
"""
import pytest

from test_raster_opening_whole_wall_frame import (
    GEOMETRY, _binding, _opening, _producer, _record, _scope,
)


@pytest.mark.parametrize("changed_field,untrusted", [
    ("member_candidate_identity_ids", ("candidate:another-wall",)),
    ("member_candidate_identity_ids", ()),
    ("member_equivalence_groups", (("wall:other",),)),
    ("member_equivalence_groups", ()),
    ("member_equivalence_groups", (("wall:host", "wall:other"),)),
])
def test_stale_physical_host_receipt_cannot_issue_raster_frame(changed_field, untrusted):
    binding = _binding()
    setattr(binding, changed_field, untrusted)
    result = _producer(_scope((_record("wall:host"),)))._raster_whole_wall_frame(
        binding=binding, opening=_opening(), geometry=GEOMETRY,
    )
    assert result is None


def test_original_exact_identity_and_same_group_still_issue_whole_frame():
    result = _producer(_scope((_record("wall:host"),)))._raster_whole_wall_frame(
        binding=_binding(), opening=_opening(), geometry=GEOMETRY,
    )
    assert result is not None
    assert result.candidate_ids == ("wall:host",)
    assert result.whole_wall_length == pytest.approx(200.0)
    assert (result.u0, result.u1) == pytest.approx((80.0, 120.0))
