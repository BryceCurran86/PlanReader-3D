"""Adversarial source sampling checks, no wall/host/count publication."""
import math
from types import SimpleNamespace
import pytest
from pb_raster_compact_partial_source_quarantine import (
    compact_band_has_partial_original_source_coverage as occupied,
)


def fixture(vertical=False):
    compact = SimpleNamespace(pixel_support_bounds=(40.,40.,80.,60.),
                              pixel_geometry=(40.,50.,80.,50.),
                              orientation="horizontal")
    source = SimpleNamespace(geometry_pt=(60*72/300,50*72/300,
                                          100*72/300,50*72/300),
                             orientation="horizontal")
    if vertical:
        compact.pixel_support_bounds=(40.,40.,60.,80.)
        compact.pixel_geometry=(50.,40.,50.,80.)
        compact.orientation="vertical"
        source.geometry_pt=(50*72/300,60*72/300,50*72/300,100*72/300)
        source.orientation="vertical"
    return compact,source


@pytest.mark.parametrize("vertical",[False,True])
def test_partial_ordinary_source_quarantines_competing_compact(vertical):
    compact,source=fixture(vertical)
    assert occupied(compact,(source,),dpi=300,source_dpi=144)
    assert occupied(compact,(source,source),dpi=300,source_dpi=144)


def test_source_and_render_pixel_footprints_not_geometry_tolerance():
    compact,source=fixture()
    shift=.35*300/72
    source.geometry_pt=(source.geometry_pt[0],(50+shift)*72/300,
                        source.geometry_pt[2],(50+shift)*72/300)
    assert occupied(compact,(source,),dpi=300,source_dpi=144)
    source.geometry_pt=(source.geometry_pt[0],(51+shift)*72/300,
                        source.geometry_pt[2],(51+shift)*72/300)
    assert not occupied(compact,(source,),dpi=300,source_dpi=144)


@pytest.mark.parametrize("damage",[
    "remote","endpoint","parallel_other_face","crossing",
    "wrong_orientation","nan","subpixel_contact"])
def test_foreign_or_nonoverlapping_source_cannot_hide_nomination(damage):
    compact,source=fixture()
    if damage=="remote": source.geometry_pt=(90.,12.,100.,12.)
    elif damage=="endpoint": source.geometry_pt=(80*72/300,12.,100*72/300,12.)
    elif damage=="parallel_other_face": source.geometry_pt=(60*72/300,55*72/300,100*72/300,55*72/300)
    elif damage=="crossing": source.geometry_pt=(60*72/300,50*72/300,65*72/300,55*72/300)
    elif damage=="wrong_orientation": source.orientation="vertical"
    elif damage=="nan": source.geometry_pt=(math.nan,0,1,0)
    else: source.geometry_pt=(79.9*72/300,12.,90*72/300,12.)
    assert not occupied(compact,(source,),dpi=300,source_dpi=144)


@pytest.mark.parametrize("dpi,source_dpi",[(0,144),(300,0),(-1,144),(300,-1)])
def test_missing_render_registration_preserves_original_candidate(dpi,source_dpi):
    compact,source=fixture()
    assert not occupied(compact,(source,),dpi=dpi,source_dpi=source_dpi)


def test_input_observations_not_modified():
    compact,source=fixture()
    before=repr((compact,source))
    assert occupied(compact,(source,),dpi=300,source_dpi=144)
    assert repr((compact,source)) == before



from pb_raster_compact_partial_source_quarantine import compact_band_crosses_original_source as crosses


@pytest.mark.parametrize("vertical",[False, True])
def test_perpendicular_original_source_fully_crosses_compact_core(vertical):
    compact, original = fixture(vertical)
    if vertical:
        original.orientation = "horizontal"
        original.geometry_pt = (40*72/300, 60*72/300, 60*72/300, 60*72/300)
    else:
        original.orientation = "vertical"
        original.geometry_pt = (60*72/300, 40*72/300, 60*72/300, 60*72/300)
    assert crosses(compact, (original,), dpi=300, source_dpi=144)


@pytest.mark.parametrize("damage", ["endpoint", "miss", "short", "remote", "wrong_axis", "nonnumeric"])
def test_corner_touch_or_non_crossing_line_never_quarantines(damage):
    compact, original = fixture()
    original.orientation="vertical"
    original.geometry_pt=(60*72/300,40*72/300,60*72/300,60*72/300)
    if damage=="endpoint":
        original.geometry_pt=(40*72/300,40*72/300,40*72/300,60*72/300)
    elif damage=="miss":
        original.geometry_pt=(82*72/300,40*72/300,82*72/300,60*72/300)
    elif damage=="short":
        original.geometry_pt=(60*72/300,44*72/300,60*72/300,52*72/300)
    elif damage=="remote":
        original.geometry_pt=(60*72/300,100*72/300,60*72/300,120*72/300)
    elif damage=="wrong_axis":
        original.orientation="horizontal"
    elif damage=="nonnumeric":
        original.geometry_pt=("bad",0,0,0)
    assert not crosses(compact,(original,),dpi=300,source_dpi=144)


def test_crossing_requires_authenticated_render_registration():
    compact, original = fixture()
    original.orientation="vertical"
    original.geometry_pt=(60*72/300,40*72/300,60*72/300,60*72/300)
    assert not crosses(compact,(original,),dpi=0,source_dpi=144)
    assert not crosses(compact,(original,),dpi=300,source_dpi=0)
    assert not crosses(compact,(),dpi=300,source_dpi=144)


def test_crossing_quarantine_never_modifies_either_source_observation():
    compact, original = fixture()
    original.orientation="vertical"
    original.geometry_pt=(60*72/300,40*72/300,60*72/300,60*72/300)
    before=repr((compact,original))
    assert crosses(compact,(original,),dpi=300,source_dpi=144)
    assert repr((compact,original))==before



from pb_raster_compact_partial_source_quarantine import (
    compact_band_endpoint_on_original_source_interior as endpoint_on_original,
)


@pytest.mark.parametrize("flip",[False,True])
def test_source_proven_ordinary_wall_touched_by_compact_t_endpoint(flip):
    # Source-derived geometry from the archived Lot16 wall/compact audit:
    # ordinary x=381, y=297..349; compact y=342.72 x=381..410.25.
    sc=300/72.
    compact=SimpleNamespace(
        pixel_geometry=(381*sc,342.72*sc,410.25*sc,342.72*sc),
        orientation="horizontal",
    )
    line=(381*72/72,297.,381*72/72,349.)
    source=SimpleNamespace(geometry_pt=line,orientation="vertical")
    if flip:
        compact.pixel_geometry=tuple(reversed(compact.pixel_geometry))
    assert endpoint_on_original(compact,(source,),dpi=300,source_dpi=144)


@pytest.mark.parametrize("damage",[
    "source_near_end","source_corner","outside","other_axis",
    "nonorthogonal","nonfinite","remote","invalid_dpi",
])
def test_t_endpoint_requires_ordinary_original_interior(damage):
    compact=SimpleNamespace(pixel_geometry=(40.,50.,90.,50.),orientation="horizontal")
    source=SimpleNamespace(geometry_pt=(40*72/300,20*72/300,
                                        40*72/300,70*72/300),orientation="vertical")
    dpi=300
    if damage=="source_near_end":
        source.geometry_pt=(40*72/300,49.8*72/300,40*72/300,70*72/300)
    elif damage=="source_corner":
        source.geometry_pt=(40*72/300,50*72/300,40*72/300,70*72/300)
    elif damage=="outside":
        source.geometry_pt=(25*72/300,20*72/300,25*72/300,70*72/300)
    elif damage=="other_axis":
        source.orientation="horizontal"
    elif damage=="nonorthogonal":
        source.geometry_pt=(40*72/300,20*72/300,42*72/300,70*72/300)
    elif damage=="nonfinite":
        source.geometry_pt=(float("nan"),20*72/300,40*72/300,70*72/300)
    elif damage=="remote":
        source.geometry_pt=(40*72/300,100*72/300,40*72/300,170*72/300)
    else:
        dpi=0
    assert not endpoint_on_original(compact,(source,),dpi=dpi,source_dpi=144)


def test_t_endpoint_cannot_alias_parallel_line_or_invent_geometry():
    compact=SimpleNamespace(pixel_geometry=(40.,50.,90.,50.),orientation="horizontal")
    source=SimpleNamespace(geometry_pt=(40*72/300,50*72/300,90*72/300,50*72/300),
                           orientation="horizontal")
    original=repr((compact,source))
    assert not endpoint_on_original(compact,(source,),dpi=300,source_dpi=144)
    assert repr((compact,source))==original
