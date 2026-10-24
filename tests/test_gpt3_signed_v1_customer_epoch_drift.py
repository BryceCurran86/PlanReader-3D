"""Previous customer approval is never portable to a re-sealed source epoch."""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

import pb_quantity_takeoff_adapter as adapter
from pb_customer_output_verification import CustomerOutputVerificationError
from pb_source_closed_run_export import seal_source_closed_run
from test_customer_output_verification import quantity, trace, authority
from tools.gpt3_signed_v1_physical_drift import (
    build_signed_v1_physical_drift_report, main,
)


def _epochs(tmp_path):
    q = quantity("physical-1", "canonical-floor-1")
    changed = replace(q, value=99.0)
    t = trace(q)
    originals = [q, changed]
    files = []
    for index, source in enumerate(originals):
        sealed = seal_source_closed_run(
            (source,), project_id="project-7",
            traces_by_quantity_id={source.quantity_id: t},
        )
        rows = adapter.quantities_to_takeoff_output_rows(
            (source,), traces_by_quantity_id={source.quantity_id: t},
            authorities_by_quantity_id={source.quantity_id: authority()},
        )
        sealed_path = tmp_path / f"source-{index}.json"
        customer_path = tmp_path / f"customer-{index}.json"
        sealed_path.write_text(json.dumps(sealed.to_dict()), encoding="utf-8")
        customer_path.write_text(json.dumps(rows), encoding="utf-8")
        files.append((sealed_path, customer_path))
    return files


def test_customer_provenance_for_both_epochs_is_independent(tmp_path):
    (old_source, old_customer), (new_source, new_customer) = _epochs(tmp_path)
    report = build_signed_v1_physical_drift_report(
        baseline_path=old_source,
        candidate_path=new_source,
        baseline_customer_path=old_customer,
        candidate_customer_path=new_customer,
    )
    assert report["customer_epoch_bijection"] == "BOTH_INDEPENDENTLY_VERIFIED"
    assert report["baseline_verified_customer_count"] == 1
    assert report["candidate_verified_customer_count"] == 1
    assert report["comparison_status"] == "DIAGNOSTIC_DRIFT"
    assert "value" in report["physical_semantic_conflicts"][0]["changed_fields"]
    assert report["official_v2_accuracy"] is None
    assert report["publication_status"] == "UNPUBLISHED"


def test_valid_previous_customer_cannot_be_reused_after_quantity_value_changes(tmp_path):
    (old_source, old_customer), (new_source, new_customer) = _epochs(tmp_path)
    # Both runs independently signed, and both have equal quantity counts.
    # Only the NEW producer-owned projection is valid for the NEW signature.
    with pytest.raises(CustomerOutputVerificationError):
        build_signed_v1_physical_drift_report(
            baseline_path=old_source,
            candidate_path=new_source,
            baseline_customer_path=old_customer,
            candidate_customer_path=old_customer,
        )


def test_customer_epoch_argument_cannot_be_one_sided(tmp_path):
    (old_source, old_customer), (new_source, _) = _epochs(tmp_path)
    with pytest.raises(ValueError, match="both source-closed customer"):
        build_signed_v1_physical_drift_report(
            baseline_path=old_source,
            candidate_path=new_source,
            baseline_customer_path=old_customer,
        )


def test_customer_epoch_cli_remains_create_only_without_score(tmp_path):
    (old_source, old_customer), (new_source, new_customer) = _epochs(tmp_path)
    output = tmp_path / "original-epoch-comparison.json"
    argv = [
        "--baseline-sealed", str(old_source),
        "--candidate-sealed", str(new_source),
        "--baseline-customer", str(old_customer),
        "--candidate-customer", str(new_customer),
        "--output", str(output),
    ]
    assert main(argv) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["customer_epoch_bijection"] == "BOTH_INDEPENDENTLY_VERIFIED"
    assert result["official_v2_accuracy"] is None
    with pytest.raises(FileExistsError):
        main(argv)
