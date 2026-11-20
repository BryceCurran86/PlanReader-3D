"""Public CI proof for the ten-sealed verifier using the committed Lot16 eight-row seal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.verify_ten_source_sealed_quantities import collect_verified_items, select_ten

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "engineering" / "lot16_original_signed_eight_row_20261015" / "production"


def test_collect_verified_items_lot16_signed_eight():
    summary, items = collect_verified_items(
        sealed_path=FIXTURE / "source_sealed_run.json",
        customer_path=FIXTURE / "verified_customer_rows.json",
    )
    assert summary["valid_quantity_count"] == 8
    assert summary["complete"] is True
    assert len(items) == 8
    assert all(item["verified"] is True for item in items)
    assert all(item["family"] == "opening_area" for item in items)
    assert sorted(round(float(item["value"]), 2) for item in items) == sorted(
        [0.54, 0.9, 1.26, 1.8, 1.8, 2.16, 2.16, 10.08]
    )


def test_select_ten_reports_incomplete_when_pool_has_only_eight(tmp_path: Path):
    sealed = FIXTURE / "source_sealed_run.json"
    customer = FIXTURE / "verified_customer_rows.json"
    receipt = select_ten([(sealed, customer)], required=10)
    assert receipt["complete"] is False
    assert receipt["selected_count"] == 8
    assert receipt["acacia_p2_metric_seal_gate"]["first_remaining_gate"] == (
        "seal_blocked_title_block_scale_not_firm"
    )
    assert receipt["acacia_p2_metric_seal_gate"]["seal_eligible"] is False


def test_select_eight_completes_from_committed_seal():
    sealed = FIXTURE / "source_sealed_run.json"
    customer = FIXTURE / "verified_customer_rows.json"
    receipt = select_ten([(sealed, customer)], required=8)
    assert receipt["complete"] is True
    assert receipt["selected_count"] == 8
    assert len({row["quantity_id"] for row in receipt["selected"]}) == 8


def test_cli_writes_receipt_for_eight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import tools.verify_ten_source_sealed_quantities as mod

    sealed = FIXTURE / "source_sealed_run.json"
    customer = FIXTURE / "verified_customer_rows.json"
    out = tmp_path / "receipt.json"

    def _pools(_root: Path):
        return [(sealed, customer)]

    monkeypatch.setattr(mod, "_default_pools", _pools)
    rc = mod.main(["--packet-root", str(tmp_path), "--out", str(out), "--required", "8"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["complete"] is True
    assert payload["selected_count"] == 8
