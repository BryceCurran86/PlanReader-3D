"""GPT3 V1/customer original-producer scope join: positive and fail-closed negatives."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from tools import diag_gpt3_original_scope_v1_consumer as consumer
from tools.diag_gptmax_producer_opening_scope_receipts import (
    producer_opening_scope_receipt_report,
)
from tests.test_live_opening_claim_source_closed_export import _opening_pdf


@pytest.fixture(scope="module")
def original():
    source = _opening_pdf()
    report = producer_opening_scope_receipt_report(source, page_ids=("1",))
    assert report["original_production_receipts"]["quantities"]
    assert report["openings"][0]["host_record"]
    return source, report


def _args(report):
    producer = report["original_production_receipts"]
    return {
        "sealed_payload": producer["sealed_run"],
        "customer_rows": producer["customer_rows"],
        "expected_source_sha256": report["source_sha256"],
        "expected_snapshot_id": report["snapshot_id"],
        "expected_project_id": "original-source-retention",
    }


def test_original_pdf_replay_binds_existing_v1_quantity_and_customer(original):
    source, report = original
    result = consumer.verify_original_scope_to_v1_customer(
        source, page_ids=("1",), **_args(report),
    )
    assert result["status"] == "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED"
    assert result["customer_bijection_verified"]
    assert result["source_owned_quantity_count"] == 1
    assert not result["signed_scope_verified"]
    assert not result["customer_scope_signature_issued"]
    assert not result["benchmark_score_granted"]
    row = result["associations"][0]
    positive = next(x for x in report["openings"] if x["quantity_id"])
    assert row["host_binding_record_id"] == positive["host_record"]["record_id"]
    assert row["decision_scope_id"] == positive["host_record"]["decision_scope_id"]
    assert row["snapshot_id"] == report["snapshot_id"]
    assert row["measurement_record_id"] == positive["quantity_measurement_record_id"]
    assert result["v1_sealed_run_fingerprint"] == _args(report)["sealed_payload"]["fingerprint"]


def test_mutating_original_pdf_or_selected_snapshot_never_uses_exported_scope(original):
    source, report = original
    expected = _args(report)
    with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="PDF SHA"):
        consumer.verify_original_scope_to_v1_customer(
            source + b"\n% mutated", page_ids=("1",), **expected,
        )
    with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="snapshot"):
        consumer.verify_original_scope_to_v1_customer(
            source, page_ids=("1",),
            **{**expected, "expected_snapshot_id": "source_snapshot_foreign"},
        )
    with pytest.raises(TypeError):
        consumer.verify_original_scope_to_v1_customer(
            source, page_ids=("1",), report=report, **expected,
        )


def test_reversed_customer_input_does_not_change_issued_association(original):
    _, report = original
    args = _args(report)
    a = consumer._verified_join(report, **args)
    b = consumer._verified_join(report, **{**args, "customer_rows": list(reversed(args["customer_rows"]))})
    assert a == b


@pytest.mark.parametrize("field,value", [
    ("document_id", "live-source:foreign"),
    ("revision_id", "source_revision_foreign"),
    ("snapshot_id", "source_snapshot_foreign"),
    ("source_sha256", "e" * 64),
    ("page_id", "999"),
    ("viewport_id", "foreign-viewport"),
    ("decision_scope_id", "wall-source:unissued"),
])
def test_foreign_source_scope_or_identity_is_rejected(original, field, value):
    _, report = original
    bad = deepcopy(report)
    next(x for x in bad["openings"] if x["quantity_id"])[field] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("host_field,value", [
    ("record_id", "foreign-host"),
    ("decision_scope_id", "wall-source:another-page"),
    ("snapshot_id", "source_snapshot_drift"),
    ("revision_id", "source_revision_old"),
    ("page_id", "other-page"),
])
def test_mismatched_host_record_cannot_be_spliced_into_old_quantity(original, host_field, value):
    _, report = original
    bad = deepcopy(report)
    next(x for x in bad["openings"] if x["quantity_id"])["host_record"][host_field] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


def test_stale_and_superseded_producer_records_are_not_eligible(original):
    _, report = original
    for marker in ("is_stale", "is_superseded"):
        for invalid in (True, "false", 0, None):
            bad = deepcopy(report)
            next(x for x in bad["openings"] if x["quantity_id"])["host_record"][marker] = invalid
            with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="superseded"):
                consumer._verified_join(bad, **_args(report))


def test_missing_original_quantity_and_duplicated_source_inventory_fail(original):
    _, report = original
    for kind in ("missing", "duplicate", "foreign_measurement", "foreign_physical"):
        bad = deepcopy(report)
        positives = [x for x in bad["openings"] if x["quantity_id"]]
        if kind == "missing":
            bad["original_production_receipts"]["quantities"] = []
        elif kind == "duplicate":
            bad["openings"].append(deepcopy(positives[0]))
        elif kind == "foreign_measurement":
            positives[0]["quantity_measurement_record_id"] = "foreign-measure"
        else:
            positives[0]["physical_opening_id"] = "foreign-physical"
        with pytest.raises(consumer.OriginalSourceScopeConsumerError):
            consumer._verified_join(bad, **_args(report))


def test_old_v1_fingerprints_and_customer_bijection_cannot_be_rewritten(original):
    _, report = original
    args = _args(report)
    old = deepcopy(args["sealed_payload"])
    before = deepcopy(args["customer_rows"])
    # A changed source scope is not part of V1; this diagnostic must not
    # rewrite or reissue V1 fingerprints in order to claim proof.
    result = consumer._verified_join(report, **args)
    assert result["signed_scope_verified"] is False
    assert args["sealed_payload"] == old
    assert args["customer_rows"] == before
    bad = deepcopy(before)
    bad[0]["commercial_projection_fingerprint"] = sha256(b"foreign").hexdigest()
    with pytest.raises(Exception):
        consumer._verified_join(report, **{**args, "customer_rows": bad})
    with pytest.raises(Exception):
        consumer._verified_join(
            report, **{**args, "customer_rows": []},
        )
    altered = deepcopy(old)
    altered["quantities"][0]["value"] += 0.01
    with pytest.raises(Exception):
        consumer._verified_join(report, **{**args, "sealed_payload": altered})


def test_replay_source_flags_are_fail_closed_not_unpublished_proof(original):
    _, report = original
    for key, forged in (
        ("status", "SOURCE_SCOPE_SIGNED"),
        ("signed_scope_verified", True),
        ("all_original_source_host_frame_quantity_seal_customer_receipts_unchanged", False),
    ):
        bad = deepcopy(report)
        bad[key] = forged
        with pytest.raises(consumer.OriginalSourceScopeConsumerError):
            consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("selector_field,value", [
    ("document_id", "foreign-document"),
    ("source_sha256", "b" * 64),
    ("revision_id", "source_revision_foreign"),
    ("snapshot_id", "source_snapshot_foreign"),
    ("page_id", "999"),
    ("decision_scope_id", "wall-source:another"),
    ("opening_identity_id", "foreign-physical-id"),
])
def test_producer_frame_selector_cannot_borrow_foreign_source_scope(
    original, selector_field, value,
):
    _, report = original
    bad = deepcopy(report)
    positive = next(row for row in bad["openings"] if row["quantity_id"])
    assert positive["frame_record"] is not None
    positive["frame_record"]["selector"][selector_field] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError,
                       match="superseded or conflicting"):
        consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("key,value", [
    ("opening_identity_id", "foreign-physical"),
    ("host_binding_record_id", "replaced-host"),
    ("host_wall_id", "replaced-wall"),
    ("record_id", ""),
])
def test_producer_frame_body_cannot_be_reissued_against_old_seal(original, key, value):
    _, report = original
    bad = deepcopy(report)
    positive = next(row for row in bad["openings"] if row["quantity_id"])
    assert positive["frame_record"] is not None
    positive["frame_record"][key] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


def test_diagnostic_cli_refuses_to_replace_original_inputs_or_frozen_paths(
    original, tmp_path, monkeypatch,
):
    source, report = original
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    source_path = tmp_path / "original.pdf"
    signed_path = tmp_path / "artifacts" / "signed.json"
    customer_path = tmp_path / "artifacts" / "customer.json"
    source_path.write_bytes(source)
    import json
    signed_path.write_text(json.dumps(_args(report)["sealed_payload"]))
    customer_path.write_text(json.dumps(_args(report)["customer_rows"]))
    before = (source_path.read_bytes(), signed_path.read_bytes(),
              customer_path.read_bytes())
    monkeypatch.setattr(
        consumer, "verify_original_scope_to_v1_customer",
        lambda *args, **kwargs: {"status": "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED", "source_owned_quantity_count": 1},
    )
    base = [
        "--pdf", str(source_path), "--page-id", "1",
        "--sealed-run", str(signed_path),
        "--customer-rows", str(customer_path),
        "--expected-source-sha256", report["source_sha256"],
        "--expected-snapshot-id", report["snapshot_id"],
        "--project-id", "original-source-retention",
    ]
    for destination, error in (
        (str(source_path), ValueError),
        (str(signed_path), FileExistsError),
        (str(customer_path), FileExistsError),
        (str(tmp_path / "benchmarks" / "frozen_holdout" / "gold.json"), ValueError),
    ):
        with pytest.raises(error):
            consumer.main(base + ["--output", destination])
        assert (source_path.read_bytes(), signed_path.read_bytes(),
                customer_path.read_bytes()) == before
    output = tmp_path / "artifacts" / "new-report.json"
    assert consumer.main(base + ["--output", str(output)]) == 0
    assert json.loads(output.read_text())["status"] == (
        "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED"
    )
    with pytest.raises(FileExistsError):
        consumer.main(base + ["--output", str(output)])
    assert (source_path.read_bytes(), signed_path.read_bytes(),
            customer_path.read_bytes()) == before


def test_synthetic_source_inventory_with_nondict_record_fails_closed(original):
    _, report = original
    bad = deepcopy(report)
    bad["original_production_receipts"]["quantities"].append("not-a-source-record")
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


def test_duplicate_unmeasured_physical_source_identity_never_disappears_from_audit(original):
    _, report = original
    bad = deepcopy(report)
    unmeasured_duplicate = deepcopy(bad["openings"][0])
    unmeasured_duplicate["quantity_id"] = None
    bad["openings"].append(unmeasured_duplicate)
    with pytest.raises(consumer.OriginalSourceScopeConsumerError,
                       match="reused original source identity"):
        consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("untrusted_rows", [
    "a string is not an original producer inventory",
    {"quantity_id": "this is not a list"},
])
def test_imported_producer_quantity_inventory_requires_an_array(original, untrusted_rows):
    _, report = original
    bad = deepcopy(report)
    bad["original_production_receipts"]["quantities"] = untrusted_rows
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("changed_input", ["pdf", "sealed", "customer"])
def test_diagnostic_cli_refuses_to_publish_when_input_changes_during_original_replay(
    original, tmp_path, monkeypatch, changed_input,
):
    import json
    source, report = original
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    paths = {
        "pdf": tmp_path / "original.pdf",
        "sealed": tmp_path / "sealed.json",
        "customer": tmp_path / "customer.json",
    }
    paths["pdf"].write_bytes(source)
    paths["sealed"].write_text(json.dumps(_args(report)["sealed_payload"]))
    paths["customer"].write_text(json.dumps(_args(report)["customer_rows"]))
    target = paths[changed_input]
    old = target.read_bytes()
    def mutate_original_input(*args, **kwargs):
        target.write_bytes(old + b" ")
        return {
            "status": "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED",
            "source_owned_quantity_count": 1,
        }
    monkeypatch.setattr(
        consumer, "verify_original_scope_to_v1_customer",
        mutate_original_input,
    )
    out = tmp_path / "artifacts" / "must-not-be-created.json"
    argv = [
        "--pdf", str(paths["pdf"]), "--page-id", "1",
        "--sealed-run", str(paths["sealed"]),
        "--customer-rows", str(paths["customer"]),
        "--expected-source-sha256", report["source_sha256"],
        "--expected-snapshot-id", report["snapshot_id"],
        "--project-id", "original-source-retention",
        "--output", str(out),
    ]
    with pytest.raises(consumer.OriginalSourceScopeConsumerError,
                       match="changed during replay"):
        consumer.main(argv)
    assert not out.exists()


def test_forbidden_diagnostic_destination_is_rejected_before_replay(
    original, tmp_path, monkeypatch,
):
    import json
    source, report = original
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    pdf = tmp_path / "original.pdf"
    sealed = tmp_path / "sealed.json"
    customer = tmp_path / "customer.json"
    pdf.write_bytes(source)
    sealed.write_text(json.dumps(_args(report)["sealed_payload"]))
    customer.write_text(json.dumps(_args(report)["customer_rows"]))
    def impossible(*args, **kwargs):
        raise AssertionError("must never invoke original producer for forbidden output")
    monkeypatch.setattr(consumer, "verify_original_scope_to_v1_customer", impossible)
    args = [
        "--pdf", str(pdf), "--page-id", "1",
        "--sealed-run", str(sealed), "--customer-rows", str(customer),
        "--expected-source-sha256", report["source_sha256"],
        "--expected-snapshot-id", report["snapshot_id"],
        "--project-id", "original-source-retention",
    ]
    with pytest.raises(ValueError, match="artifacts workspace"):
        consumer.main(args + [
            "--output", str(tmp_path / "benchmarks/frozen_holdout/forbidden.json")
        ])


def test_original_scope_workflow_triggers_on_local_import_closure():
    """No source/consumer producer import may silently skip this original PDF replay."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/test-gpt3-original-scope-v1-consumer.yml").read_text()
    assert "  pull_request:\n" in workflow
    trigger = workflow.split("  pull_request:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert "    branches: [main]\n" in trigger
    assert "    paths:\n" in trigger
    allowed = {
        line.strip()[2:].strip("'\"")
        for line in trigger.splitlines()
        if line.startswith("      - ")
    }
    entries = (
        "tools/diag_gpt3_original_scope_v1_consumer.py",
        "tools/diag_gptmax_producer_opening_scope_receipts.py",
        "tools/run_gpt3_lot16_original_sealed_score_input.py",
    )
    pending, visited = list(entries), set()
    while pending:
        rel = pending.pop()
        if rel in visited:
            continue
        visited.add(rel)
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules = [node.module] if node.module else []
            else:
                continue
            for name in modules:
                if name.startswith(("tools.", "scripts.")):
                    candidate = name.replace(".", "/") + ".py"
                    if (root / candidate).is_file() and candidate not in visited:
                        pending.append(candidate)
    # These original-source entry points can also be called by the replayed
    # producer's pb_* composition chain; missing them must not skip a check.
    required = visited | {
        "tools/run_source_closed_project_handoff.py",
        "tools/diag_gptmax_source_authority_stages.py",
        "tools/diag_gptmax_raster_unhosted_flank_source.py",
    }
    assert required <= allowed, (
        "original V1 scope replay has uncovered local producer imports: "
        + repr(sorted(required - allowed))
    )
    assert "pb_*.py" in allowed  # all root-level production authority modules
