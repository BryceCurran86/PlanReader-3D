"""A matching count/area never authorizes re-keying a different physical opening."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import copy
import hashlib
import json

import pytest

from pb_source_closed_run_export import seal_source_closed_run
from test_customer_output_verification import quantity, trace
from tools.gpt3_signed_v1_physical_drift import (
    compare_signed_v1_physical_runs,
    build_signed_v1_physical_drift_report,
    main,
)


def _run(*pairs):
    return seal_source_closed_run(
        [q for q, _ in pairs],
        project_id="project-7",
        traces_by_quantity_id={q.quantity_id: t for q, t in pairs},
    )


def _pair(qid="qty-1", eid="floor-1", amount=12.5):
    q = quantity(qid, eid, value=amount)
    return q, trace(q)


def _files(tmp_path, old, new):
    paths = [tmp_path / "old.json", tmp_path / "new.json"]
    paths[0].write_text(json.dumps(old.to_dict()), encoding="utf-8")
    paths[1].write_text(json.dumps(new.to_dict()), encoding="utf-8")
    return paths


def test_exact_signed_v1_run_is_identical_without_issuer_promotion():
    q, t = _pair()
    run = _run((q, t))
    result = compare_signed_v1_physical_runs(run, run)
    assert result["comparison_status"] == "BYTE_IDENTICAL_SIGNED_RECEIPTS"
    assert result["unchanged_quantity_ids"] == ["qty-1"]
    assert result["source_authenticated"] is False
    assert result["official_v2_accuracy"] is None


def test_same_quantity_with_changed_source_evidence_is_never_called_unchanged():
    q, t = _pair()
    newer_q = replace(q, evidence_ids=("different-original-evidence",))
    newer_t = replace(t, evidence_ids=("different-original-evidence",))
    old = _run((q, t))
    new = _run((newer_q, newer_t))
    result = compare_signed_v1_physical_runs(old, new)
    assert result["comparison_status"] == "DIAGNOSTIC_DRIFT"
    assert result["physical_semantic_conflicts"] == []
    row = result["receipt_changed_quantity_ids"][0]
    assert row["quantity_id"] == "qty-1"
    assert "evidence_ids" in row["changed_receipt_fields"]
    assert row["old_fingerprint"] != row["new_fingerprint"]
    assert result["unchanged_quantity_ids"] == []


def test_same_quantity_id_changed_measurement_is_physical_semantic_conflict():
    q, t = _pair()
    old = _run((q, t))
    new = _run((replace(q, value=99.0), t))
    result = compare_signed_v1_physical_runs(old, new)
    assert result["comparison_status"] == "DIAGNOSTIC_DRIFT"
    assert result["receipt_changed_quantity_ids"] == []
    assert result["physical_semantic_conflicts"][0]["changed_fields"] == ["value"]


def test_equal_area_and_same_run_size_cannot_rekey_physical_identity():
    qa, ta = _pair(qid="old-physical", eid="old-opening", amount=5.67)
    qb, tb = _pair(qid="new-physical", eid="new-opening", amount=5.67)
    result = compare_signed_v1_physical_runs(_run((qa, ta)), _run((qb, tb)))
    assert result["baseline_quantity_count"] == result["candidate_quantity_count"] == 1
    assert result["removed_quantity_ids"] == ["old-physical"]
    assert result["added_quantity_ids"] == ["new-physical"]
    assert not result["unchanged_quantity_ids"]
    assert result["quantity_ids_alias_inferred"] is False
    assert result["comparison_status"] == "DIAGNOSTIC_DRIFT"


def test_quantity_id_stable_but_physical_refs_changed_is_semantic_conflict():
    qa, ta = _pair()
    qb = replace(qa, input_entity_ids=("different-physical-floor",))
    tb = replace(ta, canonical_entity_ids=("different-physical-floor",))
    result = compare_signed_v1_physical_runs(_run((qa, ta)), _run((qb, tb)))
    assert "object_identity_refs" in result["physical_semantic_conflicts"][0]["changed_fields"]


def test_cross_document_source_package_cannot_be_row_compared():
    qa, ta = _pair()
    qb = replace(qa, metadata={**qa.metadata, "source_sha256": "b" * 64})
    tb = replace(ta, source_sha256="b" * 64)
    result = compare_signed_v1_physical_runs(_run((qa, ta)), _run((qb, tb)))
    assert result["comparison_status"] == "SOURCE_PACKAGE_NOT_COMPARABLE"
    assert result["source_sha_receipts_equal"] is False
    assert not result["physical_semantic_conflicts"]
    assert not result["unchanged_quantity_ids"]


def test_signed_runs_from_different_projects_are_rejected():
    qa, ta = _pair()
    old = _run((qa, ta))
    qb = replace(qa, metadata={**qa.metadata, "project_id": "project-eight"})
    tb = replace(ta, project_id="project-eight")
    other = seal_source_closed_run(
        (qb,), project_id="project-eight", traces_by_quantity_id={qb.quantity_id: tb},
    )
    with pytest.raises(ValueError, match="different projects"):
        compare_signed_v1_physical_runs(old, other)


def test_public_original_lot16_eight_receipts_survive_byte_identical_comparison():
    root = Path(__file__).resolve().parents[1]
    signed = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json"
    result = build_signed_v1_physical_drift_report(
        baseline_path=signed, candidate_path=signed,
    )
    assert result["baseline_quantity_count"] == 8
    assert result["candidate_quantity_count"] == 8
    assert len(result["unchanged_quantity_ids"]) == 8
    assert result["comparison_status"] == "BYTE_IDENTICAL_SIGNED_RECEIPTS"
    assert result["source_authenticated"] is False


def test_read_only_cli_writes_exclusive_unpublished_diagnostic(tmp_path):
    qa, ta = _pair()
    old = _run((qa, ta))
    new = _run((replace(qa, value=99.0), ta))
    paths = _files(tmp_path, old, new)
    originals = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    output = tmp_path / "diagnostic.json"
    argv = ["--baseline-sealed", str(paths[0]), "--candidate-sealed", str(paths[1]),
            "--output", str(output)]
    assert main(argv) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["official_v2_accuracy"] is None
    assert "value" in report["physical_semantic_conflicts"][0]["changed_fields"]
    assert originals == [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    with pytest.raises(FileExistsError, match="new path"):
        main(argv)
    for protected in paths:
        argv[-1] = str(protected)
        with pytest.raises(ValueError, match="protected evidence"):
            main(argv)


def test_malformed_signed_replay_cannot_be_drift_laundered(tmp_path):
    qa, ta = _pair()
    old = _run((qa, ta))
    new = _run((qa, ta))
    paths = _files(tmp_path, old, new)
    forged = json.loads(paths[1].read_text(encoding="utf-8"))
    forged["quantities"][0]["value"] = 999.0
    paths[1].write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError), match="fingerprint"):
        build_signed_v1_physical_drift_report(
            baseline_path=paths[0], candidate_path=paths[1],
        )
