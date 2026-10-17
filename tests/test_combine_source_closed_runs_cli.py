from __future__ import annotations

import inspect
import json

import pytest

import pb_combine_source_closed_runs as cli
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    seal_source_closed_run,
)
from tests.symlink_test_support import symlink_or_skip


SHA_A = "a" * 64
SHA_B = "b" * 64


def quantity(quantity_id: str, entity_id: str, source_sha: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="room_area",
        semantic_key=f"room_area:{entity_id}",
        value=10.0,
        unit="m2",
        input_entity_ids=(entity_id,),
        formula="source_closed",
        formula_version="1",
        evidence_ids=(f"ev-{entity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        metadata={
            "project_id": "project-a",
            "document_id": f"doc-{entity_id}",
            "source_sha256": source_sha,
            "revision_id": f"rev-{entity_id}",
        },
    )


def trace(entity_id: str, source_sha: str) -> CommercialTakeoffSourceTrace:
    return CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id="project-a",
        document_id=f"doc-{entity_id}",
        source_sha256=source_sha,
        source_page="p1",
        viewport_id=f"vp-{entity_id}",
        revision_id=f"rev-{entity_id}",
        current_revision_id=f"rev-{entity_id}",
        evidence_ids=(f"ev-{entity_id}",),
        canonical_entity_ids=(entity_id,),
    )


def test_cli_combines_verified_family_run_files(tmp_path) -> None:
    q1 = quantity("q1", "room-1", SHA_A)
    q2 = quantity("q2", "room-2", SHA_B)
    run1 = seal_source_closed_run(
        [q1],
        project_id="project-a",
        traces_by_quantity_id={"q1": trace("room-1", SHA_A)},
    )
    run2 = seal_source_closed_run(
        [q2],
        project_id="project-a",
        traces_by_quantity_id={"q2": trace("room-2", SHA_B)},
    )
    p1 = tmp_path / "room.json"
    p2 = tmp_path / "opening.json"
    out = tmp_path / "combined.json"
    p1.write_text(run1.to_json(), encoding="utf-8")
    p2.write_text(run2.to_json(), encoding="utf-8")

    assert cli.main([
        "--project-id", "project-a",
        "--input", str(p1),
        "--input", str(p2),
        "--output", str(out),
    ]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["project_id"] == "project-a"
    assert [row["quantity_id"] for row in payload["quantities"]] == ["q1", "q2"]
    assert payload["source_sha256s"] == [SHA_A, SHA_B]
    loaded = cli.load_verified_sealed_run(out)
    assert loaded.fingerprint == payload["fingerprint"]


def test_cli_rejects_tampered_input_before_composition(tmp_path) -> None:
    q = quantity("q1", "room-1", SHA_A)
    run = seal_source_closed_run(
        [q],
        project_id="project-a",
        traces_by_quantity_id={"q1": trace("room-1", SHA_A)},
    )
    payload = json.loads(run.to_json())
    payload["quantities"][0]["value"] = 999.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SourceClosedRunConflictError, match="fingerprint mismatch"):
        cli.combine_sealed_run_files([path], project_id="project-a")


def test_cli_has_no_benchmark_truth_or_scoring_dependency() -> None:
    source = inspect.getsource(cli)
    for forbidden in (
        "reference_takeoff",
        "object_universe",
        "expected_quantity",
        "tolerance_fraction",
        "evaluate_project_v2",
    ):
        assert forbidden not in source



def test_cli_composition_is_independent_of_family_file_order(tmp_path) -> None:
    q1 = quantity("q1", "room-1", SHA_A)
    q2 = quantity("q2", "room-2", SHA_B)
    run1 = seal_source_closed_run(
        [q1],
        project_id="project-a",
        traces_by_quantity_id={"q1": trace("room-1", SHA_A)},
    )
    run2 = seal_source_closed_run(
        [q2],
        project_id="project-a",
        traces_by_quantity_id={"q2": trace("room-2", SHA_B)},
    )
    p1 = tmp_path / "first.json"
    p2 = tmp_path / "second.json"
    p1.write_text(run1.to_json(), encoding="utf-8")
    p2.write_text(run2.to_json(), encoding="utf-8")

    forward = cli.combine_sealed_run_files(
        [p1, p2],
        project_id="project-a",
    )
    reverse = cli.combine_sealed_run_files(
        [p2, p1],
        project_id="project-a",
    )

    assert forward.run_id == reverse.run_id
    assert forward.fingerprint == reverse.fingerprint
    assert [row.quantity_id for row in forward.quantities] == ["q1", "q2"]


def _one_source_for_cli(tmp_path):
    q = quantity("q-one", "room-one", SHA_A)
    run = seal_source_closed_run(
        [q], project_id="project-a",
        traces_by_quantity_id={"q-one": trace("room-one", SHA_A)},
    )
    source = tmp_path / "verified-source.sealed.json"
    source.write_text(run.to_json(), encoding="utf-8")
    return source


def _combine_args(source, output):
    return [
        "--project-id", "project-a",
        "--input", str(source), "--output", str(output),
    ]


def test_signed_combined_customer_run_is_immutable_on_repeat_cli(tmp_path):
    source = _one_source_for_cli(tmp_path)
    output = tmp_path / "combined.json"
    assert cli.main(_combine_args(source, output)) == 0
    prior = output.read_bytes()
    with pytest.raises(FileExistsError, match="existing signed combined customer run"):
        cli.main(_combine_args(source, output))
    assert output.read_bytes() == prior
    assert not list(tmp_path.glob(".combined.json.*.tmp"))


def test_signed_combiner_cannot_replace_foreign_earlier_customer_run(tmp_path):
    source = _one_source_for_cli(tmp_path)
    output = tmp_path / "combined.json"
    old = b"earlier original signed customer result must be immutable"
    output.write_bytes(old)
    with pytest.raises(FileExistsError, match="existing signed combined customer run"):
        cli.main(_combine_args(source, output))
    assert output.read_bytes() == old


def test_combiner_cannot_replace_dangling_signed_output_symlink(tmp_path):
    source = _one_source_for_cli(tmp_path)
    output = tmp_path / "combined.json"
    missing = tmp_path / "missing-earlier-receipt.json"
    symlink_or_skip(output, missing)
    with pytest.raises(FileExistsError, match="existing signed combined customer run"):
        cli.main(_combine_args(source, output))
    assert output.is_symlink()
    assert not missing.exists()


@pytest.mark.parametrize("relative", [
    "projects/au_qld_maryborough_service_station/source_manifest.json",
    "projects/au_qld_lot16_power/reference_takeoff.json",
    "run_exact_project_reconciliation.py",
    "new-produced-source-combined.json",
])
def test_combiner_cannot_write_to_frozen_v2_root(tmp_path, monkeypatch, relative):
    repo = tmp_path / "fake-checkout"
    repo.mkdir()
    frozen = repo / "benchmarks" / "frozen_holdout" / "full_plan_v2"
    target = frozen / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    prior = b"frozen benchmark gold and evaluator immutable"
    if not relative.startswith("new-"):
        target.write_bytes(prior)
    monkeypatch.setattr(cli, "__file__", str(repo / "pb_combine_source_closed_runs.py"))
    source = _one_source_for_cli(tmp_path)
    with pytest.raises(ValueError, match="must not overwrite frozen V2 benchmark inputs"):
        cli.main(_combine_args(source, target))
    if not relative.startswith("new-"):
        assert target.read_bytes() == prior
    else:
        assert not target.exists()


def test_unsupported_hard_link_does_not_publish_partial_combined_seal(
    tmp_path, monkeypatch,
):
    source = _one_source_for_cli(tmp_path)
    output = tmp_path / "combined.json"
    def _unavailable(*args, **kwargs):
        raise OSError("source filesystem refuses atomic hard link")
    monkeypatch.setattr(cli.os, "link", _unavailable)
    with pytest.raises(OSError, match="refuses atomic"):
        cli.main(_combine_args(source, output))
    assert not output.exists()
    assert not list(tmp_path.glob(".combined.json.*.tmp"))
    assert source.is_file()


def test_simultaneous_combined_publication_cannot_erase_competing_receipt(
    tmp_path, monkeypatch,
):
    source = _one_source_for_cli(tmp_path)
    output = tmp_path / "combined.json"
    prior = b"another source-signed publisher won target"
    true_link = cli.os.link
    def _competing_writer(*args, **kwargs):
        output.write_bytes(prior)
        return true_link(*args, **kwargs)
    monkeypatch.setattr(cli.os, "link", _competing_writer)
    with pytest.raises(FileExistsError):
        cli.main(_combine_args(source, output))
    assert output.read_bytes() == prior
    assert not list(tmp_path.glob(".combined.json.*.tmp"))
