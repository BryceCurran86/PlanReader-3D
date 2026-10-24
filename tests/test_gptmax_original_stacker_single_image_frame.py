"""One original embedded pixel frame spans STACKER flanks and aperture.

Full source evidence depends on the privately SHA-authenticated PDF. Public CI
tests only source-neutral positive and adversarial transform/membership gates.
"""
from hashlib import sha256
from pathlib import Path

import pytest

from tools.diag_gptmax_original_stacker_image_frame import (
    SOURCE_SHA, STACKER_REGIONS,
    source_verified_stacker_image_frame, unique_native_image_frame,
)

ORIGINAL = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")


def _image(*, x0=0.0, x1=300.0, y0=0.0, y1=100.0, xref=17,
           width=300, height=100, rotated=False):
    if rotated:
        trans = (0.0, x1-x0, -(y1-y0), 0.0, x0, y0)
    else:
        trans = (x1-x0, 0.0, 0.0, y1-y0, x0, y0)
    return {
        "xref": xref, "width": width, "height": height,
        "bbox": (x0, y0, x1, y1), "transform": trans,
    }


_REGIONS = {
    "left": (10.0, 40.0, 80.0, 50.0),
    "gap": (80.1, 40.0, 180.0, 50.0),
    "right": (180.1, 40.0, 280.0, 50.0),
    "owned_label": (90.0, 55.0, 120.0, 62.0),
}


def test_one_true_native_image_placement_proves_only_pixel_registration():
    result = unique_native_image_frame((_image(),), _REGIONS)
    assert result is not None
    assert result["source_image_xref"] == 17
    assert result["native_pixel_scales_pt"] == [1.0, 1.0]


@pytest.mark.parametrize("sources", (
    (_image(x0=0., x1=100.), _image(x0=100., x1=300., xref=19)),
    (_image(), _image(xref=19)),
    (_image(rotated=True),),
    (_image(x0=0., x1=250.),),
    (_image(xref=0),),
))
def test_seamed_overlapping_rotated_truncated_or_invalid_image_cannot_grant_frame(sources):
    assert unique_native_image_frame(sources, _REGIONS) is None


@pytest.mark.parametrize("damage", (
    {"owned_label": (300., 55., 310., 62.)},
    {"left": (10., 40., 5., 50.)},
    {"gap": (float("nan"), 40., 180., 50.)},
))
def test_source_mismatched_region_cannot_borrow_pixel_frame(damage):
    changed = {**_REGIONS, **damage}
    assert unique_native_image_frame((_image(),), changed) is None


def test_original_2127_exact_sha_and_native_xref_when_owner_source_available():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: not a passing source replay")
    data = ORIGINAL.read_bytes()
    assert sha256(data).hexdigest() == SOURCE_SHA
    witness = source_verified_stacker_image_frame(data)
    assert witness["single_native_image_frame_proven"] is True
    assert witness["image_frame"]["source_image_xref"] == 97
    assert witness["image_frame"]["native_pixel_dimensions"] == [992, 2631]
    assert witness["physical_wall_host_proven"] is False
    assert witness["opening_count_or_area_publication_granted"] is False
    assert len(witness["source_regions"]) == len(STACKER_REGIONS)
    with pytest.raises(ValueError, match="exact original"):
        source_verified_stacker_image_frame(data + b"source-mutated")
