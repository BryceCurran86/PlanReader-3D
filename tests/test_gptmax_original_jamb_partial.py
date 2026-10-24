"""Original G17 source cap: never bridge an unpainted band to host."""
from hashlib import sha256
from pathlib import Path
import cv2
import fitz
import numpy as np
import pytest

from pb_raster_unchanged_band_segments import (
    detect_original_jamb_anchored_ink_segments,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT

SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")


def _png(im):
    ok, value=cv2.imencode(".png", im)
    assert ok
    return value.tobytes()


def _image_and_flank(*,paint_at_end=20,noise_before=True,alter=False):
    a=np.full((84,66,3),255,dtype=np.uint8)
    a[16:16+paint_at_end,20:30]=0
    if noise_before:
        a[48:72,20:30]=0
    full=a.copy()
    if alter:
        full[16+paint_at_end-2,25]=255
    return _png(a),_png(full)


def test_jamb_cap_must_touch_original_source_not_remote_paint():
    a,b=_image_and_flank(paint_at_end=20)
    # Cap at LOWER endpoint y=16, next 20 pixels painted. The remote
    # component at y48:71 must not be attached or counted.
    box=(20*72/300,16*72/300,29*72/300,71*72/300)
    rows=detect_original_jamb_anchored_ink_segments(
        a,b,dpi=300,original_source_jambs=(("vertical",box,16*72/300),))
    assert len(rows)==1
    assert rows[0].pixel_support_bounds==(20,16,29,35)
    assert _MIN_LINE_LENGTH_PT==4.0
    assert rows[0].pixel_support_bounds[3]<48


def test_short_end_source_cannot_borrow_distant_valid_run():
    a,b=_image_and_flank(paint_at_end=2)
    box=(20*72/300,16*72/300,29*72/300,71*72/300)
    rows=detect_original_jamb_anchored_ink_segments(
        a,b,dpi=300,original_source_jambs=(("vertical",box,16*72/300),))
    assert not rows


def test_native_changed_pixel_breaks_run_at_first_occlusion():
    a,b=_image_and_flank(paint_at_end=20,alter=True)
    box=(20*72/300,16*72/300,29*72/300,71*72/300)
    rows=detect_original_jamb_anchored_ink_segments(
        a,b,dpi=300,original_source_jambs=(("vertical",box,16*72/300),))
    assert len(rows)==1
    assert rows[0].pixel_support_bounds==(20,16,29,33)


def test_false_original_cap_is_rejected():
    a,b=_image_and_flank(paint_at_end=20)
    box=(20*72/300,16*72/300,29*72/300,71*72/300)
    with pytest.raises(ValueError,match="source cap"):
        detect_original_jamb_anchored_ink_segments(
            a,b,dpi=300,original_source_jambs=(("vertical",box,38*72/300),))


@pytest.mark.parametrize("mode",[None,-1,300.0,"300",0,True])
def test_source_dpi_requires_exact_positive_integer(mode):
    a,b=_image_and_flank()
    with pytest.raises(ValueError):
        detect_original_jamb_anchored_ink_segments(
            a,b,dpi=mode,original_source_jambs=())


def _original():
    if not PDF.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: requires SHA-verified Lot16 PDF; not a passing source validation")
    raw=PDF.read_bytes()
    assert sha256(raw).hexdigest()==SHA
    pdf=fitz.open(stream=raw,filetype="pdf")
    assert len(pdf)==13 and pdf[2].rotation==0
    scratch=fitz.open()
    try:
        scratch.insert_pdf(pdf,from_page=2,to_page=2)
        page=scratch[0]
        page.add_redact_annot(page.rect,fill=False)
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=fitz.PDF_REDACT_TEXT_REMOVE)
        scale=fitz.Matrix(300/72,300/72)
        ink=page.get_pixmap(matrix=scale,alpha=False,annots=False).tobytes("png")
        full=pdf[2].get_pixmap(matrix=scale,alpha=False,annots=False).tobytes("png")
    finally:
        scratch.close()
        pdf.close()
    return ink,full


def test_actual_original_ba7f_has_77pt_contiguous_jamb_end():
    a,b=_original()
    box=(581.04,411.84,584.16,503.04)
    rows=detect_original_jamb_anchored_ink_segments(
        a,b,dpi=300,original_source_jambs=(("vertical",box,503.04),))
    assert len(rows)==1
    assert rows[0].pixel_support_bounds==(2421,1776,2434,2096)
    assert (2096-1776+1)*72/300==pytest.approx(77.04)
    assert rows[0].geometry_pt[3]==pytest.approx(503.04)
    assert ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION.startswith("original_g17_jamb")


def test_actual_original_b248_048pt_jamb_run_does_not_qualify():
    a,b=_original()
    rows=detect_original_jamb_anchored_ink_segments(
        a,b,dpi=300,original_source_jambs=(
            ("vertical",(604.8,191.76,607.44,197.52),197.52),
        ))
    assert rows==()


def test_positive_integer_low_dpi_is_an_allowed_source_render_parameter():
    # This checks only the typed DPI gate, not whether a 1 DPI raster can
    # physically provide a >=4pt source-ink band.
    a,b=_image_and_flank()
    assert detect_original_jamb_anchored_ink_segments(
        a,b,dpi=1,original_source_jambs=()) == ()


def test_bool_dpi_cannot_enter_original_jamb_source_geometry():
    a,b=_image_and_flank()
    with pytest.raises(ValueError, match="positive integer"):
        detect_original_jamb_anchored_ink_segments(
            a,b,dpi=True,original_source_jambs=())
