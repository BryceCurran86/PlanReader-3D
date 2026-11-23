"""Cross-plan original diagnostic evidence pair tests.

Synthetic documents model different layouts and page scopes. These tests do
NOT authenticate any private original, physical quantity or frozen120 result.
"""
from __future__ import annotations

import hashlib
import json
import struct

import fitz
import pytest

from tools.run_original_footprint_first import run


def _unrelated_source(tmp_path, layout: str):
    source_dir = tmp_path / layout
    source_dir.mkdir()
    path = source_dir / "unrelated_original.pdf"
    with fitz.open() as document:
        if layout == "small_residential":
            width, height = 900, 660
            floor = document.new_page(width=width, height=height)
            floor.draw_rect(
                fitz.Rect(140, 140, 730, 455), color=(0, 0, 0), width=4,
            )
            floor.draw_line(
                (440, 140), (440, 455), color=(0, 0, 0), width=3,
            )
            floor.draw_line(
                (140, 300), (730, 300), color=(0, 0, 0), width=3,
            )
        else:
            width, height = 1280, 920
            floor = document.new_page(width=width, height=height)
            # A closed stepped envelope, unlike a compact rectangular house.
            corners = (
                (170, 155), (1040, 155), (1040, 425),
                (730, 425), (730, 675), (170, 675), (170, 155),
            )
            for a, b in zip(corners, corners[1:]):
                floor.draw_line(a, b, color=(0, 0, 0), width=4)
            floor.draw_line(
                (440, 155), (440, 675), color=(0, 0, 0), width=3,
            )
            # This green legend is not an authorized wall.
            floor.draw_rect(
                fitz.Rect(970, 760, 1220, 840), color=(0, .6, 0), width=1,
            )
        floor.insert_text(
            (35, 65), "Drawing title: Floor Plan\nScale: 1:100",
        )
        non_plan = document.new_page(width=width, height=height)
        non_plan.insert_text(
            (35, 65), "Drawing title: Roof Plan\nScale: 1:100",
        )
        document.save(path)
    return path, width, height


@pytest.mark.parametrize("layout", ("small_residential", "stepped_commercial"))
def test_generic_evidence_json_and_png_match_across_source_styles_and_pages(
    tmp_path, layout,
):
    """Publish both artifacts for unrelated formats and abstaining non-plan pages."""
    path, width, height = _unrelated_source(tmp_path, layout)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    destination = tmp_path / layout / "diagnostic"
    reports = []

    for page_index, title in ((0, "Floor Plan"), (1, "Roof Plan")):
        receipt, json_path, png_path = run(
            path, page_index, destination, expected_sha256=sha,
            expected_drawing_title=title,
        )
        reports.append((json_path, png_path))
        assert json_path.name == f"page_{page_index + 1}_footprint_first.json"
        assert png_path.name == f"page_{page_index + 1}_footprint_first.png"
        assert json.loads(json_path.read_text(encoding="utf8")) == receipt
        assert receipt["source_sha256"] == sha
        assert receipt["source_sha_pin_verified"] is True
        assert receipt["source_page_title_verified"] is True
        assert receipt["page_index_0based"] == page_index
        assert receipt["commercial_quantity_rows"] == 0
        assert receipt["official_frozen120_score_change"] == 0
        assert receipt["topology"]["room_quantity_authorized"] is False
        raw_png = png_path.read_bytes()
        assert receipt["overlay"]["png_filename"] == png_path.name
        assert receipt["overlay"]["png_byte_count"] == len(raw_png)
        assert receipt["overlay"]["png_sha256"] == hashlib.sha256(raw_png).hexdigest()
        assert raw_png.startswith(b"\x89PNG\r\n\x1a\n")
        pixel_width, pixel_height = struct.unpack(">II", raw_png[16:24])
        assert pixel_width >= width and pixel_height >= height
        assert pixel_width <= width * 2 and pixel_height <= height * 2
        if page_index == 1:
            assert receipt["exterior"]["status"] == "ABSTAINED"
            assert receipt["topology"]["gap_review_performed"] is False

    assert reports[0] != reports[1]
    assert all(path.is_file() for pair in reports for path in pair)


def test_generic_diagnostic_junction_graph_has_no_job_specific_focus_default():
    """Source-native graph must inspect whole submitted page, not Acacia paths."""
    import ast
    import inspect
    from tools.run_original_footprint_first import run

    tree = ast.parse(inspect.getsource(run))
    matching = [
        call for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "build_source_native_wall_body_junction_graph"
    ]
    assert len(matching) == 1
    assert not any(
        item.arg == "focus_native_path_ids"
        for item in matching[0].keywords
    )
