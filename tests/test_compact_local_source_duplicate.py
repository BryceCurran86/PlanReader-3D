from dataclasses import replace

import numpy as np
import pytest

from pb_raster_compact_wall_band_segments import (
    CompactRasterBandSegment, compact_band_already_covered_by_source_line,
)
from pb_raster_visible_segment_detector import RasterDetectedSegment


def _fixture(vertical=False):
    image = np.full((160, 160), 255, np.uint8)
    image[40:61, 40:81] = 0
    image[50, 81:131] = 0
    candidate = CompactRasterBandSegment(
        (40., 50., 80., 50.), (40., 50., 80., 50.), 'horizontal', (40, 40, 80, 60))
    parent = RasterDetectedSegment(
        (20., 50., 130., 50.), (20., 50., 130., 50.), 'horizontal')
    if vertical:
        image = image.T.copy()
        candidate = CompactRasterBandSegment(
            (50., 40., 50., 80.), (50., 40., 50., 80.), 'vertical', (40, 40, 60, 80))
        parent = RasterDetectedSegment(
            (50., 20., 50., 130.), (50., 20., 50., 130.), 'vertical')
    return image, candidate, parent


@pytest.mark.parametrize('vertical', [False, True])
def test_longer_thin_source_parent_covers_only_local_complete_band(vertical):
    image, candidate, parent = _fixture(vertical)
    before = image.copy()
    assert compact_band_already_covered_by_source_line(candidate, (parent,), image, dpi=72, source_dpi=72)
    assert compact_band_already_covered_by_source_line(candidate, (parent, parent), image, dpi=72, source_dpi=72)
    assert np.array_equal(image, before)


@pytest.mark.parametrize('defect', ['partial', 'remote', 'neighbor', 'hole', 'orientation', 'sloped'])
def test_incomplete_or_unrelated_source_cannot_suppress_nomination(defect):
    image, candidate, parent = _fixture()
    geometry = {
        'partial': (20., 50., 78., 50.),
        'remote': (90., 50., 130., 50.),
        'neighbor': (20., 65., 130., 65.),
        'sloped': (20., 49., 130., 50.),
    }.get(defect, parent.geometry_pt)
    parent = replace(parent, geometry_pt=geometry)
    if defect == 'orientation':
        parent = replace(parent, orientation='vertical')
    if defect == 'hole':
        image[45, 60] = 255
    assert not compact_band_already_covered_by_source_line(candidate, (parent,), image, dpi=72, source_dpi=72)


def test_render_registration_not_physical_scale():
    image, candidate, parent = _fixture()
    parent = replace(parent, geometry_pt=tuple(v / 2 for v in parent.geometry_pt))
    assert compact_band_already_covered_by_source_line(candidate, (parent,), image, dpi=144, source_dpi=144)


def test_original_pixel_footprint_covers_core_without_expanding_source_geometry():
    image, candidate, parent = _fixture()
    # A lower-resolution render samples the same filled core at a different
    # pixel phase. Its original pixel cells cover the inset, even though its
    # nominal centre endpoint does not cover the high-resolution outer edge.
    parent = replace(parent, geometry_pt=(40.5, 50., 130., 50.))
    before = parent
    assert compact_band_already_covered_by_source_line(
        candidate, (parent,), image, dpi=72, source_dpi=36)
    assert parent == before
    # A genuine unobserved part of the core still cannot be disposed.
    parent = replace(parent, geometry_pt=(42.1, 50., 130., 50.))
    assert not compact_band_already_covered_by_source_line(
        candidate, (parent,), image, dpi=72, source_dpi=36)


@pytest.mark.parametrize('dpi, source_dpi', [(0, 72), (72, 0), (-1, 72), (72, -1)])
def test_unknown_registration_cannot_dispose_candidate(dpi, source_dpi):
    image, candidate, parent = _fixture()
    assert not compact_band_already_covered_by_source_line(
        candidate, (parent,), image, dpi=dpi, source_dpi=source_dpi)


def test_split_source_coverage_is_order_independent_but_gap_or_parallel_axis_abstains():
    image, candidate, parent = _fixture()
    left = replace(parent, geometry_pt=(20., 50., 60., 50.))
    right = replace(parent, geometry_pt=(60., 50., 130., 50.))
    for sources in ((left, right), (right, left)):
        assert compact_band_already_covered_by_source_line(candidate, sources, image, dpi=72, source_dpi=72)
    for geometry in ((62., 50., 130., 50.), (60., 51., 130., 51.)):
        assert not compact_band_already_covered_by_source_line(
            candidate, (left, replace(right, geometry_pt=geometry)), image, dpi=72, source_dpi=72)


def test_translation_and_unrelated_source_leave_coverage_unchanged():
    image, candidate, parent = _fixture()
    image = np.pad(image, 20, constant_values=255)
    candidate = replace(candidate,
        pixel_geometry=tuple(v + 20 for v in candidate.pixel_geometry),
        geometry_pt=tuple(v + 20 for v in candidate.geometry_pt),
        pixel_support_bounds=tuple(v + 20 for v in candidate.pixel_support_bounds))
    parent = replace(parent, geometry_pt=tuple(v + 20 for v in parent.geometry_pt))
    unrelated = replace(parent, geometry_pt=(0., 0., 15., 0.))
    assert compact_band_already_covered_by_source_line(candidate, (unrelated, parent), image, dpi=72, source_dpi=72)
