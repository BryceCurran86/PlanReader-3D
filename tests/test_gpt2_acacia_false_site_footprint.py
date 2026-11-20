"""Do not mistake enclosing site/roof linework for the building's painted walls.

Acacia's owner-original floor plan exposed a thin, visually closed outer frame
which outranked separate thick physical wall runs. These PDF fixtures are
synthetic: no private drawing, benchmark answer or area enters the regression.
"""
from __future__ import annotations

from hashlib import sha256
import fitz
import pytest

from pb_external_footprint_first_trace import trace_external_footprint_first


def _fixture(*, thin_site_frame: bool) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=1100, height=780)
    if thin_site_frame:
        # An apparent fully closed project envelope. Two enclosed interior
        # buildings have real bold ink but cannot authenticate that envelope.
        page.draw_rect(fitz.Rect(145, 105, 950, 605),
                       color=(.10, .10, .10), width=2)
        page.draw_line((250, 210), (500, 210), color=(0, 0, 0), width=3)
        page.draw_line((630, 215), (865, 215), color=(0, 0, 0), width=3)
        page.draw_line((500, 210), (500, 400), color=(0, 0, 0), width=3)
    else:
        page.draw_rect(fitz.Rect(145, 105, 950, 605),
                       color=(0, 0, 0), width=4)
        page.draw_line((545, 105), (545, 605), color=(0, 0, 0), width=3)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_closed_thin_site_envelope_with_bold_disjoint_rooms_abstains():
    raw = _fixture(thin_site_frame=True)
    (trace,) = trace_external_footprint_first(
        raw, source_sha256=sha256(raw).hexdigest(), page_indices=(0,),
    )
    assert trace.status == 'ABSTAINED'
    assert trace.reason == 'external_footprint_unverified_native_wall_edges'
    assert trace.polygon_pdf_pts == ()
    assert trace.measurement_authorized is False
    assert trace.commercial_publishable is False


def test_real_bold_continuous_wall_enclosure_remains_candidate():
    raw = _fixture(thin_site_frame=False)
    (trace,) = trace_external_footprint_first(
        raw, source_sha256=sha256(raw).hexdigest(), page_indices=(0,),
    )
    assert trace.status == 'CANDIDATE'
    assert trace.bbox_pdf_pts is not None
    assert trace.measurement_authorized is False
    assert trace.commercial_publishable is False


def test_original_source_sha_is_required_even_for_diagnostic():
    raw = _fixture(thin_site_frame=True)
    with pytest.raises(ValueError, match='source_sha_mismatch'):
        trace_external_footprint_first(raw, source_sha256='0' * 64, page_indices=(0,))
