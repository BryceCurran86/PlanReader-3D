"""Whole-body nonregression for real sealed/customer receipts before frozen 4/4."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from pb_source_closed_run_export import (
    _build_sealed_run,
    sealed_source_closed_run_from_dict,
)
from tools import gpt3_frozen_120_score_delta_guard as delta


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "engineering" / "lot16_original_signed_eight_row_20261015"


def _files(tmp_path):
    a = tmp_path / "before"
    b = tmp_path / "after"
    a.mkdir()
    b.mkdir()
    for folder in (a, b):
        shutil.copyfile(
            ARCHIVE / "production" / "source_sealed_run.json",
            folder / "seal.json",
        )
        shutil.copyfile(
            ARCHIVE / "production" / "verified_customer_rows.json",
            folder / "customer.json",
        )
    return a / "seal.json", b / "seal.json", a / "customer.json", b / "customer.json"


def _reseal(path, quantities):
    original = sealed_source_closed_run_from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    candidate = _build_sealed_run(
        quantities,
        project_id=original.project_id,
    )
    path.write_text(candidate.to_json(), encoding="utf-8")


def test_archived_original_eight_signed_and_customer_full_bodies_retained(tmp_path):
    before, after, before_customer, after_customer = _files(tmp_path)
    result = delta.compare_signed_customer_retention(
        before, after, before_customer, after_customer,
    )
    assert result["comparison_status"] == "SIGNED_AND_CUSTOMER_BODIES_PRESERVED"
    assert result["baseline_signed_quantity_count"] == 8
    assert result["candidate_signed_quantity_count"] == 8
    assert result["baseline_customer_quantity_count"] == 8
    assert result["additional_signed_quantity_count"] == 0
    assert result["official_score_comparison_available"] is False
    assert result["original_source_producer_reexecuted_by_this_guard"] is False


def test_signed_guard_rejects_valid_resealed_run_with_missing_original_quantity(tmp_path):
    before, after, old_customer, after_customer = _files(tmp_path)
    source = sealed_source_closed_run_from_dict(json.loads(after.read_text()))
    _reseal(after, source.quantities[:-1])
    customers = json.loads(after_customer.read_text())
    after_customer.write_text(json.dumps(customers[:-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="dropped an existing signed quantity"):
        delta.compare_signed_customer_retention(before, after, old_customer, after_customer)


def test_signed_guard_rejects_reissued_quantity_id_even_if_candidate_is_sealed(tmp_path):
    before, after, old_customer, after_customer = _files(tmp_path)
    source = sealed_source_closed_run_from_dict(json.loads(after.read_text()))
    changed = (
        replace(source.quantities[0], quantity_id="different-source-quantity-id"),
        *source.quantities[1:],
    )
    _reseal(after, changed)
    with pytest.raises((ValueError, RuntimeError)):
        delta.compare_signed_customer_retention(before, after, old_customer, after_customer)


def test_signed_guard_rejects_whole_customer_body_change(tmp_path):
    before, after, old_customer, after_customer = _files(tmp_path)
    rows = json.loads(after_customer.read_text())
    rows[0]["element"] = "changed after sealing"
    after_customer.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError)):
        delta.compare_signed_customer_retention(before, after, old_customer, after_customer)


def test_signed_guard_cli_emits_retention_not_official_score(tmp_path):
    before, after, old_customer, after_customer = _files(tmp_path)
    out = tmp_path / "guard.json"
    assert delta.main([
        "--before-sealed-run", str(before),
        "--after-sealed-run", str(after),
        "--before-customer", str(old_customer),
        "--after-customer", str(after_customer),
        "--output", str(out),
    ]) == 0
    payload = json.loads(out.read_text())
    assert payload["schema_version"] == "gpt3-signed-customer-retention-v1"
    assert payload["official_score_comparison_available"] is False
    assert payload["original_source_producer_reexecuted_by_this_guard"] is False
    assert payload["baseline_signed_quantity_count"] == 8


def test_signed_guard_refuses_missing_actual_candidate_and_output_alias(tmp_path):
    before, after, old_customer, after_customer = _files(tmp_path)
    after.unlink()
    with pytest.raises(ValueError, match="regular source receipt"):
        delta.compare_signed_customer_retention(before, after, old_customer, after_customer)
    shutil.copyfile(before, after)
    with pytest.raises(ValueError, match="cannot overwrite"):
        delta.main([
            "--before-sealed-run", str(before),
            "--after-sealed-run", str(after),
            "--before-customer", str(old_customer),
            "--after-customer", str(after_customer),
            "--output", str(old_customer),
        ])
