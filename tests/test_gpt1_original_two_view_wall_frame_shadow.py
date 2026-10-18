"""Full source wall ring identity consistency, not wall-fit ranking."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_original_two_view_wall_frame_shadow import (
    OriginalCrossSheetWallPair,verify_source_wall_pair_rigid_frame_shadow,
)


def _pairs():
    p=((0,0),(10,0),(10,5),(0,5))
    # Source plan differs by exact (-78, 0) translation from finish sheet.
    return tuple(OriginalCrossSheetWallPair(
        f"physical-wall-{i}",
        (f"room-ink-{i}",),(f"finish-ink-{i}",),
        p[i],p[(i+1)%4],
        (p[i][0]+78,p[i][1]),(p[(i+1)%4][0]+78,p[(i+1)%4][1]),
        f"original-wall-equivalence-{i}",
    ) for i in range(4))


def test_each_original_room_wall_proves_one_exact_crossview_frame():
    result=verify_source_wall_pair_rigid_frame_shadow(_pairs())
    assert result.status is Status.CANDIDATE
    c,s,tx,ty=result.original_finish_to_room_rigid_transform
    assert abs(c-1)<1e-12
    assert abs(s)<1e-12
    assert abs(tx+78)<1e-12
    assert abs(ty)<1e-12
    assert result.maximum_native_source_endpoint_disagreement_pt==0
    assert result.diagnostic_only


def test_physically_periodic_rival_must_fail_complete_wall_endpoint_agreement():
    pieces=list(_pairs())
    shifted=pieces[-1]
    pieces[-1]=replace(shifted,finish_page_start=(shifted.finish_page_start[0]+34.08,
                                                   shifted.finish_page_start[1]))
    out=verify_source_wall_pair_rigid_frame_shadow(tuple(pieces))
    assert out.status is Status.ABSTAINED


def test_missing_wall_or_recycled_original_receipt_does_not_make_a_room():
    for candidate in (
        _pairs()[:-1],
        _pairs()[:1]+(replace(_pairs()[1],wall_equivalence_receipt_id="original-wall-equivalence-0"),)
        +_pairs()[2:],
    ):
        out=verify_source_wall_pair_rigid_frame_shadow(candidate)
        assert out.status is Status.ABSTAINED


def test_fit_cannot_be_achieved_by_scaling_whole_plan_or_redrawing_walls():
    pieces=tuple(replace(p,finish_page_start=(2*p.finish_page_start[0],
                                              2*p.finish_page_start[1]),
                         finish_page_end=(2*p.finish_page_end[0],
                                          2*p.finish_page_end[1]))
                 for p in _pairs())
    out=verify_source_wall_pair_rigid_frame_shadow(pieces)
    assert out.status is Status.ABSTAINED


def test_two_sheets_must_both_be_same_closed_physical_structural_ring():
    pieces=list(_pairs())
    pieces[2]=replace(pieces[2],room_page_end=(0,6))
    assert verify_source_wall_pair_rigid_frame_shadow(tuple(pieces)).status is Status.ABSTAINED
