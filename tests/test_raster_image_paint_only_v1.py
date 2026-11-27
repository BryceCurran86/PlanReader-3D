"""Image-region raster segments only where the picture painted them, default off (#4764 7228707838). Synthetic only."""
from __future__ import annotations

import fitz
import numpy as np
import pytest

from pb_source_visibility_authority import SourceVisibilityProducer


def _picture():
    pixels = np.full((400, 400), 255, dtype=np.uint8)
    pixels[198:202, 40:360] = 0  # the picture's own line, at page y = 100
    return fitz.Pixmap(fitz.csGRAY, 400, 400, pixels.tobytes(), False)


def _page(*, picture=True, lines=True, text=True):
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    if picture:
        page.insert_image(fitz.Rect(0, 0, 200, 200), pixmap=_picture())
    if lines:
        page.draw_line((20, 140), (180, 140), color=(0, 0, 0), width=1.0)
        page.draw_line((20, 170), (180, 170), color=(0, 0, 0), width=1.0)
    if text:
        page.insert_text((40, 60), "IIIIIIIIIIIIIIIIIIIIII", fontsize=18)
    data = document.tobytes()
    document.close()
    return data


def _raster(data, **options):
    source = SourceVisibilityProducer(producer_method="image-paint-test", producer_version="1", **options)
    published = source.ingest_native_pdf_bytes(document_id="paint", source_bytes=data, source_locator="memory://p.pdf")
    published = source.augment_with_raster_visible_segments(published.revision.revision_id)
    snapshot = published.snapshot.snapshot_id
    found = {}
    for (sid, _observation), record in source._producer._store.observations.items():
        ref = str(record.source_primitive_ref)
        if sid == snapshot and ref.startswith("raster_segment:"):
            found[record.observation_id] = tuple(round(float(v), 2) for v in record.geometry)
    return found


def _levels(found):
    return sorted({round(g[1] / 10) * 10 for g in found.values() if abs(g[3] - g[1]) < 1})


def test_only_the_pictures_own_lines_remain_with_the_option():
    data = _page()
    off, on = _raster(data), _raster(data, raster_image_paint_only_shadow=True)
    assert {100, 140, 170} <= set(_levels(off))  # the native lines over the picture are found again
    assert any(g[1] < 80 for g in off.values())  # and the letters
    assert _levels(on) == [100] and not any(g[1] < 80 for g in on.values())
    assert set(on.values()) <= set(off.values())  # nothing new: the same geometry, fewer segments


def test_default_off_is_exactly_the_historical_capture():
    data = _page()
    assert _raster(data) == _raster(data, raster_image_paint_only_shadow=False)


@pytest.mark.parametrize("kwargs", [dict(lines=False, text=False), dict(picture=False)], ids=["scan", "no-picture"])
def test_pure_pictures_and_pages_without_pictures_are_not_affected(kwargs):
    data = _page(**kwargs)
    assert _raster(data) == _raster(data, raster_image_paint_only_shadow=True)


def test_the_option_must_be_a_boolean():
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="m", producer_version="1", raster_image_paint_only_shadow="yes")
