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


def _pdf(*, same=False, gap=0, lower_dark=True, rotation=0, inner_gap=False):
    doc = fitz.open()
    p = doc.new_page(width=250, height=250)
    imgs = []
    for n in range(2):
        im = Image.new("RGB", (100, 100), "white")
        if n == 0 or lower_dark:
            ImageDraw.Draw(im).rectangle((45, 0, 54, 99), fill="black")
        if n == 1 and inner_gap:
            ImageDraw.Draw(im).rectangle((45, 1, 54, 4), fill="white")
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
    failure = _run(_pdf(**kwargs))
    assert failure["status"] == ABSTAIN
    assert failure["opening_kind_granted"] is False
    assert failure["elevation_plan_identity_granted"] is False


@pytest.mark.parametrize("gap", [0.0005, 0.01])
def test_subpixel_horizontal_source_gap_is_not_painted_in_by_raster(gap):
    """Dark endpoint pixels and a dark render cannot close a real source gap."""
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    payload = _pdf(gap=gap)
    digest = sha256(payload).hexdigest()
    common = dict(
        expected_sha256=digest, page_no=1, source_x=50,
        seam_y=100, flank_offset_pt=7, dpi=300,
    )
    for report in (
        prove_horizontal_tile_seam_source_pixels(payload, **common),
        prove_contiguous_source_ink_across_horizontal_tile_seam(payload, **common),
    ):
        assert report["status"] == ABSTAIN
        assert "source_tile_boundary_gap_unproven" in report["reason_codes"]
        assert all(report[key] is False for key in (
            "structural_host_granted", "whole_wall_frame_granted",
            "opening_count_granted", "quantity_granted",
            "elevation_plan_identity_granted", "opening_kind_granted",
        ))


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


def test_contiguous_scanline_uses_every_row_in_two_original_image_roots():
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    payload = _pdf()
    report = prove_contiguous_source_ink_across_horizontal_tile_seam(
        payload, expected_sha256=sha256(payload).hexdigest(),
        page_no=1, source_x=50, seam_y=100, flank_offset_pt=7,
    )
    assert report["status"] == "SOURCE_HORIZONTAL_TILE_CROSSING_INK_VERIFIED_SHADOW"
    assert report["source_painted_pixel_rows"] >= 50
    assert all(report["source_pixel_rows_per_image_root"])
    assert report["opening_kind_granted"] is False


def test_inner_white_stripe_refutes_connected_source_ink_despite_dark_endpoints():
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    payload = _pdf(inner_gap=True)
    kw = dict(expected_sha256=sha256(payload).hexdigest(),
              page_no=1, source_x=50, seam_y=100, flank_offset_pt=7)
    assert prove_horizontal_tile_seam_source_pixels(payload, **kw)["status"] == SOURCE_ONLY
    strong = prove_contiguous_source_ink_across_horizontal_tile_seam(payload, **kw)
    assert strong["status"] == ABSTAIN
    assert "contiguous_source_ink_scan_failed" in strong["reason_codes"]
    assert strong["opening_kind_granted"] is False


def test_original_elevation_panel_rail_is_continuous_across_horizontal_source_tiles():
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    path = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    if not path or not Path(path).is_file():
        pytest.skip("owner-private original unavailable: NOT VERIFIED")
    original = Path(path).read_bytes()
    assert sha256(original).hexdigest() == (
        "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844")
    report = prove_contiguous_source_ink_across_horizontal_tile_seam(
        original, expected_sha256=sha256(original).hexdigest(),
        page_no=5, source_x=532.172, seam_y=210.48002,
        flank_offset_pt=4, dpi=300,
    )
    assert report["status"] == "SOURCE_HORIZONTAL_TILE_CROSSING_INK_VERIFIED_SHADOW"
    assert [r["xref"] for r in report["image_roots"]] == [116, 115]
    assert report["source_painted_pixel_rows"] == 33
    assert report["source_pixel_rows_per_image_root"] == [17, 16]
    assert report["elevation_plan_identity_granted"] is False


@pytest.mark.parametrize("rect,reuse_existing_xref", [
    ((40, 96, 60, 98), False),
    ((40, 99.9999, 60, 100.0001), False),
    ((40, 102, 60, 104), False),
    ((40, 97, 60, 99), True),
])
def test_third_original_image_placement_inside_scan_must_abstain(
    rect, reuse_existing_xref,
):
    """Two dark flank roots do not exclude an extra original interior painter."""
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    document = fitz.open(stream=_pdf(), filetype="pdf")
    page = document[0]
    if reuse_existing_xref:
        # Same image payload/xref at a DISTINCT placement still adds a root.
        xref = int(page.get_images(full=True)[0][0])
        page.insert_image(fitz.Rect(*rect), xref=xref)
    else:
        extra_image = Image.new("RGB", (40, 20), "black")
        content = BytesIO()
        extra_image.save(content, format="PNG")
        page.insert_image(fitz.Rect(*rect), stream=content.getvalue())
    payload = document.tobytes()
    document.close()

    args = dict(expected_sha256=sha256(payload).hexdigest(), page_no=1,
                source_x=50, seam_y=100, flank_offset_pt=7, dpi=300)
    # The added painter deliberately avoids the two original flank samples.
    assert prove_horizontal_tile_seam_source_pixels(payload, **args)["status"] == SOURCE_ONLY
    result = prove_contiguous_source_ink_across_horizontal_tile_seam(
        payload, **args,
    )
    assert result["status"] == ABSTAIN
    assert "source_pixel_row_membership_ambiguous" in result["reason_codes"]
    assert not any(result[key] for key in (
        "structural_host_granted", "whole_wall_frame_granted",
        "opening_count_granted", "quantity_granted",
        "elevation_plan_identity_granted", "opening_kind_granted",
    ))


def test_unrelated_original_image_outside_scanline_is_invariant():
    """An unrelated source image away from the scan must not veto two roots."""
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    document = fitz.open(stream=_pdf(), filetype="pdf")
    content = BytesIO()
    Image.new("RGB", (40, 20), "black").save(content, format="PNG")
    document[0].insert_image(
        fitz.Rect(150, 96, 170, 98), stream=content.getvalue(),
    )
    payload = document.tobytes()
    document.close()
    result = prove_contiguous_source_ink_across_horizontal_tile_seam(
        payload, expected_sha256=sha256(payload).hexdigest(),
        page_no=1, source_x=50, seam_y=100, flank_offset_pt=7, dpi=300,
    )
    assert result["status"] == "SOURCE_HORIZONTAL_TILE_CROSSING_INK_VERIFIED_SHADOW"
    assert result["source_painted_pixel_rows"] >= 50
    assert not result["opening_kind_granted"]


@pytest.mark.parametrize("inline_x,should_abstain", [(40, True), (150, False)])
def test_inline_pdf_raster_painter_cannot_bypass_complete_source_root_census(
    inline_x, should_abstain,
):
    """BI/ID/EI images have xref=0 and are invisible to page.get_images."""
    from pb_gptmax_horizontal_raster_tile_seam_shadow import (
        prove_contiguous_source_ink_across_horizontal_tile_seam,
    )
    document = fitz.open(stream=_pdf(), filetype="pdf")
    page = document[0]
    stream_xref = page.get_contents()[-1]
    # Append a genuine 1x1 black inline raster, 0.2pt high across the seam.
    # PDF stream coordinates are bottom-up; page coordinates are top-down.
    inline = (
        f"\nq\n20 0 0 0.2 {inline_x} 149.9 cm\n"
        "BI /W 1 /H 1 /CS /RGB /BPC 8 ID\n"
    ).encode("ascii") + b"\x00\x00\x00\nEI\nQ\n"
    document.update_stream(
        stream_xref, document.xref_stream(stream_xref) + inline,
    )
    payload = document.tobytes()
    document.close()
    with fitz.open(stream=payload, filetype="pdf") as observed:
        assert any(
            int(info["xref"]) == 0
            for info in observed[0].get_image_info(xrefs=True)
        )
        assert all(int(item[0]) != 0 for item in observed[0].get_images(full=True))
    common = dict(
        expected_sha256=sha256(payload).hexdigest(), page_no=1,
        source_x=50, seam_y=100, flank_offset_pt=7, dpi=300,
    )
    paired = prove_horizontal_tile_seam_source_pixels(payload, **common)
    strict = prove_contiguous_source_ink_across_horizontal_tile_seam(
        payload, **common,
    )
    if should_abstain:
        for result in (paired, strict):
            assert result["status"] == ABSTAIN
            assert "inline_source_image_painter_ambiguous" in result["reason_codes"]
            assert not any(result[key] for key in (
                "structural_host_granted", "whole_wall_frame_granted",
                "opening_count_granted", "quantity_granted",
                "elevation_plan_identity_granted", "opening_kind_granted",
            ))
    else:
        assert paired["status"] == SOURCE_ONLY
        assert strict["status"] == "SOURCE_HORIZONTAL_TILE_CROSSING_INK_VERIFIED_SHADOW"
