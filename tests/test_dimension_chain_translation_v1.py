"""Dimension chains retain the same witness relationships under rigid motion."""
from types import SimpleNamespace
import copy
import itertools

import pytest

from pb_layered_wall_doorway_room_face_scope_shadow import (
    _same_rail_hash_pairs, unique_hashed_wall_length_mm,
)


def dimension(name, lo, hi, rail, mm, *, orientation="horizontal", shift=0., scale=1.):
    def point(along, across):
        p = (along*scale, across*scale+shift)
        return p if orientation == "horizontal" else (p[1], p[0])
    return SimpleNamespace(
        dimension_id=name, orientation=orientation, value_mm=mm,
        endpoints_pt=(point(lo,rail),point(hi,rail)),
    )


def parts(*, orientation="horizontal", shift=0., scale=1.):
    return [
        dimension("left",100.,160.,50.1,1440.,orientation=orientation,shift=shift,scale=scale),
        dimension("right",160.,250.,50.9,2160.,orientation=orientation,shift=shift,scale=scale),
    ]


def length(rows, *, orientation="horizontal", scale=1.):
    return unique_hashed_wall_length_mm(
        100.*scale,250.*scale,rows,orientation=orientation,
    )


@pytest.mark.parametrize("orientation",["horizontal","vertical"])
@pytest.mark.parametrize("shift",[-1024.3,-100.1,-.1,0.,.1,.4,1.,2.,10.9,1000.45])
def test_chain_value_is_invariant_to_translation_and_axis_swap(orientation,shift):
    assert length(parts(orientation=orientation,shift=shift),orientation=orientation)==3600.


@pytest.mark.parametrize("scale",[.5,1.,2.])
def test_chain_value_is_invariant_to_point_scale(scale):
    assert length(parts(scale=scale),scale=scale)==3600.


def test_order_duplicate_observations_and_unrelated_content_do_not_change_chain():
    rows=parts(shift=.1)
    far=dimension("far",1000.,1100.,50.6,2400.)
    before=copy.deepcopy([vars(x) for x in rows])
    for ordered in itertools.permutations(rows):
        assert length(list(ordered))==3600.
        assert length([far,*ordered,ordered[0]])==3600.
    assert [vars(x) for x in rows]==before


def test_subdividing_a_source_part_preserves_total():
    rows=[
        dimension("left-a",100.,130.,50.2,720.),
        dimension("left-b",130.,160.,50.2,720.),
        dimension("right",160.,250.,51.0,2160.),
    ]
    assert length(rows)==3600.


@pytest.mark.parametrize("bad",["separate_rails","gap","overlap","fork","conflicting_value","transitive_rails"])
def test_missing_or_ambiguous_source_chain_abstains(bad):
    if bad=="separate_rails":
        rows=[dimension("a",100.,160.,50.,1440.),dimension("b",160.,250.,54.,2160.)]
    elif bad=="gap":
        rows=[dimension("a",100.,155.,50.,1320.),dimension("b",160.,250.,50.,2160.)]
    elif bad=="overlap":
        rows=[dimension("a",100.,170.,50.,1680.),dimension("b",160.,250.,50.,2160.)]
    elif bad=="fork":
        rows=parts()+[dimension("fork",100.,170.,50.2,1680.)]
    elif bad=="conflicting_value":
        rows=parts()+[dimension("conflict",100.,160.,50.1,1400.)]
    else:
        rows=[
            dimension("a",100.,150.,50.,1200.),
            dimension("b",150.,200.,51.6,1200.),
            dimension("c",200.,250.,53.2,1200.),
        ]
    assert length(rows) is None


def test_pair_rail_identity_is_invariant_to_translation():
    for shift in (0.,.1,.4,1.,1000.45):
        pairs=_same_rail_hash_pairs(parts(shift=shift),orientation="horizontal",tolerance_pt=.5)
        assert len(pairs)==2
        assert len({row[0] for row in pairs})==1


def test_pair_groups_do_not_join_far_away_figures_on_nearby_rails():
    rows=parts(shift=.1)+[dimension("far",1000.,1100.,50.6,2400.)]
    pairs=_same_rail_hash_pairs(rows,orientation="horizontal",tolerance_pt=.5)
    owned=[row for row in pairs if row[1]<500.]
    foreign=[row for row in pairs if row[1]>500.]
    assert len({row[0] for row in owned})==1
    assert len(foreign)==1 and foreign[0][0]!=owned[0][0]


def test_nested_subrun_overall_is_checked_against_actual_parts():
    rows=[
        dimension("left-a",100.,130.,50.2,720.),
        dimension("left-b",130.,160.,50.2,720.),
        dimension("right",160.,250.,51.,2160.),
        dimension("left-overall",100.,160.,50.6,1440.),
    ]
    assert length(rows)==3600.
    rows[-1]=dimension("wrong-left-overall",100.,160.,50.6,1400.)
    assert length(rows) is None


@pytest.mark.parametrize("turns",[1,2,3])
def test_chain_survives_quarter_turns(turns):
    rows=[]
    for original in parts(shift=.1):
        ends=original.endpoints_pt
        for _ in range(turns):
            ends=tuple((-y,x) for x,y in ends)
        rows.append(SimpleNamespace(**{**vars(original),"endpoints_pt":ends,
            "orientation":"vertical" if turns%2 else "horizontal"}))
    values=[p[1 if turns%2 else 0] for d in rows for p in d.endpoints_pt]
    assert unique_hashed_wall_length_mm(
        min(values),max(values),rows,
        orientation="vertical" if turns%2 else "horizontal",
    )==3600.


def test_whole_geometry_translation_preserves_chain_and_endpoint_direction():
    rows=[]
    for original in reversed(parts()):
        ends=tuple((x+127.3,y-800.2) for x,y in reversed(original.endpoints_pt))
        rows.append(SimpleNamespace(**{**vars(original),"endpoints_pt":ends}))
    assert unique_hashed_wall_length_mm(227.3,377.3,rows,orientation="horizontal")==3600.
