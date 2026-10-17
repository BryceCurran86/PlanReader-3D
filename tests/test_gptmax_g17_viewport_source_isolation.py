"""Real viewport WALL scopes must not ingest opening-local ink family."""
import inspect

from pb_physical_wall_candidate_authority import (
    _partition_opening_local_supplemental_segments,
    _build_authenticated_viewport_scope_results,
)
from pb_raster_unchanged_band_segments import (
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)


def test_opening_local_family_separation_applies_to_every_viewport():
    src=inspect.getsource(_build_authenticated_viewport_scope_results)
    # Regression for a real prior omission: ordinary page W4 was filtered
    # while same page F.07 viewport W4 was fed an unfiltered page input.
    assert "page_segments, _supplemental = _partition_opening_local_supplemental_segments" in src
    assert src.index("page_segments, _supplemental = _partition_opening_local_supplemental_segments") < src.index("for viewport in eligible:")


def test_all_new_families_are_supplemental_not_original_viewport_walls():
    canonical=[{"id":"native:original-segment-1","source_observation_id":"n1"}]
    ink=[
        {"id":f"visible:raster_segment:image:{ver}:full:0",
         "source_observation_id":f"s{i}"}
        for i,ver in enumerate((
            UNCHANGED_BAND_IDENTITY_VERSION,
            ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
            ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
        ))
    ]
    filtered, supplements=_partition_opening_local_supplemental_segments(canonical+ink)
    assert filtered==canonical
    assert supplements==ink
    assert canonical==[{"id":"native:original-segment-1","source_observation_id":"n1"}]
