"""Opening-local raster fragments cannot become ordinary F.07 W2/W3/W4 wall segments."""
from __future__ import annotations

import inspect

import pytest

from pb_physical_wall_candidate_authority import (
    _build_authenticated_viewport_scope_results,
    _partition_opening_local_supplemental_segments,
    _is_opening_local_supplemental_segment,
    PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE,
    RASTER_PDF_VISIBLE_SEGMENT,
)
from pb_raster_unchanged_band_segments import UNCHANGED_BAND_IDENTITY_VERSION


def test_source_partition_excludes_only_exact_registered_supplemental_issuer_version():
    old_wall = {"id": "native:wall-1", "source_observation_id": "n1"}
    old_raster = {"id": "raster_segment:" + "c" * 64 + ":1.0.0:3",
                  "source_kind": RASTER_PDF_VISIBLE_SEGMENT, "source_observation_id": "r1"}
    supplemental = {
        "id": f"raster_segment:{'a' * 64}:{UNCHANGED_BAND_IDENTITY_VERSION}:{'b' * 64}:0",
        "source_kind": RASTER_PDF_VISIBLE_SEGMENT,
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


def test_substring_in_native_or_foreign_source_cannot_strip_canonical_wall():
    claim = f"raster_segment:{'a' * 64}:{UNCHANGED_BAND_IDENTITY_VERSION}:{'b' * 64}:0"
    native = {"id": claim, "source_kind": "native_pdf_visible_segment", "source_observation_id": "n1"}
    unknown = {"id": claim, "source_observation_id": "u1"}
    nearby = {"id": "native:wall:unchanged_terminal_band_v1:line", "source_observation_id": "n2"}
    ordinary, supplemental = _partition_opening_local_supplemental_segments([native, unknown, nearby])
    assert ordinary == [native, unknown, nearby]
    assert supplemental == []


@pytest.mark.parametrize("identifier", [
    "visible:raster_segment:" + "a" * 64 + ":" + UNCHANGED_BAND_IDENTITY_VERSION + ":" + "b" * 64 + ":0",
    "raster_segment:short:" + UNCHANGED_BAND_IDENTITY_VERSION + ":" + "b" * 64 + ":0",
    "raster_segment:" + "A" * 64 + ":" + UNCHANGED_BAND_IDENTITY_VERSION + ":" + "b" * 64 + ":0",
    "raster_segment:" + "a" * 64 + ":" + UNCHANGED_BAND_IDENTITY_VERSION + ":short:0",
    "raster_segment:" + "a" * 64 + ":" + UNCHANGED_BAND_IDENTITY_VERSION + ":" + "b" * 64 + ":00",
    "raster_segment:" + "a" * 64 + ":" + UNCHANGED_BAND_IDENTITY_VERSION + ":" + "b" * 64 + ":",
])
def test_fake_raster_issuer_is_hard_source_integrity_failure(identifier):
    malformed = {"id": identifier, "source_kind": RASTER_PDF_VISIBLE_SEGMENT,
                 "source_observation_id": "fake"}
    with pytest.raises(RuntimeError, match=PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE):
        _is_opening_local_supplemental_segment(malformed)


def test_valid_native_raster_issuer_preserves_exact_source_identity_without_mutation():
    src = {"id": f"raster_segment:{'0' * 64}:{UNCHANGED_BAND_IDENTITY_VERSION}:{'f' * 64}:19",
           "source_kind": RASTER_PDF_VISIBLE_SEGMENT, "source_observation_id": "issued"}
    old = src.copy()
    assert _is_opening_local_supplemental_segment(src)
    assert src == old
