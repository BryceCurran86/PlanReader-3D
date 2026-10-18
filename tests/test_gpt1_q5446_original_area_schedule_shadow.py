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
    assert all(not r.glyph_correspondence_authenticated for r in report.rows)
    assert all(not r.physical_surface_owner_authenticated for r in report.rows)
    assert all(not r.customer_projection_allowed for r in report.rows)
    assert report.printed_floor_subtotal_delta_m2 == Decimal("0.01")
    assert report.printed_total_rollup_delta_m2 == Decimal("0.00")
