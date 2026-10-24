"""A new G17 pixel namespace is not canonical page-wide W4 authority."""
from __future__ import annotations

import pytest

from pb_physical_wall_candidate_authority import (
    _is_opening_local_supplemental_segment,
    _partition_opening_local_supplemental_segments,
)
from pb_raster_unchanged_band_segments import (
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)


def row(version, index):
    return {"id":f"raster_segment:{'a'*64}:{version}:{'b'*64}:{index}",
            "source_kind":"raster_pdf_visible_segment",
            "source_observation_id":f"original-obs-{index}",
            "geometry":(1.0,2.0,3.0,4.0)}


@pytest.mark.parametrize("version",(
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
))
def test_each_original_opening_local_pixel_source_family_is_supplemental(version):
    assert _is_opening_local_supplemental_segment(row(version,1))


def test_historical_ordinary_producer_membership_unchanged():
    ordinary=[
        {"id":"visible:native_line:source-1"},
        row("raster_visible_segment_v1",2),
        {"id":"raster_segment:unrelated:1.0.0:3"},
    ]
    added=[row(UNCHANGED_BAND_IDENTITY_VERSION,4),
           row(ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,5),
           row(ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,6)]
    before, prior=_partition_opening_local_supplemental_segments(ordinary)
    now, supplemental=_partition_opening_local_supplemental_segments(
        [ordinary[0],added[0],ordinary[1],added[1],ordinary[2],added[2]])
    assert before==ordinary and prior==[]
    assert now==ordinary
    assert supplemental==added


def test_source_inventory_order_independent_without_host_election():
    originals=[row("normal-original-geometry-v1",1),
               row("normal-original-geometry-v1",2)]
    added=[row(ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,3),
           row(ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,4)]
    before,_=_partition_opening_local_supplemental_segments(originals)
    after,new=_partition_opening_local_supplemental_segments(originals+added)
    assert before==after and new==added


@pytest.mark.parametrize("source",(
    "free-text-original_g17_one_end_paint_v1",
    "raster_segment:fake-original_g17_jamb_partial_paint_v1:5",
    "",
))
def test_unstructured_label_similarity_does_not_become_supplemental_wall(source):
    assert not _is_opening_local_supplemental_segment({"id":source})


def test_no_mutation_of_original_source_observations():
    segment=row(ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,4)
    original=dict(segment)
    ordinary, local=_partition_opening_local_supplemental_segments([segment])
    assert ordinary==[] and local==[original]
    assert segment==original


@pytest.mark.parametrize("source", (
    "visible:raster_segment:image:original_g17_one_end_paint_v1:full:0",
    "native:original_g17_jamb_partial_paint_v1:inner:0",
    "raster_segment:image:original_g17_one_end_paint_v1:full:0:EXTRA",
    "raster_segment:image:original_g17_jamb_partial_paint_v1:full:00",
    "raster_segment:image:original_g17_jamb_partial_paint_v1:full:-1",
    "raster_segment:image:original_g17_one_end_paint_v1::0",
    "raster_segment::original_g17_jamb_partial_paint_v1:full:0",
    "raster_segment:image:normal-ink-version:original_g17_one_end_paint_v1:0",
))
def test_source_version_string_not_at_original_issuer_field_never_steals_w4_wall(source):
    assert not _is_opening_local_supplemental_segment({"id":source})


def test_typed_ordinary_wall_injected_with_g17_label_remains_canonical():
    unrelated={"id":"native:structural-wall:original_g17_one_end_paint_v1:0",
               "source_observation_id":"original-native"}
    canonical, supplemental=_partition_opening_local_supplemental_segments([unrelated])
    assert canonical==[unrelated] and not supplemental
