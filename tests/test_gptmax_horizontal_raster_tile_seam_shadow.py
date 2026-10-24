"""Horizontal elevation raster seam cannot masquerade as semantic kind."""
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path

import fitz
from PIL import Image, ImageDraw
import pytest

from pb_gptmax_horizontal_raster_tile_seam_shadow import (
    prove_horizontal_tile_seam_source_pixels,
)
from pb_gptmax_raster_tile_seam_shadow import SOURCE_ONLY, ABSTAIN


def _pdf(*, same=False, gap=0, lower_dark=True, rotation=0):
    doc = fitz.open()
    p = doc.new_page(width=250, height=250)
    imgs = []
    for n in range(2):
        im = Image.new("RGB", (100, 100), "white")
        if n == 0 or lower_dark:
            ImageDraw.Draw(im).rectangle((45, 0, 54, 99), fill="black")
        if n == 1 and not same:
            ImageDraw.Draw(im).point((1, 1), fill="red")
        buf = BytesIO()
        im.save(buf, format="PNG")
        imgs.append(buf.getvalue())
    p.insert_image(fitz.Rect(0, 0, 100, 100), stream=imgs[0])
    p.insert_image(fitz.Rect(0, 100 + gap, 100, 200 + gap),
                   stream=imgs[0] if same else imgs[1])
    p.set_rotation(rotation)
    b = doc.tobytes()
    doc.close()
    return b


def _run(payload, **kw):
    return prove_horizontal_tile_seam_source_pixels(
        payload, expected_sha256=sha256(payload).hexdigest(),
        page_no=1, source_x=50, seam_y=100, flank_offset_pt=4, **kw)


def test_two_source_image_roots_dark_and_unpublished():
    payload = _pdf()
    proof = _run(payload)
    assert proof["status"] == SOURCE_ONLY
    assert len({x["xref"] for x in proof["image_roots"]}) == 2
    assert proof == _run(payload)
    assert not any(proof[k] for k in (
        "structural_host_granted", "whole_wall_frame_granted", "opening_count_granted",
        "quantity_granted", "elevation_plan_identity_granted", "opening_kind_granted"
    ))


@pytest.mark.parametrize("kwargs", [
    {"same": True}, {"gap": 2}, {"lower_dark": False}, {"rotation": 90},
])
def test_false_or_unsupported_seam_abstains(kwargs):
    assert _run(_pdf(**kwargs))["status"] == ABSTAIN


def test_sha_bound_and_explicit_finite_parameters():
    src = _pdf()
    with pytest.raises(ValueError, match="SHA-256"):
        prove_horizontal_tile_seam_source_pixels(
            src, expected_sha256="0"*64,
            page_no=1, source_x=50, seam_y=100)
    for bad in (True, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            prove_horizontal_tile_seam_source_pixels(
                src, expected_sha256=sha256(src).hexdigest(),
                page_no=1, source_x=bad, seam_y=100)


def test_original_elevation_3_four_panel_crosses_two_image_roots():
    source = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    if not source or not Path(source).is_file():
        pytest.skip("owner-private original unavailable: source NOT VERIFIED")
    pdf = Path(source).read_bytes()
    assert sha256(pdf).hexdigest() == (
        "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844")
    report = prove_horizontal_tile_seam_source_pixels(
        pdf, expected_sha256=sha256(pdf).hexdigest(), page_no=5,
        source_x=532.172, seam_y=210.48002, flank_offset_pt=4, dpi=300)
    assert report["status"] == SOURCE_ONLY
    assert [r["xref"] for r in report["image_roots"]] == [116, 115]
    assert not report["opening_kind_granted"]
    assert not report["elevation_plan_identity_granted"]
