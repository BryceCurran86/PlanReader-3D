"""Real viewport WALL scopes must not ingest opening-local ink family."""
from pb_physical_wall_candidate_authority import (
    _partition_opening_local_supplemental_segments,
)
from pb_raster_unchanged_band_segments import (
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)


def test_all_new_families_are_supplemental_not_original_viewport_walls():
    canonical=[{"id":"native:original-segment-1","source_observation_id":"n1"}]
    # The wall producer consumes primitive IDs after stripping the `visible:`
    # wrapper from independently verified source-visible receipts.
    ink=[
        {"id":f"raster_segment:{'a'*64}:{ver}:{'b'*64}:0",
         "source_kind":"raster_pdf_visible_segment",
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
