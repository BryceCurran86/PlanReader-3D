"""Only independently source-owned member geometry can scope a raw G17 gap."""
from copy import deepcopy

import pytest

from pb_g17_raw_floor_plan_scope_shadow import (
    _line_scope, _scope_for_group, audit_original_g17_raw_plan_view_scope,
)

PLAN = (10., 10., 100., 100.)


def line(a, b, c, d):
    return (float(a), float(b), float(c), float(d))


def test_every_actual_source_segment_inside_required():
    segments = [line(20, 20, 30, 20), line(22, 25, 32, 25)]
    bbox = (20., 20., 32., 25.)
    before = deepcopy((segments, bbox))
    assert _scope_for_group(segments, bbox, PLAN) == "inside_this_authenticated_floor_plan"
    assert (segments, bbox) == before


def test_all_outside_one_floor_plan_do_not_disprove_opening():
    segments = [line(20, 120, 30, 120), line(25, 123, 35, 123)]
    assert _scope_for_group(segments, (20., 119., 35., 125.), PLAN) == (
        "outside_this_authenticated_floor_plan_other_role_unproven"
    )


def test_crossing_and_mixed_groups_do_not_choose_favourable_port():
    assert _scope_for_group([line(0, 50, 30, 50)], (5., 49., 15., 51.), PLAN) == (
        "crossing_or_competing_view_owner_unproven"
    )
    assert _scope_for_group([line(20, 20, 25, 20), line(150, 20, 160, 20)],
                            (20., 20., 160., 21.), PLAN) == (
        "crossing_or_competing_view_owner_unproven"
    )


def test_raw_bbox_outside_prevents_false_inside_from_member_geometry():
    assert _scope_for_group([line(20, 20, 30, 20)], (110., 30., 120., 32.), PLAN) == (
        "crossing_or_competing_view_owner_unproven"
    )


def test_source_lines_outside_but_gap_inside_cannot_be_called_out_of_plan():
    assert _scope_for_group([line(20, 110, 30, 110)], (20., 20., 30., 25.), PLAN) == (
        "crossing_or_competing_view_owner_unproven"
    )


def test_geometry_at_exact_boundary_retained_as_inside_not_nearest():
    assert _line_scope(line(10, 50, 100, 50), PLAN) == "inside"
    assert _line_scope(line(9.999, 50, 100, 50), PLAN) == "crossing"
    assert _line_scope(line(0, 50, 9, 50), PLAN) == "outside"


@pytest.mark.parametrize("bad", [
    (float("nan"), 0., 1., 2.), (0., float("inf"), 1., 2.),
    (), (0., 1., 2.), ("15", 20., 25., 20.),
])
def test_invalid_original_geometry_abstains(bad):
    assert _scope_for_group([bad], (20., 20., 30., 30.), PLAN) == "source_members_unreadable"


def test_input_order_and_reversal_preserve_disposition():
    s=[line(20, 120, 30, 120), line(25, 123, 35, 123)]
    a=_scope_for_group(s,(20., 119., 35., 125.),PLAN)
    b=_scope_for_group([line(*s[1][2:],*s[1][:2]),line(*s[0][2:],*s[0][:2])],
                       (20.,119.,35.,125.),PLAN)
    assert a==b


def test_foreign_source_object_or_untrusted_page_never_enter_bridge():
    with pytest.raises(TypeError):
        audit_original_g17_raw_plan_view_scope(object(),revision_id="r",page_id="3")
