"""The app's source-native preview keeps mitred corner paint in its exterior outline (on by default).

Synthetic only; no private source. ``pb_source_wall_joint_paint_continuity`` admits opaque black wall-layer pieces that sit flush
against admitted walls on two sides into the outline step's topology union. The canonical preview now asks for it, and it can be
turned off. Nothing here is a wall, a length, an area or a quantity.
"""
from __future__ import annotations

import fitz
import pytest

import pb_new_source_trace_preview as canonical

LAYER = "Enclosure_WallExternal"
# top (stops short of the corner), right (owns the corner square), bottom, left; offset onto the page
WALLS = ((0.0, 0.0, 94.0, 2.5), (97.5, 0.0, 100.0, 80.0), (0.0, 77.5, 97.5, 80.0), (0.0, 2.5, 2.5, 77.5))
JOINT = ((94.0, 0.0), (97.5, 0.0), (97.5, 1.2), (94.0, 2.5))
ORIGIN = (60.0, 60.0)


def _pdf(path, *, joint=True):
    doc = fitz.open()
    page = doc.new_page(width=300.0, height=220.0)
    layer = doc.add_ocg(LAYER)
    ox, oy = ORIGIN
    for x0, y0, x1, y1 in WALLS:
        page.draw_rect(fitz.Rect(ox + x0, oy + y0, ox + x1, oy + y1), color=None, fill=(0, 0, 0), oc=layer)
    if joint:
        shape = page.new_shape()
        shape.draw_polyline([fitz.Point(ox + x, oy + y) for x, y in (*JOINT, JOINT[0])])
        shape.finish(color=None, fill=(0, 0, 0), closePath=True, oc=layer)
        shape.commit()
    doc.save(path)
    doc.close()
    return path


def test_the_preview_closes_a_mitred_corner_and_says_how_many_pieces_it_used(tmp_path):
    summary, png = canonical.source_native_trace_preview(_pdf(tmp_path / "corner.pdf"), 0)
    assert summary["external_wall_trace_status"] == "CANDIDATE", summary["external_wall_trace_reason"]
    assert summary["external_wall_joint_paint_count"] == 1
    assert png


def test_switched_off_the_preview_reads_the_corner_as_open(tmp_path):
    summary, _png = canonical.source_native_trace_preview(_pdf(tmp_path / "corner.pdf"), 0, admit_wall_joint_paint=False)
    assert summary["external_wall_trace_status"] == "ABSTAINED"
    assert "external_wall_joint_paint_count" not in summary


def test_a_page_without_a_corner_piece_is_the_same_either_way(tmp_path):
    path = _pdf(tmp_path / "open.pdf", joint=False)
    on, on_png = canonical.source_native_trace_preview(path, 0)
    off, off_png = canonical.source_native_trace_preview(path, 0, admit_wall_joint_paint=False)
    assert on == off and on_png == off_png and on["external_wall_trace_status"] == "ABSTAINED"


@pytest.mark.parametrize("bad", [1, 0, None, "yes"])
def test_the_switch_must_be_a_real_boolean(bad):
    with pytest.raises(ValueError, match="new_trace_admit_wall_joint_paint_must_be_bool"):
        canonical.source_native_trace_preview("missing.pdf", 0, admit_wall_joint_paint=bad)
