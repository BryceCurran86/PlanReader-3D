"""P2a: the canonical preview traces and draws a /Rotate 90 sheet in the page's NATIVE frame.

``page.get_drawings()`` rows and every overlay coordinate live in the page's native frame, but the preview used to build its
tiles, canvas and background from ``page.rect``, the DISPLAYED rectangle. At /Rotate 90 the displayed extent is the native
extent transposed, so the tiles and the canvas covered only part of the sheet and the PNG background was the native region
unrotated. These tests use synthetic pages only: a closed room whose walls lie entirely in the band the old tiles missed.
The frame itself comes from the existing seam ``pb_native_page_frame.native_page_frame``; 180, 270 and unreadable frames fail
closed there, and so here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
import pytest

import pb_new_source_trace_preview as preview_module
from pb_native_page_frame import NativePageFrameUnresolved, native_page_frame
from pb_new_source_trace_preview import (
    _full_page_source_tiles,
    _new_native_frame_canvas,
    source_native_trace_preview,
)

NATIVE_W, NATIVE_H = 700.0, 1000.0
# A closed room of four 5 pt black bars, entirely in the native band y > 700: at /Rotate 90 the displayed rectangle is 1000 x 700,
# so the band the old tiles and the old canvas never covered.
ROOM = ((160, 780, 165, 960), (530, 780, 535, 960), (165, 780, 530, 785), (165, 955, 530, 960))
ROOM_INNER = (165.0, 785.0, 530.0, 955.0)  # the air between the bars, in unscaled, uncropped native points

# keys that legitimately differ between the same native content on different /Rotate values
ROTATION_ONLY_KEYS = {"source_sha256", "native_page_frame", "preview_png_orientation"}


def _build_pdf(
    tmp_path: Path, *, rotation: int = 0, user_unit: float = 1, crop=None, name: str = "sheet.pdf",
    room=ROOM, size=(NATIVE_W, NATIVE_H), grey_lines=(),
) -> Path:
    path = tmp_path / name
    with fitz.open() as doc:
        page = doc.new_page(width=size[0], height=size[1])
        for rect in room:
            page.draw_rect(fitz.Rect(*rect), color=None, fill=(0, 0, 0))
        for start, end in grey_lines:  # unrelated, non-wall ink
            page.draw_line(start, end, color=(0.6, 0.6, 0.6), width=0.5)
        if crop is not None:
            left, top, right, bottom = crop
            page.set_cropbox(fitz.Rect(left, top, NATIVE_W - right, NATIVE_H - bottom))
        if user_unit != 1:
            doc.xref_set_key(page.xref, "UserUnit", str(user_unit))
        if rotation:
            page.set_rotation(rotation)
        doc.save(path)
    return path


def _native_rect_to_display(rotation: int, native_height: float, box):
    """A native-frame box in displayed-frame points (0 and 90 only: the two frames the seam resolves)."""
    x0, y0, x1, y1 = box
    if rotation == 0:
        return (x0, y0, x1, y1)
    assert rotation == 90
    # displayed x = native height - native y; displayed y = native x
    return (native_height - y1, x0, native_height - y0, x1)


def _scan(pix: fitz.Pixmap, predicate, step: int = 2):
    xs, ys = [], []
    samples, n, width = pix.samples, pix.n, pix.width
    for y in range(0, pix.height, step):
        base = y * width * n
        for x in range(0, width, step):
            offset = base + x * n
            if predicate(samples[offset], samples[offset + 1], samples[offset + 2]):
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _is_ring_green(r, g, b):
    return g > 140 and r < 90 and b < 110


def _is_black(r, g, b):
    return r < 60 and g < 60 and b < 60


@pytest.fixture
def seen_viewports(monkeypatch):
    seen: list = []
    real = preview_module.build_layered_wall_doorway_room_rings

    def spy(*args, **kwargs):
        seen.append(kwargs.get("viewport_pdf_pts"))
        return real(*args, **kwargs)

    monkeypatch.setattr(preview_module, "build_layered_wall_doorway_room_rings", spy)
    return seen


# ------------------------------------------------------------------------------------------------ the frame itself

def test_the_synthetic_pages_are_what_the_tests_say_they_are(tmp_path):
    with fitz.open(_build_pdf(tmp_path, rotation=90)) as doc:
        page = doc[0]
        frame = native_page_frame(page)
        assert (page.rect.width, page.rect.height) == (NATIVE_H, NATIVE_W)  # displayed 1000 x 700
        assert (frame.native_width, frame.native_height) == (NATIVE_W, NATIVE_H)
        rows = page.get_drawings()
        assert len(rows) == 4
        assert all(row["rect"].y0 > page.rect.height for row in rows)  # every bar lies outside the displayed rectangle read as native


def test_room_in_the_band_the_displayed_rectangle_missed_is_traced(tmp_path):
    summary, png = source_native_trace_preview(_build_pdf(tmp_path, rotation=90), 0)
    assert summary["status"] == "candidate"
    assert summary["candidate_enclosed_regions"] >= 1
    assert summary["wall_strip_count"] >= 4
    assert summary["quantity_authorized"] is False and summary["commercial_publishable"] is False
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_tiles_cover_the_native_extent_at_rotate_90(tmp_path, seen_viewports):
    source_native_trace_preview(_build_pdf(tmp_path, rotation=90), 0)
    (tiles,) = seen_viewports
    assert min(t[0] for t in tiles) == 0.0 and min(t[1] for t in tiles) == 0.0
    assert max(t[2] for t in tiles) == NATIVE_W
    assert max(t[3] for t in tiles) == NATIVE_H
    assert tuple(tiles) == _full_page_source_tiles(NATIVE_W, NATIVE_H, 4)


def test_upright_tiles_are_exactly_the_old_formula(tmp_path, seen_viewports):
    source_native_trace_preview(_build_pdf(tmp_path, rotation=0), 0)
    (tiles,) = seen_viewports
    assert tuple(tiles) == _full_page_source_tiles(NATIVE_W, NATIVE_H, 4)


def _canonical(summary: dict, source_pdf: Path) -> str:
    """The summary as text with the source's own digest (it differs with /Rotate, wherever it appears) masked."""
    text = json.dumps({k: v for k, v in summary.items() if k not in ROTATION_ONLY_KEYS}, sort_keys=True, default=repr)
    return text.replace(hashlib.sha256(source_pdf.read_bytes()).hexdigest(), "SOURCE_SHA256")


def test_same_native_content_gives_the_same_trace_at_rotate_0_and_90(tmp_path):
    upright_pdf = _build_pdf(tmp_path, rotation=0, name="a.pdf")
    turned_pdf = _build_pdf(tmp_path, rotation=90, name="b.pdf")
    upright, upright_png = source_native_trace_preview(upright_pdf, 0)
    turned, turned_png = source_native_trace_preview(turned_pdf, 0)
    assert upright["candidate_enclosed_regions"] >= 1
    assert _canonical(upright, upright_pdf) == _canonical(turned, turned_pdf)
    assert upright_png != turned_png  # a different orientation, by design


def _counts(summary: dict) -> dict:
    keys = ("status", "reason_codes", "candidate_enclosed_regions", "temporary_opening_closures", "wall_strip_count",
            "wall_gap_count", "unresolved_wall_gap_count", "source_tile_count")
    return {key: summary[key] for key in keys}


def test_translating_the_room_does_not_change_the_rotated_trace(tmp_path):
    base = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="a.pdf"), 0)[0]
    shifted = tuple((x0 + 40, y0 - 30, x1 + 40, y1 - 30) for x0, y0, x1, y1 in ROOM)
    moved = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="b.pdf", room=shifted), 0)[0]
    assert base["candidate_enclosed_regions"] >= 1
    assert _counts(base) == _counts(moved)


def test_unrelated_ink_elsewhere_does_not_change_the_rotated_trace(tmp_path):
    base = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="a.pdf"), 0)[0]
    grey = (((50, 100), (650, 100)), ((50, 500), (650, 500)))
    noisy = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="b.pdf", grey_lines=grey), 0)[0]
    assert base["candidate_enclosed_regions"] >= 1
    assert _counts(base) == _counts(noisy)


def test_a_taller_page_with_the_same_room_gives_the_same_rotated_trace(tmp_path):
    base = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="a.pdf"), 0)[0]
    taller = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="b.pdf", size=(NATIVE_W, 1400.0)), 0)[0]
    assert base["candidate_enclosed_regions"] >= 1
    assert _counts(base) == _counts(taller)


@pytest.mark.parametrize("rotation", [180, 270])
def test_unsupported_frames_fail_closed_before_any_tracing(tmp_path, monkeypatch, seen_viewports, rotation):
    called = []
    monkeypatch.setattr(preview_module, "scope_outlined_vector_lettering", lambda *a, **k: called.append(1))
    with pytest.raises(ValueError, match="new_trace_native_page_frame_unresolved") as info:
        source_native_trace_preview(_build_pdf(tmp_path, rotation=rotation), 0)
    assert isinstance(info.value.__cause__, NativePageFrameUnresolved)
    assert not seen_viewports and not called


def test_an_unreadable_frame_fails_closed(tmp_path, monkeypatch):
    def refuse(page):
        raise NativePageFrameUnresolved("native_page_frame_unresolved")

    monkeypatch.setattr(preview_module, "native_page_frame", refuse)
    with pytest.raises(ValueError, match="new_trace_native_page_frame_unresolved"):
        source_native_trace_preview(_build_pdf(tmp_path), 0)


# ------------------------------------------------------------------------------------------------ the receipt

def test_the_receipt_appears_on_rotated_pages_only(tmp_path):
    upright, _ = source_native_trace_preview(_build_pdf(tmp_path, rotation=0, name="a.pdf"), 0)
    turned, _ = source_native_trace_preview(_build_pdf(tmp_path, rotation=90, name="b.pdf"), 0)
    assert "native_page_frame" not in upright and "preview_png_orientation" not in upright
    frame = turned["native_page_frame"]
    assert frame["rotation"] == 90
    assert (frame["native_width"], frame["native_height"]) == (NATIVE_W, NATIVE_H)
    assert (frame["display_width"], frame["display_height"]) == (NATIVE_H, NATIVE_W)
    assert frame["coordinate_space"] == "native_page_user_space"
    assert turned["preview_png_orientation"] == "displayed"


# ------------------------------------------------------------------------------------------------ the picture

@pytest.mark.parametrize(
    "rotation,user_unit,crop",
    [(0, 1, None), (90, 1, None), (90, 2, None), (90, 1, (20, 20, 20, 20)), (90, 2, (20, 20, 20, 20)), (0, 2, (20, 20, 20, 20))],
)
def test_png_is_complete_displayed_oriented_and_aligned_with_the_overlays(tmp_path, rotation, user_unit, crop):
    pdf = _build_pdf(tmp_path, rotation=rotation, user_unit=user_unit, crop=crop)
    summary, png = source_native_trace_preview(pdf, 0)
    assert summary["candidate_enclosed_regions"] >= 1
    with fitz.open(pdf) as doc:
        page = doc[0]
        rect = page.rect
        rows = page.get_drawings()
        frame = native_page_frame(page)
    zoom = min(1.2, 1800 / max(float(rect.width), float(rect.height)))
    pix = fitz.Pixmap(png)
    # complete and displayed-oriented: the PNG is the displayed extent at the preview zoom, never the native extent turned
    assert abs(pix.width - rect.width * zoom) <= 1 and abs(pix.height - rect.height * zoom) <= 1

    # expected positions come from the page's own rows, mapped from the native frame to the displayed frame
    scale = user_unit
    union = fitz.Rect(rows[0]["rect"])
    for row in rows[1:]:
        union |= fitz.Rect(row["rect"])
    expected_walls = _native_rect_to_display(rotation, frame.native_height, tuple(union))
    inner = (union.x0 + 5 * scale, union.y0 + 5 * scale, union.x1 - 5 * scale, union.y1 - 5 * scale)
    expected_ring = _native_rect_to_display(rotation, frame.native_height, inner)

    def within(found, expected, tolerance):
        assert found is not None
        assert all(abs(f - e * zoom) <= tolerance for f, e in zip(found, expected)), (found, [e * zoom for e in expected])

    within(_scan(pix, _is_black), expected_walls, 6)       # the background is drawn under the same frame
    within(_scan(pix, _is_ring_green), expected_ring, 6)   # the ring overlay lands on the room's air


def _build_two_page_pdf(tmp_path: Path) -> Path:
    """Page 0 upright with its room inside the displayed rectangle; page 1 the rotated sheet with the room in the lost band."""
    path = tmp_path / "two.pdf"
    with fitz.open() as doc:
        first = doc.new_page(width=NATIVE_W, height=NATIVE_H)
        for rect in ((160, 120, 165, 300), (530, 120, 535, 300), (165, 120, 530, 125), (165, 295, 530, 300)):
            first.draw_rect(fitz.Rect(*rect), color=None, fill=(0, 0, 0))
        second = doc.new_page(width=NATIVE_W, height=NATIVE_H)
        for rect in ROOM:
            second.draw_rect(fitz.Rect(*rect), color=None, fill=(0, 0, 0))
        second.set_rotation(90)
        doc.save(path)
    return path


def test_the_frame_and_the_background_belong_to_the_requested_page_not_the_first(tmp_path):
    pdf = _build_two_page_pdf(tmp_path)
    summary, png = source_native_trace_preview(pdf, 1)
    assert summary["page_index"] == 1 and summary["document_page_count"] == 2
    assert summary["native_page_frame"]["rotation"] == 90
    assert summary["candidate_enclosed_regions"] >= 1
    pix = fitz.Pixmap(png)
    zoom = min(1.2, 1800 / NATIVE_H)
    found = _scan(pix, _is_black)
    expected = _native_rect_to_display(90, NATIVE_H, (160, 780, 535, 960))
    assert found is not None and all(abs(f - e * zoom) <= 6 for f, e in zip(found, expected))
    upright, _ = source_native_trace_preview(pdf, 0)
    assert "native_page_frame" not in upright and upright["candidate_enclosed_regions"] >= 1


def test_the_live_progress_overlays_are_aligned_too(tmp_path):
    payloads: list[dict] = []
    pdf = _build_pdf(tmp_path, rotation=90)
    source_native_trace_preview(pdf, 0, progress_callback=payloads.append)
    final = [p for p in payloads if p["stage"] == "drawing_enclosed_room_candidates"]
    assert len(final) == 1 and final[0]["overlay_png"]
    pix = fitz.Pixmap(final[0]["overlay_png"])
    zoom = min(0.95, 1500 / NATIVE_H)
    assert abs(pix.width - NATIVE_H * zoom) <= 1 and abs(pix.height - NATIVE_W * zoom) <= 1
    expected = _native_rect_to_display(90, NATIVE_H, ROOM_INNER)
    found = _scan(pix, _is_ring_green)
    assert found is not None and all(abs(f - e * zoom) <= 6 for f, e in zip(found, expected)), (found, expected)


# ------------------------------------------------------------------------------------------------ differential and invariants

def test_the_native_frame_canvas_is_the_old_canvas_on_an_upright_page(tmp_path):
    pdf = _build_pdf(tmp_path, rotation=0)
    with fitz.open(pdf) as document, fitz.open() as old_preview, fitz.open() as new_preview:
        page = document[0]
        frame = native_page_frame(page)
        old = old_preview.new_page(width=page.rect.width, height=page.rect.height)
        old.show_pdf_page(old.rect, document, 0)
        new = _new_native_frame_canvas(new_preview, document, 0, frame)
        a = old.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        b = new.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        assert (a.width, a.height) == (b.width, b.height)
        assert a.samples == b.samples


def test_the_source_is_never_modified_and_replay_is_deterministic(tmp_path):
    pdf = _build_pdf(tmp_path, rotation=90)
    before = pdf.read_bytes()
    first = source_native_trace_preview(pdf, 0)
    second = source_native_trace_preview(pdf, 0)
    assert pdf.read_bytes() == before
    assert first[0]["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert json.dumps(first[0], sort_keys=True, default=repr) == json.dumps(second[0], sort_keys=True, default=repr)
    assert first[1] == second[1]
