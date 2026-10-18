"""Original source-neutral raster tile seam proofs and exact original optional test."""
import hashlib
from io import BytesIO
import os
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

from pb_gptmax_raster_tile_seam_shadow import (
    prove_tile_seam_source_pixels, SOURCE_ONLY, ABSTAIN,
)


def _source(*, gap=0, same=False, right_dark=True, vector_override=False, rotated=False, interior_gap=False):
    doc = fitz.open()
    page = doc.new_page(width=250, height=150)
    images = []
    for side in range(2):
        im = Image.new("RGB", (100, 100), "white")
        draw = ImageDraw.Draw(im)
        if side == 0 or right_dark:
            draw.rectangle((0, 48, 99, 53), fill=(0, 0, 0))
        if side == 1 and interior_gap:
            draw.rectangle((1, 48, 2, 53), fill=(255, 255, 255))
        if side == 1 and not same:
            draw.point((12, 12), fill=(255, 0, 0))
        stream = BytesIO()
        im.save(stream, format="PNG")
        images.append(stream.getvalue())
    page.insert_image(fitz.Rect(0, 0, 100, 100), stream=images[0])
    page.insert_image(fitz.Rect(100 + gap, 0, 200 + gap, 100), stream=images[0] if same else images[1])
    if vector_override:
        page.draw_line(fitz.Point(95, 50), fitz.Point(110, 50), color=(0, 0, 0), width=3)
    if rotated:
        page.set_rotation(90)
    output = doc.tobytes()
    doc.close()
    return output


def _proof(pdf, **kw):
    return prove_tile_seam_source_pixels(
        pdf, expected_sha256=hashlib.sha256(pdf).hexdigest(),
        page_no=1, seam_x=100, source_y=50, flank_offset_pt=4, **kw,
    )


def test_independent_image_roots_and_rendered_source_ink():
    pdf = _source()
    got = _proof(pdf)
    assert got["status"] == SOURCE_ONLY
    assert len(got["image_roots"]) == 2
    assert got["image_roots"][0]["xref"] != got["image_roots"][1]["xref"]
    assert got["image_roots"][0]["image_sha256"] != got["image_roots"][1]["image_sha256"]
    assert all(not got[k] for k in (
        "structural_host_granted", "whole_wall_frame_granted", "opening_count_granted", "quantity_granted"
    ))
    assert got == _proof(pdf)


def test_one_identical_xref_cannot_pretend_to_be_two_source_roots():
    got = _proof(_source(same=True))
    assert got["status"] == ABSTAIN
    assert "distinct_abutting_unmasked_image_roots_unproven" in got["reason_codes"]


def test_gapped_image_roots_do_not_prove_continuity():
    got = _proof(_source(gap=2))
    assert got["status"] == ABSTAIN


def test_vector_paint_over_white_tile_does_not_prove_source_image_ink():
    got = _proof(_source(right_dark=False, vector_override=True))
    assert got["status"] == ABSTAIN
    assert "source_ink_or_render_corroboration_failed" in got["reason_codes"]


def test_rotated_page_is_not_treated_as_unrotated_source_frame():
    got = _proof(_source(rotated=True))
    assert got["status"] == ABSTAIN
    assert "unresolved_source_page_frame" in got["reason_codes"]


def test_pinned_source_and_bounded_explicit_parameters_fail_closed():
    pdf = _source()
    digest = hashlib.sha256(pdf).hexdigest()
    with pytest.raises(ValueError, match="SHA-256"):
        prove_tile_seam_source_pixels(pdf, expected_sha256="0" * 64, page_no=1, seam_x=100, source_y=50)
    for invalid in (float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            prove_tile_seam_source_pixels(pdf, expected_sha256=digest, page_no=1, seam_x=invalid, source_y=50)
    with pytest.raises(ValueError, match="dpi"):
        _proof(pdf, dpi=20)
    with pytest.raises(ValueError, match="page"):
        prove_tile_seam_source_pixels(pdf, expected_sha256=digest, page_no=0, seam_x=100, source_y=50)


def test_original_lot16_page5_seam_requires_owner_source_if_available():
    source = os.environ.get("LOT16_ARCH_ORIGINAL")
    if not source or not Path(source).is_file():
        pytest.skip("private immutable source not provisioned: NOT an original-source verification")
    pdf = Path(source).read_bytes()
    digest = hashlib.sha256(pdf).hexdigest()
    assert digest == "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    report = prove_tile_seam_source_pixels(
        pdf, expected_sha256=digest, page_no=5,
        seam_x=714.36, source_y=514, flank_offset_pt=4,
    )
    assert report["status"] == SOURCE_ONLY
    assert [r["xref"] for r in report["image_roots"]] == [115, 117]
    assert all(not report[k] for k in (
        "structural_host_granted", "whole_wall_frame_granted", "opening_count_granted", "quantity_granted"
    ))


def test_complete_source_scanline_corroborates_all_dark_pixel_columns():
    from pb_gptmax_raster_tile_seam_shadow import prove_contiguous_source_ink_across_tile_seam
    pdf = _source()
    got = prove_contiguous_source_ink_across_tile_seam(
        pdf, expected_sha256=hashlib.sha256(pdf).hexdigest(), page_no=1,
        seam_x=100, source_y=50, flank_offset_pt=7,
    )
    assert got["status"] == "SOURCE_TILE_CROSSING_INK_VERIFIED_SHADOW"
    assert got["source_painted_pixel_columns"] >= 50
    assert all(got["source_pixel_columns_per_image_root"])
    assert all(not got[k] for k in (
        "structural_host_granted", "whole_wall_frame_granted", "opening_count_granted", "quantity_granted"
    ))


def test_inner_white_source_gap_blocks_even_with_two_dark_endpoint_samples():
    from pb_gptmax_raster_tile_seam_shadow import prove_contiguous_source_ink_across_tile_seam
    pdf = _source(interior_gap=True)
    digest = hashlib.sha256(pdf).hexdigest()
    basic = prove_tile_seam_source_pixels(
        pdf, expected_sha256=digest, page_no=1, seam_x=100, source_y=50, flank_offset_pt=7,
    )
    assert basic["status"] == SOURCE_ONLY
    strict = prove_contiguous_source_ink_across_tile_seam(
        pdf, expected_sha256=digest, page_no=1, seam_x=100, source_y=50, flank_offset_pt=7,
    )
    assert strict["status"] == ABSTAIN
    assert "contiguous_source_ink_scan_failed" in strict["reason_codes"]


def test_original_lot16_p3_58_source_image_pixel_columns_cross_tile_seam():
    from pb_gptmax_raster_tile_seam_shadow import prove_contiguous_source_ink_across_tile_seam
    source = os.environ.get("LOT16_ARCH_ORIGINAL")
    if not source or not Path(source).is_file():
        pytest.skip("private original source absent: not an original-source verification")
    pdf = Path(source).read_bytes()
    digest = hashlib.sha256(pdf).hexdigest()
    assert digest == "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    report = prove_contiguous_source_ink_across_tile_seam(
        pdf, expected_sha256=digest, page_no=3, seam_x=714.36,
        source_y=426.5, flank_offset_pt=7,
    )
    assert report["status"] == "SOURCE_TILE_CROSSING_INK_VERIFIED_SHADOW"
    assert [r["xref"] for r in report["image_roots"]] == [95, 97]
    assert report["source_painted_pixel_columns"] == 58
    assert report["source_pixel_columns_per_image_root"] == [29, 29]
    assert not report["structural_host_granted"]


def test_original_lot16_tiles_have_positive_axis_aligned_unmirrored_transforms():
    from pb_gptmax_raster_tile_seam_shadow import _canonical_source_image_placement
    source = os.environ.get("LOT16_ARCH_ORIGINAL")
    if not source or not Path(source).is_file():
        pytest.skip("private SHA-verified original source not provisioned")
    data = Path(source).read_bytes()
    assert hashlib.sha256(data).hexdigest() == "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    with fitz.open(stream=data, filetype="pdf") as document:
        for index, xrefs in ((2, (95, 97)), (4, (115, 117))):
            page = document[index]
            for xref in xrefs:
                placements = page.get_image_rects(xref, transform=True)
                assert len(placements) == 1
                rect, matrix = placements[0]
                assert _canonical_source_image_placement(rect, matrix)
                assert abs(rect.x0 - 714.36) < .02 or abs(rect.x1 - 714.36) < .02


def test_image_rotation_cannot_masquerade_as_native_unrotated_source_root():
    from pb_gptmax_raster_tile_seam_shadow import (
        _canonical_source_image_placement, prove_tile_seam_source_pixels,
    )
    data = _source()
    with fitz.open(stream=data, filetype="pdf") as input_pdf:
        original = input_pdf[0]
        left_xref, right_xref = [int(t[0]) for t in original.get_images(full=True)]
        assert len(original.get_image_rects(left_xref, transform=True)) == 1
        assert len(original.get_image_rects(right_xref, transform=True)) == 1
        left_blob = input_pdf.extract_image(left_xref)["image"]
        right_blob = input_pdf.extract_image(right_xref)["image"]
    out = fitz.open()
    page = out.new_page(width=250, height=150)
    page.insert_image(fitz.Rect(0, 0, 100, 100), stream=left_blob)
    page.insert_image(fitz.Rect(100, 0, 200, 100), stream=right_blob, rotate=90)
    raw = out.tobytes()
    right_placements = page.get_image_rects(page.get_images(full=True)[1][0], transform=True)
    assert any(not _canonical_source_image_placement(rect, matrix)
               for rect, matrix in right_placements)
    out.close()
    report = prove_tile_seam_source_pixels(
        raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
        page_no=1, seam_x=100, source_y=50, flank_offset_pt=4,
    )
    assert report["status"] == ABSTAIN
    assert "source_tile_image_transform_unsupported" in report["reason_codes"]


def test_image_transform_mirror_shear_and_duplicate_boxes_all_fail_closed():
    from pb_gptmax_raster_tile_seam_shadow import _canonical_source_image_placement
    rect = fitz.Rect(0, 0, 100, 100)
    assert _canonical_source_image_placement(rect, fitz.Matrix(100, 0, 0, 100, 0, 0))
    assert not _canonical_source_image_placement(rect, fitz.Matrix(-100, 0, 0, 100, 100, 0))
    assert not _canonical_source_image_placement(rect, fitz.Matrix(100, 0, 0, -100, 0, 100))
    assert not _canonical_source_image_placement(rect, fitz.Matrix(100, 0.02, 0, 100, 0, 0))
    assert not _canonical_source_image_placement(rect, fitz.Matrix(100, 0, 0.02, 100, 0, 0))
    assert not _canonical_source_image_placement(rect, fitz.Matrix(100, 0, 0, 100, 0.1, 0))
