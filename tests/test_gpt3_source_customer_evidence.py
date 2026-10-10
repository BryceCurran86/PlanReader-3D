"""Evidence-only GPT3 source-to-customer report: no benchmark inference."""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from pb_customer_output_verification import CustomerOutputVerificationError
from pb_source_closed_run_export import SourceClosedRunExportError
from test_customer_output_verification import sealed_and_rows
from tools.diag_gpt3_source_customer_evidence import (
    build_source_customer_evidence_report,
    main,
)


def test_verified_source_customer_report_has_exact_sealed_items_not_benchmark_scores() -> None:
    sealed, rows = sealed_and_rows()
    report = build_source_customer_evidence_report(sealed.to_dict(), rows)

    assert report["project_id"] == sealed.project_id
    assert report["sealed_run_fingerprint_verified"] is True
    assert report["sealed_run_fingerprint"] == sealed.fingerprint
    assert report["quantity_to_customer_parity"]["valid_quantity_count"] == 2
    assert report["quantity_to_customer_parity"]["customer_row_count"] == 2
    assert [q["quantity_id"] for q in report["source_backed_sealed_items"]] == [
        "qty-1", "qty-2",
    ]
    assert all(q["canonical_object_refs"] for q in report["source_backed_sealed_items"])
    assert all(q["source_evidence_ids"] for q in report["source_backed_sealed_items"])
    assert not any(q["quantity_id"] == "qty-abstain" for q in report["source_backed_sealed_items"])
    assert report["input_pdf_sha256_verified"] is False
    assert report["source_object_universe_complete"] == "NOT_DETERMINED"
    assert report["official_frozen_evaluator_status"] == "UNPUBLISHED"
    assert report["official_coverage_accuracy"] is None
    assert report["official_precision_adjusted_accuracy"] is None


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "tampered_quantity"])
def test_report_rejects_invalid_commercial_bijection(mutation: str) -> None:
    sealed, rows = sealed_and_rows()
    rows = [dict(row) for row in rows]
    if mutation == "duplicate":
        rows.append(dict(rows[0]))
    elif mutation == "missing":
        rows.pop()
    else:
        rows[0]["quantity"] = 4444.0
    with pytest.raises(CustomerOutputVerificationError):
        build_source_customer_evidence_report(sealed.to_dict(), rows)


def test_report_rejects_tampered_sealed_run_before_emitting_items() -> None:
    sealed, rows = sealed_and_rows()
    with pytest.raises(SourceClosedRunExportError):
        build_source_customer_evidence_report(replace(sealed, run_id="tampered").to_dict(), rows)


def test_cli_emits_deterministic_diagnostic_json(tmp_path, monkeypatch) -> None:
    sealed, rows = sealed_and_rows()
    sealed_path = tmp_path / "sealed.json"
    rows_path = tmp_path / "rows.json"
    output_path = tmp_path / "report" / "evidence.json"
    sealed_path.write_text(sealed.to_json(), encoding="utf-8")
    rows_path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["diag", "--sealed-run", str(sealed_path), "--customer-rows", str(rows_path), "--output", str(output_path)],
    )
    main()
    first = output_path.read_bytes()
    main()
    assert output_path.read_bytes() == first
    assert json.loads(first)["official_frozen_evaluator_status"] == "UNPUBLISHED"
