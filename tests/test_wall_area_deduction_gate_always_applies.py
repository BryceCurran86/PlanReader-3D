"""Regression: the opening-deduction publication gate must not be bypassed
merely because zero openings were detected for a wall.

Root cause this locks in: ``GenericPlanReaderExtractor.extract_from_pdf``
used to call ``GenericOpeningDeductionPipeline`` only ``if opening_instances``
was non-empty. An empty opening list is not evidence that a wall genuinely
has zero doors/windows -- it is at least as likely to mean opening
detection/schedule extraction was incomplete for that document. Bypassing
the pipeline in that case let ``perimeter_walling``'s raw, un-deducted
gross area publish as a final quantity, silently overcounting whenever
openings went undetected (observed on a real benchmark document: a wall
with genuine but undetected windows/doors published its full un-deducted
gross area instead of failing closed).

The pipeline itself already treats an empty local opening list as "not
evidenced zero deduction" (see
``test_empty_local_opening_list_is_not_evidenced_zero_deduction`` in
``tests/test_opening_deduction_pipeline_publication_gate.py``); the bug was
purely that the extractor skipped calling it at all.
"""
from __future__ import annotations

import os
import tempfile

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

_X0, _Y0 = 100.0, 100.0
_WIDTH_PT, _DEPTH_PT = 200.0, 160.0  # 10m x 8m at 20pt/m
_THICKNESS_PT = 4.0


def _build_rectangle_pdf(path: str, *, with_door: bool) -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = _X0 + _WIDTH_PT
    y1 = _Y0 + _DEPTH_PT

    page.draw_rect(fitz.Rect(_X0, _Y0, _X0 + _THICKNESS_PT, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - _THICKNESS_PT, _Y0, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, _Y0, x1, _Y0 + _THICKNESS_PT), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, y1 - _THICKNESS_PT, x1, y1), color=None, fill=(0, 0, 0))

    page.insert_text((_X0, _Y0 - 20), "10,000 x 8,000", fontsize=10)
    page.insert_text((_X0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)

    if with_door:
        page.insert_text((_X0, y1 + 40), "DOOR SCHEDULE", fontsize=10)
        page.insert_text((_X0, y1 + 55), "D1  900 x 2100mm  1 No.  Flush door", fontsize=9)

    doc.save(path)
    doc.close()


def _extract(path: str):
    extractor = GenericPlanReaderExtractor()
    return {p.tag: p for p in extractor.extract_from_pdf(path, pages=[0])}


def test_wall_with_no_detected_openings_does_not_publish_raw_gross_area() -> None:
    """No door/window prediction reaches the pipeline -- perimeter_walling
    must fail closed rather than publish its un-deducted gross area."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "no_openings.pdf")
        _build_rectangle_pdf(path, with_door=False)
        preds = _extract(path)

    assert "perimeter_walling" in preds
    wall_pred = preds["perimeter_walling"]
    assert wall_pred.quantity is None
    metadata = wall_pred.metadata or {}
    assert metadata.get("publication_blocked") is True
    # The raw gross area must still be visible as a diagnostic, never as
    # the published quantity.
    assert metadata.get("gross_area_m2") is not None or metadata.get(
        "provisional_net_area_m2"
    ) is not None


def test_gate_still_reachable_when_an_opening_is_detected() -> None:
    """Sanity check: adding a real opening still routes through the same
    fail-closed gate (net_wall_authority remains unavailable either way, so
    quantity stays None, but the wall must still surface as a tracked,
    blocked prediction rather than disappearing or erroring)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "with_door.pdf")
        _build_rectangle_pdf(path, with_door=True)
        preds = _extract(path)

    assert "perimeter_walling" in preds
    wall_pred = preds["perimeter_walling"]
    assert wall_pred.quantity is None
    assert (wall_pred.metadata or {}).get("publication_blocked") is True
