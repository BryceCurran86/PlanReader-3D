"""Actual original Lot16 G17 paint: page-3 source-owned, nonpublishing."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import fitz
import pytest

from pb_raster_unchanged_band_segments import (
    detect_original_one_ended_ink_band_segments,
)
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT

SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
RECEIPT = Path("docs/engineering/gptmax_lot16_host_source_queue_20261016.json")


def source():
    payload = PDF.read_bytes()
    assert sha256(payload).hexdigest() == SOURCE_SHA
    assert json.loads(RECEIPT.read_text())["source_sha256"] == SOURCE_SHA
    doc=fitz.open(stream=payload,filetype="pdf")
    try:
        page=doc[2]
        assert len(doc)==13 and page.rotation==0
        scratch=fitz.open()
        try:
            scratch.insert_pdf(doc,from_page=2,to_page=2)
            original=scratch[0]
            original.add_redact_annot(original.rect,fill=False)
            original.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                text=fitz.PDF_REDACT_TEXT_REMOVE,
            )
            scale=300/72
            images=original.get_pixmap(matrix=fitz.Matrix(scale,scale),
                                       alpha=False,annots=False).tobytes("png")
            full=page.get_pixmap(matrix=fitz.Matrix(scale,scale),
                                 alpha=False,annots=False).tobytes("png")
        finally:
            scratch.close()
    finally:
        doc.close()
    return images, full


def original_faces(case):
    # Source evidence is a previously issued original physical-opening G17
    # inventory, not a frozen benchmark prediction.
    faces=[p["geometry_pdf_pts"] for p in case["source_g17_observations"]
           if p["observation_kind"] == "raster_wall_band_face"]
    grouped={}
    for x0,y0,x1,y1 in faces:
        if x0==x1 and y0<y1:
            key=("vertical",y0,y1)
            grouped.setdefault(key,[]).append(x0)
        elif y0==y1 and x0<x1:
            key=("horizontal",x0,x1)
            grouped.setdefault(key,[]).append(y0)
        else:
            raise AssertionError("malformed original G17 face")
    boxes=[]
    for (axis,lo,hi), offsets in grouped.items():
        assert len(offsets)==2 and offsets[0]!=offsets[1]
        a,b=sorted(offsets)
        bbox=(lo,a,hi,b) if axis=="horizontal" else (a,lo,b,hi)
        boxes.append((axis,bbox))
    assert len(boxes)==2
    return tuple(sorted(boxes))


def test_original_six_real_pdf_sources_preserve_source_negative_evidence():
    original,full=source()
    inventory=json.loads(RECEIPT.read_text())["case_evidence"]
    requested=[r for r in inventory if "source_g17_observations" in r]
    assert len(requested)==6
    observed={}
    for row in requested:
        boxes=original_faces(row)
        segments=detect_original_one_ended_ink_band_segments(
            original,full,dpi=300,source_closed_flank_boxes=boxes)
        assert all(any(s.pixel_support_bounds==tuple(
            round(v*300/72) for v in box)
            for _,box in boxes) for s in segments)
        observed[row["physical_opening_id"][-32:][:8]]=len(segments)
    # These are original ink-family regression receipts, not wall counts,
    # opening counts, FIRM quantities or expected benchmark item matches.
    assert observed == {
        "33d277d4":2,"81a45c3a":2,"a68d0b7d":2,
        "b2489726":1,"ba7f75a2":1,"f8197523":2,
    }
    assert _MIN_LINE_LENGTH_PT == 4.0


def test_original_33d_is_painted_17_cells_with_no_invented_outer_cap():
    original,full=source()
    box=("horizontal",(581.04,361.68,584.88,363.84))
    segment=detect_original_one_ended_ink_band_segments(
        original,full,dpi=300,source_closed_flank_boxes=(box,))
    assert len(segment)==1
    assert segment[0].pixel_support_bounds == (2421,1507,2437,1516)
    assert (2437-2421+1)*72/300==pytest.approx(4.08)
    assert segment[0].geometry_pt[2]-segment[0].geometry_pt[0]==pytest.approx(4.08)
    assert segment[0].pixel_geometry[0]==pytest.approx(2420.5)
    assert segment[0].pixel_geometry[2]==pytest.approx(2437.5)
