from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_auto_geometry_v1219 as auto
from pb_migration_contracts import QuantityEvidence


def _quantity(
    *,
    quantity_id: str = "opening-area-1",
    canonical_id: str = "opening-1",
    kind: str = "window",
    value: float = 2.172,
    basis: str = "figured_opening_label",
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="opening_area",
        semantic_key=f"{kind}_area:{canonical_id}",
        value=value,
        unit="m2",
        input_entity_ids=(canonical_id,),
        formula="authenticated figured opening-label dimension product",
        formula_version="1.0.0",
        evidence_ids=(canonical_id, "measurement-1"),
        authority="fixture",
        status="corroborated",
        confidence=1.0,
        abstained=False,
        metadata={
            "canonical_opening_id": canonical_id,
            "opening_kind": kind,
            "area_basis": basis,
            "measurement_record_id": "measurement-1",
            "page_no": "3",
        },
    )


def _named(row):
    return dict(zip(auto.TAKEOFF_ROW_FIELDS, row))


def test_opening_quantity_becomes_reviewable_customer_row_with_same_value() -> None:
    rows, outputs = auto._opening_quantity_customer_rows(
        7,
        SimpleNamespace(opening_quantity_evidence=(_quantity(),)),
    )
    assert len(rows) == 1
    assert len(outputs) == 1
    named = _named(rows[0])

    assert named["workspace_id"] == 7
    assert named["section"] == "Openings"
    assert named["element"] == "Window area"
    assert named["quantity"] == pytest.approx(2.172)
    assert named["unit"] == "m²"
    assert named["quantity_status"] == "Measured"
    assert named["inclusion_status"] == "PROVISIONAL"
    assert named["source_page"] == "p3"
    assert named["source_reference"].startswith(auto.SOURCE_PREFIX)
    assert "opening-area-1" in named["source_reference"]
    assert named["row_role"] == ""

    output = outputs[0]
    assert output.quantity_id == "opening-area-1"
    assert output.value == pytest.approx(2.172)
    assert output.unit == "m2"
    assert output.trade == "window"
    assert output.geometry_ref == "opening-1"
    assert output.dimension_text_id == "measurement-1"
    assert output.is_publishable is False


def test_opening_customer_row_preserves_exact_quantity_without_rounding() -> None:
    value = 1.234567
    rows, _outputs = auto._opening_quantity_customer_rows(
        7,
        SimpleNamespace(
            opening_quantity_evidence=(_quantity(value=value),)
        ),
    )
    assert _named(rows[0])["quantity"] == pytest.approx(value)


def test_untyped_or_unknown_measurement_basis_does_not_publish_customer_row() -> None:
    untyped = _quantity(kind="")
    unknown_basis = _quantity(
        quantity_id="opening-area-2",
        basis="unknown",
    )
    rows, outputs = auto._opening_quantity_customer_rows(
        7,
        SimpleNamespace(
            opening_quantity_evidence=(untyped, unknown_basis)
        ),
    )
    assert rows == []
    assert outputs == ()


def test_duplicate_opening_quantity_id_fails_closed_before_customer_publication() -> None:
    quantity = _quantity()
    with pytest.raises(auto.TakeoffRowContractError, match="duplicate live opening quantity id"):
        auto._opening_quantity_customer_rows(
            7,
            SimpleNamespace(
                opening_quantity_evidence=(quantity, quantity)
            ),
        )
