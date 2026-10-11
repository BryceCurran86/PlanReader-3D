"""Signed source quantity parity is not commercial trade or customer approval."""
from __future__ import annotations

from pathlib import Path

from pb_combine_source_closed_runs import load_verified_sealed_run
from scripts.report_full_plan_v2_readiness import (
    _first_failing_authority_stage, _sealed_projection_proof,
    produced_sealed_parity_blockers,
)
from tools.export_gpt3_produced_items import export_verified_produced_items
from test_gpt3_produced_items_original_source import (
    _original_projected_customer_row, _source_run,
)


def _signed_source_export(tmp_path, *, customer=False):
    source, old_run, _sha, quantity, trace = _source_run(tmp_path)
    root = tmp_path / "sealed"
    target = root / "project-a" / "sealed_run.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(old_run.read_bytes())
    receipt = load_verified_sealed_run(target)
    customers = [_original_projected_customer_row(quantity, trace)] if customer else None
    produced = export_verified_produced_items(
        old_run, [source], expected_project_id="project-a",
        customer_rows=customers,
    )
    return root, receipt, produced


def test_valid_signed_quantity_with_trade_unavailable_and_customer_unchecked_still_has_quantity_parity(tmp_path):
    root, sealed, produced = _signed_source_export(tmp_path)
    raw = produced_sealed_parity_blockers(produced, sealed.quantities)
    assert "projection_trade_category_missing:qty-room-1" in raw
    assert "projection_customer_output_parity_unverified:qty-room-1" in raw
    downstream = []
    assert _sealed_projection_proof(
        root, "project-a", produced, True,
        expected_seal_fingerprint=sealed.fingerprint,
        downstream_reason_sink=downstream,
    ) == (True, [])
    assert downstream == [
        "projection_customer_output_parity_unverified:qty-room-1",
        "projection_trade_category_missing:qty-room-1",
    ]


def test_customer_bijection_proven_but_trade_unavailable_still_has_signed_quantity_parity(tmp_path):
    root, sealed, produced = _signed_source_export(tmp_path, customer=True)
    assert produced[0]["customer_output_parity_verified"] is True
    assert produced[0]["trade_category"] is None
    downstream = []
    assert _sealed_projection_proof(
        root, "project-a", produced, True,
        expected_seal_fingerprint=sealed.fingerprint,
        downstream_reason_sink=downstream,
    ) == (True, [])
    assert downstream == [
        "projection_trade_category_missing:qty-room-1",
    ]


def test_original_identity_or_quantity_tampering_remains_a_quantity_parity_failure(tmp_path):
    root, sealed, produced = _signed_source_export(tmp_path)
    forged = [dict(produced[0])]
    forged[0]["object_refs"] = ["foreign-physical-room"]
    ok, reasons = _sealed_projection_proof(
        root, "project-a", forged, True,
        expected_seal_fingerprint=sealed.fingerprint,
    )
    assert ok is False
    assert "projection_object_identity_mismatch:qty-room-1" in reasons

    forged[0] = dict(produced[0])
    forged[0]["value"] = 999.0
    ok, reasons = _sealed_projection_proof(
        root, "project-a", forged, True,
        expected_seal_fingerprint=sealed.fingerprint,
    )
    assert ok is False
    assert "projection_value_mismatch:qty-room-1" in reasons


def test_first_failure_identifies_customer_then_trade_after_quantity_parity():
    common = dict(
        source_verified=True, source_reasons=[],
        manifest_status="VERIFIED", manifest_reasons=[],
        sealed_verified=True, seal_reasons=[],
        produced_present=True, produced_valid=True, produced_count=1,
        produced_reasons=[], parity_verified=True, parity_reasons=[],
    )
    assert _first_failing_authority_stage(
        **common, customer_verified=False,
        customer_reasons=["customer_rows_not_supplied"],
    ) == ("CUSTOMER_OUTPUT_BIJECTION", "customer_rows_not_supplied")
    assert _first_failing_authority_stage(
        **common, customer_verified=True, customer_reasons=[],
    ) == ("COMMERCIAL_TRADE_AUTHORITY", "commercial_trade_authority_not_independently_verified")
