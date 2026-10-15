"""Source-only G17 partial original ink: adversarial native-pixel tests."""
from copy import deepcopy

import numpy as np
import pytest

from pb_g17_raw_endpoint_ink_shadow import audit_original_raw_endpoint_ink


def frames(width=110, height=60):
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    full = image.copy()
    return image, full


def test_complete_original_source_never_fabricates_subinterval():
    image, full = frames()
    image[20, 2:103] = 0
    full[:] = image
    r = audit_original_raw_endpoint_ink(image, full, (2., 20., 102., 20.), dpi=300)
    assert r["original_whole_source_line_solid_unchanged"]
    assert not r["authenticated_contained_original_endpoint_witnesses"]
    assert r["original_source_intervals_not_mutated"]


def test_two_holes_are_never_bridged_or_interior_selected():
    image, full = frames()
    image[20, 2:103] = 0
    image[20, 32] = 255
    image[20, 83] = 255
    full[:] = image
    original = deepcopy(image)
    r = audit_original_raw_endpoint_ink(image, full, (102., 20., 2., 20.), dpi=300)
    assert not r["original_whole_source_line_solid_unchanged"]
    assert r["original_whole_line_negative_preserved"]
    w = r["authenticated_contained_original_endpoint_witnesses"]
    assert len(w) == 2
    assert w[0]["original_axis_endpoint"] == "minimum"
    assert w[0]["contained_original_pixel_bbox_inclusive"] == [2, 20, 31, 20]
    assert w[1]["contained_original_pixel_bbox_inclusive"] == [84, 20, 102, 20]
    assert w[0]["original_endpoint_span_pt"] >= r["unchanged_minimum_line_length_pt"]
    assert all(not x["physical_wall_role_granted"] for x in w)
    assert np.array_equal(image, original)


def test_short_endpoint_remains_unreported():
    image, full = frames()
    image[12, 2:103] = 0
    image[12, 12] = 255
    image[12, 40] = 255
    image[12, 98] = 255
    full[:] = image
    r = audit_original_raw_endpoint_ink(image, full, (2, 12, 102, 12), dpi=300)
    assert not r["original_whole_source_line_solid_unchanged"]
    assert not r["authenticated_contained_original_endpoint_witnesses"]


def test_original_native_overpaint_must_block_even_if_full_render_is_dark():
    image, full = frames()
    image[12, 2:103] = 0
    full[:] = image
    full[12, 45] = (255, 255, 255)
    r = audit_original_raw_endpoint_ink(image, full, (2, 12, 102, 12), dpi=300)
    assert not r["original_whole_source_line_solid_unchanged"]
    assert len(r["authenticated_contained_original_endpoint_witnesses"]) == 2
    assert r["authenticated_contained_original_endpoint_witnesses"][0][
        "contained_original_pixel_bbox_inclusive"] == [2, 12, 44, 12]


def test_original_half_cell_requires_both_native_rows():
    image, full = frames()
    image[17, 2:103] = 0
    full[:] = image
    r = audit_original_raw_endpoint_ink(image, full, (2., 17.5, 102., 17.5), dpi=300)
    assert not r["original_whole_source_line_solid_unchanged"]
    assert not r["authenticated_contained_original_endpoint_witnesses"]


def test_original_vertical_continuation_only_owns_its_original_endpoint():
    image, full = frames(70, 120)
    image[2:103, 16] = 0
    image[67, 16] = 255
    full[:] = image
    a = audit_original_raw_endpoint_ink(image, full, (16., 102., 16., 2.), dpi=300)
    b = audit_original_raw_endpoint_ink(image, full, (16., 2., 16., 102.), dpi=300)
    assert a == b
    w = a["authenticated_contained_original_endpoint_witnesses"]
    assert len(w) == 2
    assert w[0]["contained_original_pixel_bbox_inclusive"] == [16, 2, 16, 66]
    assert w[1]["contained_original_pixel_bbox_inclusive"] == [16, 68, 16, 102]


@pytest.mark.parametrize("pixels", [
    (1, 1, 1, 1), (2, 2, 5, 5), (float("nan"), 5, 3, 5),
    (float("inf"), 0, 2, 0), (1000, 3, 1100, 3), (1, 2, 3),
    ("2", 3, 4, 3),
])
def test_source_invalid_or_nonaxis_line_fails_closed(pixels):
    a, b = frames()
    with pytest.raises(ValueError):
        audit_original_raw_endpoint_ink(a, b, pixels, dpi=300)


def test_different_frames_or_types_or_dpi_fail_closed():
    a, b = frames()
    with pytest.raises(ValueError):
        audit_original_raw_endpoint_ink(a, b[:-1], (2, 3, 5, 3), dpi=300)
    with pytest.raises(ValueError):
        audit_original_raw_endpoint_ink(a.astype(float), b, (2, 3, 5, 3), dpi=300)
    with pytest.raises(ValueError):
        audit_original_raw_endpoint_ink(a, b, (2, 3, 5, 3), dpi=0)
