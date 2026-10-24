"""Source-ink proof: opaque white masking rectangles are not drawn frames.

This is a DEFAULT-OFF viewport diagnostic; it does not issue F.07, W4,
material, physical ceiling, FIRM quantities or original PDF bytes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_viewport_segmentation import (
    _opaque_white_unstroked_frame_mask_shadow,
    calibrate_viewport_layout,
    extract_vector_frames,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _near(box, coords, tol=0.01):
    return all(abs(float(a) - float(b)) <= tol for a, b in zip(box, coords))


def _synthetic():
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=450)
    page.insert_text((220, 35), "REFLECTED CEILING PLAN", fontsize=12)
    page.draw_rect(fitz.Rect(60, 80, 240, 300), color=None, fill=(1, 1, 1))
    page.draw_rect(fitz.Rect(310, 80, 540, 300), color=(0, 0, 0), fill=None)
    return pdf, page


def test_optin_f07_source_shadow_refuses_unstroked_white_rect_but_retains_real_ink():
    pdf, page = _synthetic()
    try:
        calibration = calibrate_viewport_layout(page)
        baseline = extract_vector_frames(page, calibration)
        shadow = extract_vector_frames(
            page, calibration, exclude_opaque_white_fill_masks_shadow=True,
        )
        assert any(_near(box, (60, 80, 240, 300)) for box in baseline)
        assert not any(_near(box, (60, 80, 240, 300)) for box in shadow)
        assert any(_near(box, (310, 80, 540, 300)) for box in baseline)
        assert any(_near(box, (310, 80, 540, 300)) for box in shadow)
        assert len(shadow) < len(baseline)
        assert extract_vector_frames(page, calibration) == baseline
        with pytest.raises(ValueError, match="explicit_bool"):
            extract_vector_frames(
                page, calibration, exclude_opaque_white_fill_masks_shadow=1,
            )
    finally:
        pdf.close()


def test_exact_native_ink_type_not_area_or_white_color_alone():
    white = {"type": "f", "color": None, "fill": (1., 1., 1.),
             "fill_opacity": 1.0}
    assert _opaque_white_unstroked_frame_mask_shadow(white)
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "type": "fs"})
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "color": (0, 0, 0)})
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "fill_opacity": .8})
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "fill": (.95, 1., 1.)})
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "fill": None})
    assert not _opaque_white_unstroked_frame_mask_shadow({**white, "type": "s"})
    assert not _opaque_white_unstroked_frame_mask_shadow(None)


def test_original_page9_source_mask_141_cannot_be_an_ink_frame():
    if not SOURCE.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE unavailable in public CI; positive not run")
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    with fitz.open(stream=raw, filetype="pdf") as pdf:
        assert len(pdf) == 31
        page = pdf[8]
        assert page.rotation == 90
        drawing = page.get_drawings()[141]
        assert _opaque_white_unstroked_frame_mask_shadow(drawing)
        assert drawing["items"][0][0] == "re"
        bbox = tuple(drawing["items"][0][1])
        assert _near(bbox, (279.84, 471.20, 1217.04, 1376.72))
        calibration = calibrate_viewport_layout(page)
        prior = extract_vector_frames(page, calibration)
        shadow = extract_vector_frames(
            page, calibration, exclude_opaque_white_fill_masks_shadow=True
        )
        assert any(_near(box, bbox) for box in prior)
        assert not any(_near(box, bbox) for box in shadow)
        assert len(shadow) <= len(prior)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
    # No source rectangle, including a genuine stroked one, alone authenticates
    # the entire original p9 RCP ceiling zone or an installed square metre.
