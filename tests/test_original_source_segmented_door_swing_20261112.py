"""Original-app segmented black line swing detection + safe doorway closures."""
from __future__ import annotations
from pathlib import Path
import functools
import os
import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import (
    _Gap, _place_swings, _source_wall_ink_candidate_drawings,
    build_layered_wall_doorway_room_rings,
)
from pb_source_segmented_door_swing_shadow import (
    _arc_quarter_candidate, collect_source_black_segmented_door_swings,
    propose_source_owned_doorway_chords,
)

SHA="ab"*32


def _swing():
    return {
        "arc": 101,
        "arc_source_ids":tuple(range(101,110)),
        "leaf":100,
        "centre":(10.0,20.0),
        "closed_tip":(62.0,20.0),
        "radius":52.0,
        "source_segmented_polyline":True,
    }


def test_source_swing_closes_only_exact_wall_end_gap():
    arc=_swing()
    matching=_Gap(True,(17.0,23.0),10.0,62.0,(7,8),(9,10),True)
    placed,unplaced,ambiguous=_place_swings([arc],[matching])
    assert set(placed)=={0}
    assert placed[0] is arc
    assert not unplaced and not ambiguous


@pytest.mark.parametrize("wrong", [
    _Gap(True,(17.0,23.0),10.0,1000.0,(7,),(9,),True),
    _Gap(True,(17.0,23.0),0.0,62.0,(7,),(9,),True),
    _Gap(True,(17.0,23.0),10.0,61.5,(7,),(9,),True),
    _Gap(True,(50.0,55.0),10.0,62.0,(7,),(9,),True),
    _Gap(False,(7.0,13.0),10.0,62.0,(7,),(9,),True),
])
def test_source_swing_does_not_close_nonmatching_or_long_gap(wrong):
    placed,unplaced,ambiguous=_place_swings([_swing()],[wrong])
    assert placed=={}
    assert unplaced==1
    assert ambiguous==0


def test_source_swing_refuses_ambiguous_identical_gap_owners():
    arc=_swing()
    match=_Gap(True,(17.0,23.0),10.0,62.0,(7,8),(9,10),True)
    placed,unplaced,ambiguous=_place_swings([arc],[match,match])
    assert placed=={}
    assert unplaced==0 and ambiguous==1


def test_real_maryborough_d13_has_original_connected_arc_and_distinct_open_closed_tips():
    original=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("private Maryborough original not provisioned")
    with fitz.open(original) as doc:
        filtered,eligible,green=_source_wall_ink_candidate_drawings(doc[6].get_drawings())
    assert eligible==14038 and green==64333
    witnesses=collect_source_black_segmented_door_swings(filtered)
    assert len(witnesses)==12
    d13=next(
        w for w in witnesses if w["arc_native_path_indices"]==tuple(range(69484,69493))
    )
    assert d13["leaf_native_path_index"]==69480
    assert d13["source_hinge_point_pdf_pts"]==pytest.approx((441.12,1383.2),abs=.002)
    assert d13["source_open_leaf_tip_pdf_pts"]==pytest.approx((441.12,1435.28),abs=.002)
    assert d13["source_closed_leaf_tip_pdf_pts"]==pytest.approx((389.04,1383.2),abs=.002)
    assert not d13["topology_doorway_closure_authorized"]
    assert not d13["commercial_publishable"]
    assert len(d13["native_source_path_indices"])==10


@functools.lru_cache(maxsize=1)
def _real_a110_ring():
    original=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("private Maryborough original not provisioned")
    with fitz.open(original) as doc:
        drawings=doc[6].get_drawings()
    return build_layered_wall_doorway_room_rings(
        drawings,source_sha256=SHA,page_index=6,dark_painted_wall_source=True,
    )


def test_real_maryborough_a110_original_rings_retains_segmented_source_witnesses_but_never_invents_wall():
    real=_real_a110_ring()
    assert len(real.source_segmented_swing_witnesses)==12
    # Chord and closure counts are NOT pinned here: they moved with 4285e133a
    # (merged face strips), not with the 20,000-primitive structural count.
    assert all(not c["commercial_publishable"]
               for c in real.source_owned_doorway_chords)
    assert all(not ring.commercial_projection_allowed for ring in real.rings)
    assert all(not ring.metric_area_issued for ring in real.rings)


@pytest.mark.xfail(
    strict=True,
    reason="A110 had 2 source-owned doorway chords at e93dbfe2e and has 0 since 4285e133a "
           "(first bad commit with the cap check bypassed); follow-up of the A110 cap note, "
           "not of the structural-primitive cap. Remove this marker when the chords return.",
)
def test_real_maryborough_a110_original_rings_regain_the_two_source_owned_doorway_chords():
    real=_real_a110_ring()
    assert len(real.source_owned_doorway_chords)==2


def _any_size_source_door(width,*,vertical=False,threshold=False,missing_right=False):
    """CAD black strokes at a door's genuine sides, no hardcoded project coordinates."""
    lo=21.0;hi=lo+width;perp=78.0
    def point(along,across):
        return (across,along) if vertical else (along,across)
    def stroke(start,end):
        a=point(*start);b=point(*end)
        return {"fill":None,"color":(0.0,0.0,0.0),
                "items":[("l",fitz.Point(*a),fitz.Point(*b))]}
    native=[
        stroke((lo-4,perp),(lo,perp)),
        stroke((hi,perp),(hi+4,perp)),
        stroke((lo,perp-3),(lo,perp)),
        stroke((hi,perp-3),(hi,perp)),
    ]
    if missing_right:
        native.pop(1)
    if threshold:
        native.append(stroke((lo,perp),(hi,perp)))
    hinge=point(hi,perp);tip=point(lo,perp)
    witness={
        "native_source_path_indices":(100,101,102),
        "source_hinge_point_pdf_pts":hinge,
        "source_closed_leaf_tip_pdf_pts":tip,
    }
    parent=_Gap(not vertical,(perp-4,perp+1),lo,hi+width*4,
                (90,),(91,),False)
    return native,witness,parent


@pytest.mark.parametrize("width", [23.0,52.08,90.0,138.0])
@pytest.mark.parametrize("vertical", [False,True])
@pytest.mark.parametrize("threshold", [False,True])
def test_common_door_wall_rule_handles_any_width_orientation_or_threshold(width,vertical,threshold):
    drawings,witness,parent=_any_size_source_door(
        width,vertical=vertical,threshold=threshold,
    )
    chords=propose_source_owned_doorway_chords(drawings,[witness],[parent])
    assert len(chords)==1
    chord=chords[0]
    assert chord["horizontal"] is not vertical
    assert chord["door_interval_pdf_pts"]==pytest.approx((21,21+width))
    assert len(chord["source_wall_end_left_path_indices"])==1
    assert len(chord["source_wall_end_right_path_indices"])==1
    assert bool(chord["source_threshold_path_indices"]) is threshold
    assert chord["commercial_publishable"] is False


def test_common_door_wall_rule_rejects_missing_wall_side_even_with_real_swing():
    drawings,witness,parent=_any_size_source_door(52.08,missing_right=True)
    assert propose_source_owned_doorway_chords(drawings,[witness],[parent])==()


def test_common_door_wall_rule_rejects_missing_parent_or_two_competing_bands():
    drawings,witness,parent=_any_size_source_door(67.0)
    assert propose_source_owned_doorway_chords(drawings,[witness],[])==()
    assert propose_source_owned_doorway_chords(drawings,[witness],[parent,parent])==()


def test_original_legacy_door_mode_default_off_and_no_extra_witnesses():
    # A clean dark-ink room has no source door and no reference mutation.
    def bar(rect):
        return {"fill":(.195,.195,.195),"color":None,"items":[("re",fitz.Rect(*rect),1)]}
    rows=[bar(x) for x in ((0,0,100,4),(0,4,4,96),(96,4,100,96),(0,96,100,100))]
    a=build_layered_wall_doorway_room_rings(rows,source_sha256=SHA,page_index=0)
    assert not a.source_segmented_swing_witnesses
    b=build_layered_wall_doorway_room_rings(rows,source_sha256=SHA,page_index=0,dark_painted_wall_source=True)
    assert not b.source_segmented_swing_witnesses
    assert a!=b


@functools.lru_cache(maxsize=None)
def _paired_ring(page_index):
    original=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("private Maryborough original not provisioned")
    with fitz.open(original) as doc:
        drawings=doc[page_index].get_drawings()
    return build_layered_wall_doorway_room_rings(
        drawings,source_sha256=SHA,page_index=page_index,dark_painted_wall_source=True,door_jamb_returns=True,
    )


@pytest.mark.parametrize("page_index,expected",[(6,6),(23,0),(24,0),(25,1),(26,1)])
def test_real_maryborough_paired_door_switch_recovers_source_owned_doorway_chords(page_index,expected):
    # door_jamb_returns keeps each swing's own strokes out of the wall strips and adds its jamb returns. The two A110 chords lost at
    # 4285e133a come back (with four more). On the p23 inset the door is closed by its swing directly, so no raw gap is left for a
    # chord. Counts only; topology only. Without the switch the default path above is unchanged (still xfail).
    real=_paired_ring(page_index)
    assert len(real.source_owned_doorway_chords)==expected
    assert all(not c["commercial_publishable"] and not c["metric_area_issued"] for c in real.source_owned_doorway_chords)
