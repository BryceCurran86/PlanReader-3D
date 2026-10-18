"""Opening-local raster fragments cannot become ordinary F.07 W2/W3/W4 wall segments."""
from __future__ import annotations

import inspect

from pb_physical_wall_candidate_authority import (
    _build_authenticated_viewport_scope_results,
    _partition_opening_local_supplemental_segments,
)
from pb_raster_unchanged_band_segments import UNCHANGED_BAND_IDENTITY_VERSION


def test_source_partition_excludes_only_exact_registered_supplemental_issuer_version():
    old_wall = {"id": "native:wall-1", "source_observation_id": "n1"}
    old_raster = {"id": "raster_segment:page:plain_v1:full:3", "source_observation_id": "r1"}
    supplemental = {
        "id": f"visible:raster_segment:image:{UNCHANGED_BAND_IDENTITY_VERSION}:full:0",
        "source_observation_id": "s1",
    }
    source = [old_wall, supplemental, old_raster]
    old, shadow = _partition_opening_local_supplemental_segments(source)
    assert old == [old_wall, old_raster]
    assert shadow == [supplemental]
    assert source == [old_wall, supplemental, old_raster]  # pure and deterministic
    assert _partition_opening_local_supplemental_segments(list(reversed(source))) == (
        list(reversed(old)), shadow,
    )


def test_viewport_reads_only_the_same_canonical_source_members_as_page_w4():
    source = inspect.getsource(_build_authenticated_viewport_scope_results)
    partition = "_partition_opening_local_supplemental_segments("
    assert source.count(partition) == 1
    assert source.index(partition) > source.index("_source_page_segments(")
    assert source.index(partition) < source.index("if physical_plan_view_shadow:")
    assert source.index(partition) < source.index("for viewport in eligible:")
    assert "page_segments, _opening_local_supplemental = " in source


def test_supplemental_scope_is_kept_separate_from_viewport_physical_wall_scope():
    from pb_physical_wall_candidate_authority import (
        PhysicalWallCandidateProducer,
    )
    ordinary = inspect.getsource(PhysicalWallCandidateProducer.from_source_visibility_producer)
    supplemental = inspect.getsource(
        PhysicalWallCandidateProducer.from_opening_local_supplemental_source_visibility_producer
    )
    assert "supplemental_only=False" in ordinary
    assert "supplemental_only=True" in supplemental
    assert "include_authenticated_viewports=False" in supplemental
