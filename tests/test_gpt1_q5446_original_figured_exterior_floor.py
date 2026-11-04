"""Source-neutral QA: original vector figure -> source-sealed customer floor."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os

import pytest

from pb_gpt1_q5446_original_figured_exterior_floor import (
    _X_FIGURE_GLYPHS, _Y_FIGURE_GLYPHS,
    _X_CAPTION_STROKES, _Y_CAPTION_STROKES,
    _X_ENDPOINT_TICKS, _Y_ENDPOINT_TICKS,
    _X_DIMENSION_LINE, _Y_DIMENSION_LINE,
    _figured_native_mm, _original_source_figure_receipts,
    produce_original_figured_exterior_floor,
    seal_and_project_original_figured_exterior_floor,
)
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass
class P:
    x: float
    y: float


@dataclass
class R:
    x0: float
    y0: float
    x1: float
    y1: float


def _glyph(char: str, rect: R, *, vertical: bool) -> dict:
    template = {
        "0": (16, .43, .0), "1": (3, .0, .2),
        "2": (13, .07, .25), "3": (14, .14, .0),
        "4": (3, .67, 1.), "5": (16, .86, .0),
        "6": (22, .92, .17), "7": (2, .27, 1.),
        "8": (28, .36, .0), "9": (22, 1., .33),
    }
    n, px, py = template[char]
    if vertical:
        first = P(rect.x0 + py * (rect.x1 - rect.x0),
                  rect.y0 + (1 - px) * (rect.y1 - rect.y0))
    else:
        first = P(rect.x0 + px * (rect.x1 - rect.x0),
                  rect.y0 + py * (rect.y1 - rect.y0))
    return {
        "type": "s", "color": (0., 0., 0.), "width": .72,
        "rect": rect, "items": [("l", first, first)] * n,
    }


def _line(x0, y0, x1, y1, *, width=.48):
    return {
        "type": "s", "color": (0., 0., 0.), "width": width,
        "rect": R(x0, y0, x1, y1), "items": [("l", P(x0,y0), P(x1,y1))],
    }


def _complete_source_figures():
    max_path = max((*_Y_CAPTION_STROKES, *_X_CAPTION_STROKES, *_Y_FIGURE_GLYPHS))
    drawings = [{} for _ in range(max_path + 1)]
    for index, c in enumerate("3000"):
        x0 = 831.12 + index * 4.8
        w = 3.6 if index == 3 else 3.36
        drawings[_X_FIGURE_GLYPHS[index]] = _glyph(
            c, R(x0, 90.96, x0 + w, 96.72), vertical=False,
        )
    for index, c in enumerate("4000"):
        y0 = 412.56 if index == 0 else 408.0 - (index - 1) * 4.8
        h = 3.6 if index == 0 else 3.36
        drawings[_Y_FIGURE_GLYPHS[index]] = _glyph(
            c, R(1054.08, y0, 1059.84, y0+h), vertical=True,
        )
    drawings[_X_ENDPOINT_TICKS[0]] = _line(797.52, 93.84, 797.52, 110.88)
    drawings[_X_ENDPOINT_TICKS[1]] = _line(882.48, 93.84, 882.48, 110.88)
    drawings[_X_DIMENSION_LINE] = _line(799.68, 98.16, 880.32, 98.16)
    drawings[_Y_ENDPOINT_TICKS[0]] = _line(1048.56, 350.64, 1065.36, 350.64)
    drawings[_Y_ENDPOINT_TICKS[1]] = _line(1048.56, 463.8, 1065.36, 463.8)
    drawings[_Y_DIMENSION_LINE] = _line(1061.28, 352.8, 1061.28, 461.64)
    caption_counts = (2, 1, 2, 2, 1, 10, 1, 2, 1, 1, 19, 17, 20)
    for i, n in enumerate(caption_counts):
        drawings[_X_CAPTION_STROKES[i]] = {
            "type": "s", "color": (0., 0., 0.), "width": .48,
            "rect": R(826.08 + i*2., 99.6, 827.08 + i*2., 103.68),
            "items": [("l", P(1, 1), P(2, 2))] * n,
        }
        drawings[_Y_CAPTION_STROKES[i]] = {
            "type": "s", "color": (0., 0., 0.), "width": .48,
            "rect": R(1062.72, 390.0 + i*2., 1066.8, 391.0 + i*2.),
            "items": [("l", P(1, 1), P(2, 2))] * n,
        }
    return drawings


def test_two_original_vector_figure_axes_are_independently_recoverable():
    drawings = _complete_source_figures()
    before = deepcopy(drawings)
    assert _figured_native_mm(drawings, _X_FIGURE_GLYPHS, "horizontal") == 3000
    assert _figured_native_mm(drawings, _Y_FIGURE_GLYPHS, "vertical") == 4000
    result = _original_source_figure_receipts(drawings)
    assert result is not None
    assert result[:2] == (3000, 4000)
    assert drawings == before


@pytest.mark.parametrize("target", [
    _X_DIMENSION_LINE, _Y_DIMENSION_LINE,
    _X_ENDPOINT_TICKS[0], _Y_ENDPOINT_TICKS[1],
])
def test_missing_dimension_axis_or_tick_blocks_source_metric(target):
    drawings = _complete_source_figures()
    drawings[target] = dict(drawings[target], type="f")
    assert _original_source_figure_receipts(drawings) is None


@pytest.mark.parametrize("target", [_X_FIGURE_GLYPHS[0], _Y_FIGURE_GLYPHS[0]])
def test_incomplete_or_foreign_numeric_glyph_blocks_original_figure(target):
    drawings = _complete_source_figures()
    drawings[target] = dict(drawings[target], width=.96)
    assert _original_source_figure_receipts(drawings) is None


@pytest.mark.parametrize("target", [_X_CAPTION_STROKES[0], _Y_CAPTION_STROKES[4]])
def test_broken_source_caption_identity_blocks_floor_ownership(target):
    drawings = _complete_source_figures()
    original = drawings[target]
    drawings[target] = dict(original, items=original["items"] + original["items"])
    assert _original_source_figure_receipts(drawings) is None


def test_cross_axis_figured_scale_conflict_cannot_be_silently_snapped():
    drawings = _complete_source_figures()
    drawings[_Y_FIGURE_GLYPHS[0]] = _glyph(
        "8", R(1054.08, 412.56, 1059.84, 415.92), vertical=True,
    )
    assert _figured_native_mm(drawings, _Y_FIGURE_GLYPHS, "vertical") == 8000
    assert _original_source_figure_receipts(drawings) is None


def test_wrong_or_missing_original_source_never_mints_commercial_metric(tmp_path):
    unavailable = produce_original_figured_exterior_floor(
        tmp_path / "missing.pdf", workspace_id=3, project_id="source-plan-project",
    )
    assert unavailable.status is EvidenceResolutionStatus.ABSTAINED
    assert unavailable.quantity is None
    fake = tmp_path / "not_original.pdf"
    fake.write_bytes(b"%PDF-1.7\nwrong original source")
    unavailable = produce_original_figured_exterior_floor(
        fake, workspace_id=3, project_id="source-plan-project",
    )
    assert unavailable.status is EvidenceResolutionStatus.ABSTAINED
    assert unavailable.quantity is None
    with pytest.raises(ValueError, match="original exterior floor unavailable"):
        seal_and_project_original_figured_exterior_floor(
            fake, workspace_id=3, project_id="source-plan-project",
        )


def test_exact_private_original_source_to_customer_positive_when_provisioned():
    path = os.environ.get("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not path:
        pytest.skip("private original unavailable to public runner; no source claim")
    source = produce_original_figured_exterior_floor(
        path, workspace_id=13, project_id="private-source-project",
    )
    assert source.status is EvidenceResolutionStatus.CORROBORATED, source.reason_codes
    assert source.quantity is not None
    assert source.quantity.value == 12.0
    sealed, rows = seal_and_project_original_figured_exterior_floor(
        path, workspace_id=13, project_id="private-source-project",
    )
    assert len(sealed.quantities) == len(rows) == 1
    assert rows[0]["quantity"] == 12.0
    assert rows[0]["quantity_family"] == "floor_area"
    assert rows[0]["quantity_status"] == "To review"
