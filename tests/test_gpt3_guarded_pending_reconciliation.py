from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.run_gpt3_guarded_pending_reconciliation as module


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "docs/engineering/lot16_original_identity_reconciliation_20261012"
)
MANIFEST = (
    ROOT
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / "au_qld_lot16_power/source_manifest.json"
)
OBJECT_UNIVERSE = (
    ROOT
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / "au_qld_lot16_power/object_universe.json"
)
SOURCE_IDENTITY_PROOF = EVIDENCE / "source_identity_proof.json"
SOURCE_SHA = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)
ITEM = "lot16-1218-sgw-01-area"
OBJECT_REF = "lot16:opening:p3:1218_sgw:01"
PHYSICAL = "physical_opening_existence_c4d87543028146e1cff0b5e2ca480c55"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _pending():
    return {
        "project_id": "au_qld_lot16_power",
        "source_sha256": SOURCE_SHA,
        "status": "IDENTITY_READY_QUANTITY_UNSEALED",
        "physical_opening_id": PHYSICAL,
        "benchmark_item_id": ITEM,
        "benchmark_object_ref": OBJECT_REF,
    }


def _partial_map():
    active = _json(EVIDENCE / "identity_map.json")
    active["bindings"] = [
        row
        for row in active["bindings"]
        if row["benchmark_item_id"] != ITEM
    ]
    assert len(active["bindings"]) == 6
    return active


def _run(*, pending=None, active=None):
    return module.build_guarded_exact_report(
        pending_ledger=_pending() if pending is None else pending,
        sealed_run_payload=_json(EVIDENCE / "source_sealed_run.json"),
        customer_rows=_json(EVIDENCE / "verified_customer_rows.json"),
        active_identity_map_payload=(
            _partial_map() if active is None else active
        ),
        source_manifest=_json(MANIFEST),
        source_identity_proof=_json(SOURCE_IDENTITY_PROOF),
        object_universe=_json(OBJECT_UNIVERSE),
        manifest_path=MANIFEST,
    )


def test_real_seven_row_evidence_scores_only_after_guarded_activation():
    candidate, activation, report = _run()

    assert activation["activated_count"] == 1
    assert activation["benchmark_score_granted"] is False
    assert activation["benchmark_accuracy"] is None
    assert activation["evaluator_invoked"] is False

    assert len(candidate["bindings"]) == 7
    activated = next(
        row for row in candidate["bindings"]
        if row["benchmark_item_id"] == ITEM
    )
    assert activated["production_object_identity_refs"] == [PHYSICAL]
    assert activated["production_family"] == "opening_area"

    assert report["source_sha_verified"] is True
    assert report["reconciliation_complete"] is True
    assert report["denominator"] == 27
    assert report["matched_within_tolerance"] == 7
    assert report["matched_outside_tolerance"] == 0
    assert report["missed"] == 20
    assert report["partial"] == 0
    assert report["unresolved"] == 0
    assert report["unsupported_extra"] == 0
    assert report["lineage_conflicts"] == 0
    assert report["coverage_accuracy"] == 7 / 27
    assert report["precision_adjusted_accuracy"] == 7 / 27
    assert len(report["produced_items"]) == 7



def test_forged_pending_physical_swap_never_reaches_exact_evaluator(
    monkeypatch,
):
    called = False

    class _Exact:
        @staticmethod
        def build_exact_project_report(**kwargs):
            nonlocal called
            called = True
            raise AssertionError("evaluator must not run")

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Exact)
    pending = {
        **_pending(),
        "physical_opening_id": (
            "physical_opening_existence_91ae06327d4fcc8004a557b116a77820"
        ),
    }
    with pytest.raises(
        ValueError,
        match="does not match frozen source location",
    ):
        _run(pending=pending)
    assert called is False


def test_unsealed_pending_identity_never_reaches_exact_evaluator(monkeypatch):
    called = False

    class _Exact:
        @staticmethod
        def build_exact_project_report(**kwargs):
            nonlocal called
            called = True
            raise AssertionError("evaluator must not run")

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Exact)
    pending = {
        **_pending(),
        "physical_opening_id": "physical_opening_existence_not_sealed",
    }
    with pytest.raises(
        ValueError,
        match="no pre-certified identity is newly sealed",
    ):
        _run(pending=pending)
    assert called is False


def test_duplicate_active_identity_never_reaches_exact_evaluator(monkeypatch):
    called = False

    class _Exact:
        @staticmethod
        def build_exact_project_report(**kwargs):
            nonlocal called
            called = True
            raise AssertionError("evaluator must not run")

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Exact)
    with pytest.raises(ValueError, match="already active"):
        _run(active=_json(EVIDENCE / "identity_map.json"))
    assert called is False


def test_guarded_report_rejects_activation_and_report_run_mismatch(monkeypatch):
    real = module._exact_report_module()

    class _Changed:
        @staticmethod
        def build_exact_project_report(**kwargs):
            report = real.build_exact_project_report(**kwargs)
            return {**report, "sealed_run_id": "different-run"}

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Changed)
    with pytest.raises(ValueError, match="sealed run mismatch"):
        _run()


def test_guarded_report_rejects_activation_and_report_fingerprint_mismatch(
    monkeypatch,
):
    real = module._exact_report_module()

    class _Changed:
        @staticmethod
        def build_exact_project_report(**kwargs):
            report = real.build_exact_project_report(**kwargs)
            return {
                **report,
                "sealed_run_fingerprint": "0" * 64,
            }

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Changed)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        _run()


@pytest.mark.parametrize("payload", [
    '{"project_id":"a","project_id":"b"}',
    '{"inner":{"binding":"one","binding":"two"}}',
    '{"quantity":NaN}',
    '{"quantity":Infinity}',
    '{"quantity":1e9999}',
])
def test_guarded_identity_ingress_rejects_duplicate_keys_and_nonfinite_numbers(tmp_path, payload):
    source = tmp_path / "untrusted.json"
    source.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        module._object(source)


def test_guarded_customer_ingress_rejects_duplicated_provenance_and_non_objects(tmp_path):
    path = tmp_path / "customer.json"
    for body in (
        '[{"quantity_id":"first","quantity_id":"second"}]',
        '[{"notes":{"sealed_id":"a","sealed_id":"b"}}]',
        '[{"quantity_id":"a"}, 12]',
    ):
        path.write_text(body, encoding="utf-8")
        with pytest.raises((ValueError, TypeError)):
            module._rows(path)


def test_guarded_outputs_refuse_aliases_existing_source_and_frozen_truth(tmp_path):
    inputs = (tmp_path / "sealed.json",)
    inputs[0].write_text("signed original stays here", encoding="utf-8")
    good = (tmp_path / "map.json", tmp_path / "activation.json", tmp_path / "exact.json")
    module._preflight_outputs(good, inputs)
    for forbidden in (
        (good[0], good[0], good[2]),
        (inputs[0], good[1], good[2]),
        (MANIFEST, good[1], good[2]),
        (module.FROZEN_ROOT / "illegal.json", good[1], good[2]),
    ):
        with pytest.raises((ValueError, FileExistsError)):
            module._preflight_outputs(forbidden, inputs)
    assert inputs[0].read_text(encoding="utf-8") == "signed original stays here"


def test_guarded_outputs_create_three_verifiable_new_files_and_reject_overwrite(tmp_path):
    inputs = (tmp_path / "source.json",)
    inputs[0].write_text("immutable-source", encoding="utf-8")
    outputs = (tmp_path / "map.json", tmp_path / "receipt.json", tmp_path / "report.json")
    payloads = ({"sealed_id": "real"}, {"activated_count": 1}, {"score": None})
    module._write_triplet(outputs, payloads, inputs=inputs)
    assert [json.loads(p.read_text()) for p in outputs] == list(payloads)
    with pytest.raises(FileExistsError, match="new"):
        module._write_triplet(outputs, payloads, inputs=inputs)
    assert inputs[0].read_text(encoding="utf-8") == "immutable-source"


def test_guarded_outputs_roll_back_all_new_files_on_second_write_collision(tmp_path, monkeypatch):
    inputs = (tmp_path / "original.json",)
    inputs[0].write_text("do not touch this", encoding="utf-8")
    outputs = tuple(tmp_path / name for name in ("map.json", "receipt.json", "exact.json"))
    original_link = module.os.link
    counter = [0]

    def fail_second(temp, target):
        counter[0] += 1
        if counter[0] == 2:
            raise FileExistsError("synthetic competing writer")
        return original_link(temp, target)

    monkeypatch.setattr(module.os, "link", fail_second)
    with pytest.raises(FileExistsError, match="competing"):
        module._write_triplet(
            outputs, ({"a": 1}, {"b": 2}, {"c": 3}), inputs=inputs,
        )
    assert all(not target.exists() for target in outputs)
    assert not list(tmp_path.glob(".gpt3-activation-*.tmp"))
    assert inputs[0].read_text(encoding="utf-8") == "do not touch this"


def test_guarded_output_preflight_does_not_invoke_source_or_evaluator_when_unsafe(
    tmp_path, monkeypatch,
):
    doomed = tmp_path / "existing_output.json"
    doomed.write_text('{"original":true}', encoding="utf-8")
    called = []

    def forbidden(_):
        called.append("input parsed")
        raise AssertionError("source should not be consumed")

    monkeypatch.setattr(module, "_object", forbidden)
    cli = [
        "--pending-ledger", str(tmp_path / "missing_pending.json"),
        "--sealed-run", str(tmp_path / "missing_sealed.json"),
        "--customer-rows", str(tmp_path / "missing_customers.json"),
        "--active-identity-map", str(tmp_path / "missing_map.json"),
        "--manifest", str(MANIFEST),
        "--source-identity-proof", str(tmp_path / "missing_identity.json"),
        "--object-universe", str(OBJECT_UNIVERSE),
        "--output-map", str(doomed),
        "--output-activation-receipt", str(tmp_path / "activation.json"),
        "--output-report", str(tmp_path / "report.json"),
    ]
    with pytest.raises(FileExistsError, match="new"):
        module.main(cli)
    assert called == []
    assert doomed.read_text(encoding="utf-8") == '{"original":true}'
