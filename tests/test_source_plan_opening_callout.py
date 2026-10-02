from __future__ import annotations

import hashlib

import fitz
import pytest

from pb_source_plan_opening_callout import (
    SOURCE_PLAN_OPENING_CALLOUT_BINDING_REQUIRED,
    extract_source_plan_opening_callouts,
)


def _pdf_bytes(
    *,
    title: str = "FLOOR PLAN",
    lines: tuple[str, ...] = (),
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((40, 40), title, fontsize=12)
    y = 90
    for line in lines:
        page.insert_text((60, y), line, fontsize=8)
        y += 30
    payload = doc.tobytes()
    doc.close()
    return payload


def _extract(payload: bytes):
    sha = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        return extract_source_plan_opening_callouts(
            doc[0],
            source_sha256=sha,
            source_page=1,
        )
    finally:
        doc.close()


def test_explicit_compact_window_and_door_callouts_publish_source_area() -> None:
    result = _extract(
        _pdf_bytes(
            lines=(
                "1218 SGW",
                "0630 FG",
                "2127 STACKER",
                "2148 PANEL LIFT",
            )
        )
    )
    assert len(result) == 4
    by_callout = {item.raw_callout: item for item in result}

    window = by_callout["1218 SGW"]
    assert window.opening_kind == "window"
    assert window.trade_category == "windows"
    assert window.width_mm == 1800.0
    assert window.height_mm == 1200.0
    assert window.area_m2 == pytest.approx(2.16)
    assert window.quantity_evidence.value is None
    assert window.quantity_evidence.unit == "m2"
    assert window.quantity_evidence.input_entity_ids == ()
    assert window.quantity_evidence.status == "abstained"
    assert window.quantity_evidence.abstained is True
    assert window.quantity_evidence.blocking_reasons == (
        SOURCE_PLAN_OPENING_CALLOUT_BINDING_REQUIRED,
    )
    assert window.quantity_evidence.metadata["observed_area_m2"] == pytest.approx(2.16)
    assert window.quantity_evidence.metadata["source_callout_id"] == window.opening_id
    assert window.quantity_evidence.metadata["physical_opening_identity_bound"] is False
    assert window.quantity_evidence.metadata["shadow_only"] is True
    assert window.quantity_evidence.metadata["commercial_projection_allowed"] is False

    door = by_callout["2127 STACKER"]
    assert door.opening_kind == "door"
    assert door.trade_category == "doors"
    assert door.width_mm == 2700.0
    assert door.height_mm == 2100.0
    assert door.area_m2 == pytest.approx(5.67)


def test_duplicate_callout_text_remains_distinct_by_source_location() -> None:
    result = _extract(_pdf_bytes(lines=("1218 SGW", "1218 SGW")))
    assert len(result) == 2
    assert result[0].raw_callout == result[1].raw_callout == "1218 SGW"
    assert result[0].opening_id != result[1].opening_id
    assert result[0].bbox != result[1].bbox


def test_bare_dimensions_never_create_openings() -> None:
    result = _extract(
        _pdf_bytes(
            lines=(
                "870",
                "1200",
                "1218",
                "2890 1900",
                "24940",
            )
        )
    )
    assert result == ()


def test_non_floor_plan_scope_is_rejected() -> None:
    result = _extract(
        _pdf_bytes(
            title="ELEVATIONS",
            lines=("1218 SGW", "2127 STACKER"),
        )
    )
    assert result == ()


def test_explicit_descriptor_must_resolve_one_opening_kind() -> None:
    result = _extract(
        _pdf_bytes(
            lines=(
                "1218 NOTE",
                "1218 SGW DOOR",
                "2127 STACKER WINDOW",
            )
        )
    )
    assert result == ()


def test_physically_impossible_compact_code_fails_closed() -> None:
    result = _extract(
        _pdf_bytes(
            lines=(
                "9918 SGW",
                "0199 SGW",
                "0912 STACKER",
            )
        )
    )
    assert result == ()


def test_source_callout_measurement_never_mints_commercial_physical_identity() -> None:
    result = _extract(
        _pdf_bytes(
            lines=(
                "1218 SGW",
                "2127 STACKER",
            )
        )
    )
    assert len(result) == 2
    for callout in result:
        quantity = callout.quantity_evidence
        assert quantity.abstained is True
        assert quantity.value is None
        assert quantity.input_entity_ids == ()
        assert SOURCE_PLAN_OPENING_CALLOUT_BINDING_REQUIRED in quantity.reason_codes
        assert quantity.metadata["source_callout_id"] == callout.opening_id
