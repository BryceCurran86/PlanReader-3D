"""Source-neutral Q5446 role dispatch regression; original positives stay private."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_gpt1_q5446_alfresco_original_customer import OriginalQ5446AlfrescoCustomerResult
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import seal_source_closed_run
from pb_combine_source_closed_runs import load_verified_sealed_run
from tests.test_source_closed_project_handoff import _quantity
from tests.test_gpt3_owner_all_source_role_handoff import _fake_sources
from tools import gpt3_owner_all_source_role_handoff as roles
from tools import q5446_source_role_customer_runtime as runtime


def _setup(tmp_path, monkeypatch):
    source_dir = tmp_path / "source-private"
    source_dir.mkdir()
    source = source_dir / "fake.pdf"
    source.write_bytes(b"synthetic original role for regression; not a real Q5446 PDF")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    project = "source-neutral-project"
    document = "source-neutral-document"
    monkeypatch.setattr(runtime, "SOURCE_SHA256", sha)
    monkeypatch.setattr(runtime, "Q5446_PROJECT_ID", project)
    monkeypatch.setattr(runtime, "Q5446_DOCUMENT_ID", document)

    quantity = replace(
        _quantity("synthetic-q5446-floor", "floor_area"),
        input_entity_ids=("source-neutral-physical-floor",),
        metadata={
            "source_sha256": sha,
            "commercial_projection_allowed": True,
            "tiled_floor_finish_authorized": False,
            "net_internal_finished_face_authorized": False,
            "canonical_physical_floor_owner_authenticated": True,
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1, project_id=project, document_id=document,
        source_sha256=sha, source_page="1",
        viewport_id="source-neutral-physical-floor", revision_id="rev",
        current_revision_id="rev", evidence_ids=quantity.evidence_ids,
        canonical_entity_ids=quantity.input_entity_ids,
    )
    sealed = seal_source_closed_run(
        (quantity,), project_id=project,
        traces_by_quantity_id={quantity.quantity_id: trace},
    )
    row = quantity_evidence_to_takeoff_output_row(
        quantity, trace=trace, authority=CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=("synthetic-figured-x", "synthetic-figured-y"),
        ),
    )
    receipt = OriginalQ5446AlfrescoCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW", ("source-neutral-test-only",),
        quantity, trace, sealed, (row,),
    )
    monkeypatch.setattr(runtime, "issue_original_q5446_alfresco_customer_area",
                        lambda *_a, **_kw: receipt)
    return source, sha, project, receipt


def _produce(source, project, tmp_path):
    role = tmp_path / "role"
    role.mkdir()
    return runtime.produce_q5446_source_role(
        pdf_path=source, project_id=project, output_dir=role, workspace_id=1,
    ), role


def test_source_owned_dispatch_requires_exact_hash_and_all_family(monkeypatch):
    sha = "a" * 64
    monkeypatch.setattr(runtime, "SOURCE_SHA256", sha)
    assert runtime.source_owned_role_module(sha, family_group="all") == (
        "tools.q5446_source_role_customer_runtime"
    )
    assert runtime.source_owned_role_module(sha, family_group="floor_area") == (
        "tools.run_source_closed_project_handoff"
    )
    assert runtime.source_owned_role_module("b" * 64, family_group="all") == (
        "tools.run_source_closed_project_handoff"
    )
    with pytest.raises(TypeError):
        runtime.source_owned_role_module(None, family_group="all")


def test_actual_seal_customer_verifier_and_canonical_role_files(tmp_path, monkeypatch):
    source, sha, project, receipt = _setup(tmp_path, monkeypatch)
    result, output = _produce(source, project, tmp_path)
    assert result["status"] == "sealed"
    assert result["customer_rows_verified"] is True
    assert result["full_project_customer_first_gate"] == "PROJECT_VERIFIED"
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None
    assert result["family_counts"] == {"floor_area": 1}
    assert result["verified_customer_row_count"] == 1
    signed = load_verified_sealed_run(output / (project + ".json"))
    rows = json.loads((output / "verified_customer_rows.json").read_text())
    assert len(rows) == len(signed.quantities) == 1
    assert set(signed.source_sha256s) == {sha}
    assert set(verify_sealed_customer_output(
        signed, rows,
    ).verified_quantity_ids) == {receipt.quantity.quantity_id}
    assert json.loads((output / "production_summary.json").read_text()) == result
    assert not list(output.rglob("*.pdf"))


@pytest.mark.parametrize("failure", (
    "wrong_project", "wrong_digest", "non_all", "source_absent",
    "issuer_abstain", "wrong_trace", "bad_quantity_scope", "bad_customer_row",
    "foreign_seal",
))
def test_negative_source_role_never_manufactures_customer_quantity(
    tmp_path, monkeypatch, failure,
):
    source, sha, project, receipt = _setup(tmp_path, monkeypatch)
    kwargs = {}
    if failure == "wrong_project":
        project = "foreign-project"
    elif failure == "wrong_digest":
        source.write_bytes(b"changed original content")
    elif failure == "non_all":
        kwargs["family_group"] = "floor_area"
    elif failure == "source_absent":
        source.unlink()
    elif failure == "issuer_abstain":
        monkeypatch.setattr(
            runtime, "issue_original_q5446_alfresco_customer_area",
            lambda *_a, **_k: OriginalQ5446AlfrescoCustomerResult(
                "ABSTAIN", ("missing_source_primitive",),
            ),
        )
    elif failure == "wrong_trace":
        monkeypatch.setattr(
            runtime, "issue_original_q5446_alfresco_customer_area",
            lambda *_a, **_k: replace(receipt, trace=replace(
                receipt.trace, document_id="borrowed-document",
            )),
        )
    elif failure == "bad_quantity_scope":
        monkeypatch.setattr(
            runtime, "issue_original_q5446_alfresco_customer_area",
            lambda *_a, **_k: replace(receipt, quantity=replace(
                receipt.quantity, metadata={
                    **receipt.quantity.metadata, "tiled_floor_finish_authorized": True,
                },
            )),
        )
    elif failure == "bad_customer_row":
        monkeypatch.setattr(
            runtime, "issue_original_q5446_alfresco_customer_area",
            lambda *_a, **_k: replace(receipt, customer_rows=({
                **receipt.customer_rows[0], "quantity": 99.0,
            },)),
        )
    elif failure == "foreign_seal":
        other = replace(receipt.sealed_run, project_id="wrong-project")
        monkeypatch.setattr(
            runtime, "issue_original_q5446_alfresco_customer_area",
            lambda *_a, **_k: replace(receipt, sealed_run=other),
        )
    role = tmp_path / "role"
    role.mkdir()
    if failure == "source_absent":
        with pytest.raises(FileNotFoundError):
            runtime.produce_q5446_source_role(
                pdf_path=source, project_id=project, output_dir=role, **kwargs,
            )
        return
    result = runtime.produce_q5446_source_role(
        pdf_path=source, project_id=project, output_dir=role, **kwargs,
    )
    assert result["status"] == "no_sealable_quantities"
    assert result["customer_rows_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert not (role / (project + ".json")).exists()
    assert not (role / "verified_customer_rows.json").exists()


def test_role_outputs_cannot_overwrite_or_write_into_sources(tmp_path, monkeypatch):
    source, _sha, project, _receipt = _setup(tmp_path, monkeypatch)
    role = tmp_path / "role"
    role.mkdir()
    (role / "previous.json").write_text("{}")
    with pytest.raises(FileExistsError):
        runtime.produce_q5446_source_role(
            pdf_path=source, project_id=project, output_dir=role,
        )
    with pytest.raises(ValueError, match="inside source"):
        runtime.produce_q5446_source_role(
            pdf_path=source, project_id=project, output_dir=tmp_path,
        )


def test_real_owner_roster_dispatches_only_sha_authenticated_matching_role(
    tmp_path, monkeypatch,
):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    # No real Q5446 source, only synthetic roster entries. This tests dispatch
    # and incomplete role coverage, NOT original-source geometry or accuracy.
    monkeypatch.setattr(runtime, "SOURCE_SHA256", docs[0]["sha256"])
    monkeypatch.setattr(roles, "FROZEN_ROOT", tmp_path / "frozen")
    calls = []

    def produce(command, _repo, _log, **_kw):
        calls.append(command)
        output = Path(command[command.index("--output-dir") + 1])
        (output / "production_summary.json").write_text(json.dumps({
            "status": "no_sealable_quantities",
        }))
        return 0, "COMPLETED", {}

    monkeypatch.setattr(roles, "run_logged", produce)
    out = tmp_path / "owner-output"
    result = roles.produce_all_source_roles(
        project_id=project, source_dir=root, output_dir=out,
    )
    assert len(calls) == 2
    assert calls[0][2] == "tools.q5446_source_role_customer_runtime"
    assert calls[1][2] == "tools.run_source_closed_project_handoff"
    assert result["source_role_coverage_verified"] is False
    assert not (out / "ALL_SOURCE_ROLES.sealed.json").exists()
    assert not (out / "ALL_SOURCE_ROLES.customer_rows.json").exists()
    assert result["benchmark_score_granted"] is False


def test_private_sha_original_single_role_optional(tmp_path):
    private = os.getenv("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not private:
        pytest.skip("private original not in public CI; no source-positive claim")
    from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
    from pb_gpt1_q5446_source_declared_area_firm_handoff import Q5446_PROJECT_ID
    source = Path(private)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256
    role = tmp_path / "real-role"
    role.mkdir()
    result = runtime.produce_q5446_source_role(
        pdf_path=source, project_id=Q5446_PROJECT_ID,
        output_dir=role, workspace_id=14,
    )
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 1
    assert result["benchmark_score_granted"] is False
