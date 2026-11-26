"""Focused regression & parity tests for Runtime Optimization Slice 1."""
from __future__ import annotations

import cv2
import fitz
import numpy as np
import pytest

import pb_raster_opening_source_primitives as rop
from pb_source_observation_authority import (
    SourceObservationProducer,
    _observation_ids_with_derived,
)


def _reference_raw_axis_line_runs(
    line_mask: np.ndarray,
    *,
    dpi: int,
    axis: str,
    exclude_mask: np.ndarray | None = None,
    registration_scale: tuple[float, float] = (1.0, 1.0),
):
    source_work = line_mask if axis == "horizontal" else np.ascontiguousarray(line_mask.T)
    excluded_work = None
    if exclude_mask is not None:
        excluded_work = exclude_mask if axis == "horizontal" else np.ascontiguousarray(exclude_mask.T)
        work = (source_work & (excluded_work == 0)).astype(np.uint8)
    else:
        work = source_work
    along_scale, _ = rop._axis_registration_scales(axis, registration_scale)
    minimum = rop._scaled_px(rop.THIN_RUN_MIN_PT, dpi, along_scale)
    out = []
    for row_index, row in enumerate(work):
        padded = np.pad(row.astype(np.int8, copy=False), (1, 1))
        transitions = np.diff(padded)
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1) - 1
        for start, end in zip(starts.tolist(), ends.tolist()):
            if end - start + 1 < minimum:
                continue
            if excluded_work is not None:
                if start > 0 and bool(source_work[row_index, start - 1]) and bool(excluded_work[row_index, start - 1]):
                    start -= 1
                if end + 1 < source_work.shape[1] and bool(source_work[row_index, end + 1]) and bool(excluded_work[row_index, end + 1]):
                    end += 1
            center = float(row_index)
            geometry = (float(start), center, float(end), center)
            if axis == "vertical":
                geometry = (center, float(start), center, float(end))
            out.append(rop._primitive(rop.RASTER_LINE_RUN, geometry, dpi=dpi))
    return tuple(out)


def test_vectorized_raw_axis_line_runs_bit_exact_against_reference() -> None:
    rng = np.random.default_rng(42)
    mask = np.zeros((96, 120), dtype=np.uint8)
    excl = np.zeros((96, 120), dtype=np.uint8)
    # Long horizontal and vertical runs touching excluded wall poche
    mask[10, 5:60] = 1
    excl[10, 0:6] = 1
    excl[10, 59:70] = 1
    mask[25, 10:15] = 1  # too short
    mask[40:90, 30] = 1
    excl[35:41, 30] = 1
    mask |= (rng.random(mask.shape) > 0.92).astype(np.uint8)

    for axis in ("horizontal", "vertical"):
        for use_excl in (None, excl):
            expected = _reference_raw_axis_line_runs(mask, dpi=144, axis=axis, exclude_mask=use_excl)
            actual = tuple(rop._raw_axis_line_run_primitives(mask, dpi=144, axis=axis, exclude_mask=use_excl))
            assert actual == expected


def test_detect_raster_opening_primitives_cache_hits_and_isolates_modified_png(monkeypatch) -> None:
    img = np.full((120, 160), 255, dtype=np.uint8)
    img[20:30, 15:140] = 0
    ok1, buf1 = cv2.imencode(".png", img)
    assert ok1
    png1 = buf1.tobytes()

    img2 = img.copy()
    img2[70:80, 20:130] = 0
    ok2, buf2 = cv2.imencode(".png", img2)
    assert ok2
    png2 = buf2.tobytes()

    rop._PRIMITIVE_CACHE.clear()
    decode_calls = 0
    orig_imdecode = cv2.imdecode

    def counting_imdecode(*args, **kwargs):
        nonlocal decode_calls
        decode_calls += 1
        return orig_imdecode(*args, **kwargs)

    monkeypatch.setattr(rop.cv2, "imdecode", counting_imdecode)
    res1 = rop.detect_raster_opening_source_primitives(png1, dpi=144)
    res1_repeat = rop.detect_raster_opening_source_primitives(png1, dpi=144)
    assert res1 == res1_repeat
    assert decode_calls == 1

    res2 = rop.detect_raster_opening_source_primitives(png2, dpi=144)
    assert res2 != res1
    assert decode_calls == 2


def test_observation_ids_with_derived_bisect_matches_sorted_union() -> None:
    parent = tuple(f"obs:{i:05d}" for i in range(0, 400, 2))
    derived = ["obs:00000", "obs:00001", "obs:00199", "obs:00399", "obs:00401", "obs:00001"]
    expected = tuple(sorted(set(parent) | set(derived)))
    assert _observation_ids_with_derived(parent, derived) == expected
    assert _observation_ids_with_derived(parent, ["obs:00000", "obs:00010"]) is parent
    assert _observation_ids_with_derived((), ["b", "a", "a"]) == ("a", "b")


def test_render_native_page_png_caches_full_page_and_detects_tamper(monkeypatch) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200.0, height=150.0)
    page.draw_line(fitz.Point(20, 20), fitz.Point(180, 20), color=(0, 0, 0), width=1.5)
    raw = doc.tobytes()
    doc.close()

    producer = SourceObservationProducer(producer_method="test-cache", producer_version="1.0")
    pub = producer.ingest_native_pdf_bytes(
        document_id="doc-render-cache",
        source_bytes=raw,
        source_locator="memory:render.pdf",
    )
    args = dict(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id="1",
        dpi=144.0,
    )
    png_a, parent_a = producer.render_native_page_png(**args, images_only=False)
    png_b, parent_b = producer.render_native_page_png(**args, images_only=False)
    assert png_a == png_b
    assert parent_a == parent_b
    assert (pub.revision.source_sha256, 1, 144.0, False) in producer._native_image_only_png_cache

    # Tampered source bytes must still be rejected immediately.
    producer._store.source_bytes_by_revision[pub.revision.revision_id] = raw + b"tamper"
    with pytest.raises(Exception):
        producer.render_native_page_png(**args, images_only=False)
