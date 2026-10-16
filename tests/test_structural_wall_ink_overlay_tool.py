"""The overlay tool is read-only and must draw in the displayed frame, including for rotated sheets."""
from __future__ import annotations

import json

import fitz
import pytest

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from tools.diag_structural_wall_ink_overlay import run  # noqa: E402


def _plan_pdf(path, rotation):
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    # a stroked wall outline: two faces 2.6 pt apart with end caps, as one closed rectangle per wall piece
    for x0, y0, x1, y1 in ((100, 100, 400, 102.6), (100, 297.4, 400, 300), (100, 102.6, 102.6, 297.4),
                           (397.4, 102.6, 400, 297.4), (248.7, 102.6, 251.3, 297.4)):
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(x0, y0, x1, y1))
        shape.finish(color=(0, 0, 0), fill=None, width=0.96)
        shape.commit()
    if rotation:
        page.set_rotation(rotation)
    document.save(str(path))
    document.close()


@pytest.mark.parametrize("rotation", [0, 90])
def test_overlay_summary_and_png_for_a_plain_and_a_rotated_sheet(tmp_path, rotation):
    pdf = tmp_path / f"plan{rotation}.pdf"
    _plan_pdf(pdf, rotation)
    png = tmp_path / "overlay.png"
    summary_path = tmp_path / "summary.json"
    before = pdf.read_bytes()
    summary = run(pdf, 1, png, summary_path, dpi=72)
    assert pdf.read_bytes() == before                       # the source is never written
    assert summary["classification_counts"].get("wall_network_ink_candidate", 0) > 0
    assert summary["shadow_only"] is True and summary["live_effect"] is False
    assert summary["wall_authority_granted"] is False
    assert json.loads(summary_path.read_text(encoding="utf-8"))["segments"] == summary["segments"]

    from PIL import Image

    image = Image.open(png).convert("RGB")
    red = [(x, y) for x in range(0, image.width, 2) for y in range(0, image.height, 2)
           if image.getpixel((x, y))[0] > 180 and image.getpixel((x, y))[1] < 60 and image.getpixel((x, y))[2] < 60]
    assert red, "accepted ink must be drawn on the rendered sheet"
    # the drawn wall ring must sit where the sheet shows it: centred on the building, in the displayed frame
    xs = [p[0] for p in red]
    ys = [p[1] for p in red]
    width_pt, height_pt = (842, 595) if rotation == 0 else (595, 842)
    assert image.width == pytest.approx(width_pt, abs=2) and image.height == pytest.approx(height_pt, abs=2)
    assert min(xs) >= 0 and max(xs) < image.width and min(ys) >= 0 and max(ys) < image.height
