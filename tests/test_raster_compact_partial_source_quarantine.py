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
