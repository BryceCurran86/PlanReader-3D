"""Q5446 printed original architect AREAS table: no FIRM source laundering."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os

import pytest

from pb_gpt1_q5446_original_area_schedule_shadow import (
    SOURCE_SHA256,
    ORIGINAL_TABLE_RULES,
    ORIGINAL_LEFT_BORDER,
    ORIGINAL_LABEL_DIVIDER,
    PRINTED_ORIGINAL_ROWS,
    _rule_matches,
    _table_witnesses_valid,
    _numeric_vector_digit,
    _original_numeric_glyph_receipts,
    ORIGINAL_ROW_Y_BOUNDS,
    inspect_original_q5446_printed_area_schedule,
)


@dataclass
class _Rect:
    x0: float
    y0: float
    x1: float
    y1: float


def _original_ruling_grid():
    strokes = [{} for _ in range(373)]
    for idx, x0, y0, x1, y1 in (
        *ORIGINAL_TABLE_RULES, ORIGINAL_LEFT_BORDER, ORIGINAL_LABEL_DIVIDER,
    ):
        strokes[idx] = {
            "type": "fs", "color": (0.0, 0.0, 0.0),
            "fill": (0.0, 0.0, 0.0),
            "width": 0.375, "rect": _Rect(x0, y0, x1, y1),
        }
    return strokes


def test_original_vector_ruled_schedule_has_nine_independent_path_witnesses():
    assert len(ORIGINAL_TABLE_RULES) == 7
    assert _table_witnesses_valid(_original_ruling_grid())


@pytest.mark.parametrize("target", [
    ORIGINAL_TABLE_RULES[0], ORIGINAL_TABLE_RULES[4],
    ORIGINAL_LEFT_BORDER, ORIGINAL_LABEL_DIVIDER,
])
def test_missing_tampered_or_retyped_original_schedule_structure_abstains(target):
    strokes = _original_ruling_grid()
    idx = target[0]
    for mutation in (
        lambda row: row.update({"type": "s"}),
        lambda row: row.update({"width": 2.0}),
        lambda row: row.update({"rect": _Rect(0.0, 0.0, 0.0, 0.0)}),
        lambda row: row.update({"color": None}),
    ):
        changed = [v.copy() for v in strokes]
        mutation(changed[idx])
        assert not _table_witnesses_valid(changed)


def test_no_source_sha_means_zero_candidate_rows_not_zero_m2(tmp_path):
    missing = inspect_original_q5446_printed_area_schedule(tmp_path / "absent.pdf")
    assert missing.status == "ABSTAIN" and missing.rows == ()
    wrong = tmp_path / "wrong.pdf"
    wrong.write_bytes(b"%PDF-1.7\nnot original")
    tampered = inspect_original_q5446_printed_area_schedule(wrong)
    assert tampered.status == "ABSTAIN"
    assert tampered.rows == ()
    assert tampered.actual_source_sha256 != SOURCE_SHA256


def test_original_printed_values_are_not_recomputed_from_rounded_display():
    values = {key: val for key, _, val, _ in PRINTED_ORIGINAL_ROWS}
    assert values["ground_floor"] == Decimal("123.89")
    assert values["first_floor"] == Decimal("121.81")
    assert values["porch"] == Decimal("4.08")
    assert values["garage"] == Decimal("36.40")
    assert values["alfresco"] == Decimal("12.00")
    assert values["subtotal"] == Decimal("245.71")
    assert values["total"] == Decimal("298.19")
    # Printed subtotal has its own source authority. Preserve discrepancy.
    assert values["subtotal"] - (
        values["ground_floor"] + values["first_floor"]
    ) == Decimal("0.01")
    assert values["subtotal"] + values["porch"] + values["garage"] + values["alfresco"] == values["total"]
    assert sum(not rollup for _, _, _, rollup in PRINTED_ORIGINAL_ROWS) == 5
    assert sum(rollup for _, _, _, rollup in PRINTED_ORIGINAL_ROWS) == 2


@dataclass
class _Point:
    x: float
    y: float


@dataclass
class _Quad:
    ul: _Point


def _outlined_numeral(char: str, x0: float, y0: float):
    shape = {
        "0": (16, 3.36, 5.76, .43, 0.0),
        "1": (3, 1.20, 5.76, 0.0, .20),
        "2": (13, 3.36, 5.76, .07, .25),
        "3": (14, 3.36, 5.76, .14, 0.0),
        "4": (3, 3.60, 5.76, .67, 1.0),
        "5": (16, 3.36, 5.76, .86, 0.0),
        "6": (22, 3.12, 5.76, .92, .17),
        "7": (2, 3.60, 5.76, .27, 1.0),
        "8": (28, 3.36, 5.76, .36, 0.0),
        "9": (22, 3.12, 5.76, 1.0, .33),
        ".": (1, .48, .48, .50, 0.0),
    }
    count, w, h, first_x, first_y = shape[char]
    r = _Rect(x0, y0, x0 + w, y0 + h)
    point = _Point(x0 + w * first_x, y0 + h * first_y)
    items = ([("qu", _Quad(point))] if char == "."
             else [("l", point, point)] * count)
    return {"type": "s", "color": (0., 0., 0.), "width": .96,
            "rect": r, "items": items}


def _synthetic_numeric_table():
    result = _original_ruling_grid()
    for (name, _, original_m2, _), (start, end) in zip(
        PRINTED_ORIGINAL_ROWS, ORIGINAL_ROW_Y_BOUNDS
    ):
        for position, char in enumerate(str(original_m2)):
            y = start + (6.7 if char == "." else 1.6)
            result.append(_outlined_numeral(char, 1041 + position * 4.5, y))
    return result


def test_all_ten_vector_decimal_glyph_shapes_are_independently_decoded():
    for char in "0123456789.":
        assert _numeric_vector_digit(_outlined_numeral(char, 1045, 650)) == char


def test_full_source_numeric_rows_have_unique_ordered_vector_receipts():
    rows = _original_numeric_glyph_receipts(_synthetic_numeric_table())
    assert rows is not None
    assert [len(r) for r in rows] == [6, 6, 6, 4, 5, 5, 6]
    assert len(set(index for row in rows for index in row)) == sum(len(x) for x in rows)


def test_native_6_cannot_be_mutated_into_a_9_or_borrowed_from_another_row():
    source = _synthetic_numeric_table()
    ids = _original_numeric_glyph_receipts(source)
    assert ids is not None
    six = ids[4][1]
    record = source[six].copy()
    rect = record["rect"]
    fake_start = _Point(rect.x0 + rect.x1 - rect.x0, rect.y0 + .34 * (rect.y1 - rect.y0))
    record["items"] = [("l", fake_start, fake_start)] * 22
    source[six] = record
    assert _original_numeric_glyph_receipts(source) is None


def test_private_original_positive_is_optional_not_mocked():
    source = os.environ.get("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not source:
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: original-positive source gate not run")
    report = inspect_original_q5446_printed_area_schedule(source)
    assert report.status == "CANDIDATE", report.reason_codes
    assert report.actual_source_sha256 == SOURCE_SHA256
    assert len(report.rows) == 7
    assert sum(not r.is_rollup for r in report.rows) == 5
    assert all(r.status == "CANDIDATE" for r in report.rows)
    assert all(r.glyph_correspondence_authenticated for r in report.rows)
    assert [len(r.original_numeric_vector_path_ids) for r in report.rows] == [
        6, 6, 6, 4, 5, 5, 6,
    ]
    assert all(not r.physical_surface_owner_authenticated for r in report.rows)
    assert all(not r.customer_projection_allowed for r in report.rows)
    assert report.printed_floor_subtotal_delta_m2 == Decimal("0.01")
    assert report.printed_total_rollup_delta_m2 == Decimal("0.00")
