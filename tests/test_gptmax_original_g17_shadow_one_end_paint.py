"""Source-authenticated original G17 one-jamb terminal ink can only be shadow."""
from copy import deepcopy

import numpy as np
import pytest

from tools.diag_gptmax_g17_original_inclusive_source_shadow import (
    authenticated_one_end_g17_paint_shadow as classify,
)


def source(flank_pixels=17):
    first=20
    last=first+flank_pixels-1
    source_rgb=np.full((110,110,3),255,dtype=np.uint8)
    source_rgb[50:60,first:last+1,:]=0
    flank={
        "orientation":"horizontal",
        "source_bbox_pdf_pts":[first*72/300,50*72/300,
                               last*72/300,59*72/300],
        "source_observation_ids":["physical-face-a","physical-face-b","source-jamb-end"],
    }
    return source_rgb,flank


@pytest.mark.parametrize("columns,expected", [(16,False),(17,True),(18,True),(30,True)])
def test_one_ended_source_ink_respects_original_inclusive_four_point_policy(
    columns,expected,
):
    source_rgb,flank=source(columns)
    prior=deepcopy(flank)
    result=classify(source_rgb,source_rgb.copy(),flank,dpi=300,
                    image_regions=((4.0,11.0,18.0,20.0),))
    assert result["source_one_end_shadow_eligible"] is expected
    assert result["inclusive_original_painted_cells"]==columns
    assert result["complete_outer_end_cap_assumed"] is False
    assert result["structural_W2_or_W4_proven"] is False
    assert result["host_or_frame_granted"] is False
    assert result["metric_area_granted"] is False
    assert result["opening_height_or_count_granted"] is False
    assert flank==prior


def test_non_solid_original_image_is_rejected_even_when_rgb_equals_full():
    image,flank=source()
    image[55,24:34,:]=255
    result=classify(image,image.copy(),flank,dpi=300,
                    image_regions=((4,11,18,20),))
    assert result["source_one_end_shadow_eligible"] is False
    assert result["source_original_rgb_solid"] is False
    assert result["source_shadow_first_failure"]=="original_source_ink_not_solid"


def test_native_paint_overlay_difference_abstains_even_with_solid_base():
    image,flank=source()
    full=image.copy()
    full[55,22:35,1]=10
    result=classify(image,full,flank,dpi=300,
                    image_regions=((4,11,18,20),))
    assert result["source_one_end_shadow_eligible"] is False
    assert result["source_vs_full_rgb_identical"] is False
    assert result["source_shadow_first_failure"]=="original_source_overpaint_conflict"


def test_missing_exact_original_image_region_source_owner_abstains():
    image,flank=source()
    result=classify(image,image,flank,dpi=300,image_regions=())
    assert result["source_one_end_shadow_eligible"] is False
    assert result["original_image_region_owned"] is False
    assert result["source_shadow_first_failure"]=="original_source_image_region_unowned"


@pytest.mark.parametrize("damage", [
    "duplicate_source", "missing_jamb", "non_pixel_grid", "invalid_axis",
    "invalid_dpi", "nonfinite",
])
def test_forged_or_incomplete_g17_source_receipts_fail_closed(damage):
    image,flank=source()
    dpi=300
    if damage=="duplicate_source":
        flank["source_observation_ids"][1]=flank["source_observation_ids"][0]
    elif damage=="missing_jamb":
        flank["source_observation_ids"]=flank["source_observation_ids"][:2]
    elif damage=="non_pixel_grid":
        flank["source_bbox_pdf_pts"][0]+=0.1
    elif damage=="invalid_axis":
        flank["orientation"]="diagonal"
    elif damage=="invalid_dpi":
        dpi=0
    else:
        flank["source_bbox_pdf_pts"][2]=float("nan")
    with pytest.raises(ValueError):
        classify(image,image,flank,dpi=dpi,
                 image_regions=((4,11,18,20),))
