"""Read-only exact 144/300 DPI G17 source filter stage classification."""
import pytest

from pb_raster_unchanged_band_segments import UnchangedRasterBandSegment
from pb_raster_visible_segment_detector import RasterDetectedSegment
from tools.diag_gptmax_g17_detector_first_gate import (
    classify_original_terminal_flank_pixel_gate as classify,
)


def flank():
    return {
        "orientation": "horizontal",
        "source_bbox_pdf_pts": [60.0, 29.0, 64.08, 31.0],
        "source_observation_ids": ["original-left-face", "original-right-face", "original-end"],
    }


def painted():
    # Seventeen original supported 300-DPI cells, not sixteen endpoints.
    return UnchangedRasterBandSegment(
        (250.0, 125.0, 267.0, 125.0),
        (60.0, 30.0, 64.08, 30.0),
        "horizontal",
        (250, 123, 267, 127),
    )


def test_exact_source_present_and_region_owned_yields_shadow_candidate_only():
    result = classify(
        source_flank=flank(),
        original_300dpi_segments=(painted(),),
        original_144dpi_segments=(),
        original_image_regions=((59.0, 27.0, 66.0, 33.0),),
    )
    assert result["original_300dpi_terminal_candidates"] == 1
    assert result["source_image_region_owned_candidates"] == 1
    assert result["not_ordinary_deduplicated_candidates"] == 1
    assert result["first_detector_gate"] == "pixel_and_image_source_nomination_eligible"
    assert result["physical_host_granted"] is False
    assert result["metric_quantity_granted"] is False


def test_missing_real_terminal_candidate_fails_at_first_gate():
    result = classify(
        source_flank=flank(),
        original_300dpi_segments=(),
        original_144dpi_segments=(),
        original_image_regions=((59.0, 27.0, 66.0, 33.0),),
    )
    assert result["first_detector_gate"] == "original_300dpi_terminal_candidate_unavailable"


def test_missing_real_image_tile_source_ownership_fails_closed():
    result = classify(
        source_flank=flank(),
        original_300dpi_segments=(painted(),),
        original_144dpi_segments=(),
        original_image_regions=(),
    )
    assert result["first_detector_gate"] == "source_image_region_ownership_unavailable"
    assert result["original_300dpi_terminal_candidates"] == 1
    assert result["source_image_region_owned_candidates"] == 0


def test_existing_ordinary_raster_veto_reported_not_waived():
    ordinary = RasterDetectedSegment(
        (118.0, 60.0, 132.0, 60.0),
        (59.0, 30.0, 66.0, 30.0),
        "horizontal",
    )
    result = classify(
        source_flank=flank(),
        original_300dpi_segments=(painted(),),
        original_144dpi_segments=(ordinary,),
        original_image_regions=((59.0, 27.0, 66.0, 33.0),),
    )
    assert result["first_detector_gate"] == (
        "suppressed_by_original_144dpi_ordinary_raster_candidate"
    )
    assert result["not_ordinary_deduplicated_candidates"] == 0
    assert result["physical_host_granted"] is False


def test_unrelated_ordinary_raster_cannot_veto_original_flank():
    ordinary = RasterDetectedSegment(
        (120.0, 100.0, 132.0, 100.0),
        (60.0, 50.0, 66.0, 50.0),
        "horizontal",
    )
    result = classify(
        source_flank=flank(),
        original_300dpi_segments=(painted(),),
        original_144dpi_segments=(ordinary,),
        original_image_regions=((59.0, 27.0, 66.0, 33.0),),
    )
    assert result["first_detector_gate"] == "pixel_and_image_source_nomination_eligible"


@pytest.mark.parametrize("bad", [
    {"orientation": "diagonal", "source_bbox_pdf_pts": [60.0, 29.0, 64.08, 31.0]},
    {"orientation": "horizontal", "source_bbox_pdf_pts": [60.0, 29.0]},
])
def test_invalid_source_geometry_never_supplies_nomination(bad):
    with pytest.raises(ValueError):
        classify(
            source_flank=bad,
            original_300dpi_segments=(painted(),),
            original_144dpi_segments=(),
            original_image_regions=((59.0, 27.0, 66.0, 33.0),),
        )
