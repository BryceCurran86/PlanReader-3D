"""GPT3 real Lot16 source-sealed score-input firewall tests (no frozen gold)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import run_gpt3_lot16_original_sealed_score_input as handoff


def _source(tmp_path):
    pdf = tmp_path / "1. Construction Plans - Lot 16 Power (REV E).pdf"
    pdf.write_bytes(b"%PDF-1.7\nsynthetic evidence for tests")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(json.dumps({
        "project_id": handoff.PROJECT,
        "source_documents": [
            {"name": pdf.name, "role": "architectural_drawings",
             "size_bytes": pdf.stat().st_size, "sha256": sha},
        ],
    }), encoding="utf-8")
    return pdf, sha, manifest


def _signed(sha):
    q = SimpleNamespace(quantity_id="original-opening-quantity-1",
                        family="opening_area")
    return SimpleNamespace(
        project_id=handoff.PROJECT, source_sha256s=(sha,),
        run_id="sealed-source-run-1", fingerprint="fingerprint-sha",
        quantities=(q,), to_dict=lambda: {
            "project_id": handoff.PROJECT, "source_sha256s": [sha],
            "run_id": "sealed-source-run-1", "quantities": [
                {"quantity_id": "original-opening-quantity-1", "family": "opening_area"},
            ], "fingerprint": "fingerprint-sha",
        },
    )


def _verified():
    return SimpleNamespace(
        verified_quantity_ids=("original-opening-quantity-1",),
        valid_quantity_count=1,
    )


def test_real_project_handoff_seals_single_source_claim_and_verifies_customer_once(
    tmp_path, monkeypatch,
):
    pdf, sha, manifest = _source(tmp_path)
    captured = []
    def _inspect_source(pdf_file, page, *, on_original_claim):
        assert pdf_file == pdf
        assert page == 2
        assert callable(on_original_claim)
        # A read-only original-source opening is required by the production
        # witness sidecar; the mock must retain the producer's actual shape.
        opening = SimpleNamespace(to_dict=lambda: {
            "physical_opening_id": "physical-original",
            "canonical_opening_id": "physical-original",
            "source_sha256": sha,
            "host_binding_record_id": "opening_host_binding_v3_original",
        })
        on_original_claim(SimpleNamespace(canonical_openings=(opening,)))
        return {
            "pdf_sha256": sha,
            "opening_sealing_diagnostic": {
                "status": "source_sealed_and_customer_rows_verified",
                "sealed_quantity_ids": ["original-opening-quantity-1"],
            },
        }
    monkeypatch.setattr(handoff, "inspect_source", _inspect_source)
    def _seal(claim, *, workspace_id, project_id):
        assert project_id == handoff.PROJECT
        assert workspace_id == 1
        captured.append("sealed")
        return _signed(sha)
    def _rows(claim, *, workspace_id, project_id):
        assert project_id == handoff.PROJECT
        captured.append("customer")
        return ({"quantity_id": "original-opening-quantity-1"},)
    def _verify(sealed, rows):
        captured.append("verified")
        assert sealed.project_id == handoff.PROJECT
        return _verified()
    monkeypatch.setattr(handoff, "seal_live_opening_area_claim_run", _seal)
    monkeypatch.setattr(handoff, "project_live_opening_customer_rows", _rows)
    monkeypatch.setattr(handoff, "verify_sealed_customer_output", _verify)
    out = tmp_path / "score-inputs"
    receipt = handoff.run_original_lot16_sealed_handoff(
        pdf, out, manifest_path=manifest,
    )
    assert captured == ["sealed", "customer", "verified"]
    assert receipt["quantity_count"] == 1
    assert receipt["benchmark_score_granted"] is False
    assert receipt["benchmark_accuracy"] is None
    assert receipt["identity_map_status"] == "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED"
    assert json.loads((out / "source_sealed_run.json").read_text())["project_id"] == handoff.PROJECT
    assert json.loads((out / "source_production_openings.json").read_text()) == [{
        "physical_opening_id": "physical-original",
        "canonical_opening_id": "physical-original",
        "source_sha256": sha,
        "host_binding_record_id": "opening_host_binding_v3_original",
    }]
    assert json.loads((out / "verified_customer_rows.json").read_text()) == [
        {"quantity_id": "original-opening-quantity-1"},
    ]
    assert json.loads(
        (out / "source_score_readiness_UNPUBLISHED.json").read_text()
    )["frozen_v2_reconciliation_complete"] is False


@pytest.mark.parametrize("tamper", [
    "source_sha", "source_name", "source_bytes", "source_size", "source_project",
])
def test_original_pdf_receipt_does_not_accept_changed_source(tmp_path, tamper):
    pdf, sha, manifest = _source(tmp_path)
    data = json.loads(manifest.read_text())
    if tamper == "source_sha":
        data["source_documents"][0]["sha256"] = "f" * 64
    elif tamper == "source_name":
        data["source_documents"][0]["name"] = "other-project.pdf"
    elif tamper == "source_bytes":
        pdf.write_bytes(b"x" * pdf.stat().st_size)
    elif tamper == "source_size":
        data["source_documents"][0]["size_bytes"] += 1
    else:
        data["project_id"] = "foreign-project"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="source|project"):
        handoff._verify_original_source(pdf, manifest)


@pytest.mark.parametrize("tamper", [
    "foreign_project", "foreign_sha", "missing_seal", "duplicate_quantity",
    "family_mismatch", "customer_mismatch", "extra_customer_rows",
])
def test_unverified_seal_cannot_be_promoted_to_score_input(tmp_path, tamper):
    sha = "a" * 64
    sealed = _signed(sha)
    rows = ({"quantity_id": "original-opening-quantity-1"},)
    verified = _verified()
    if tamper == "foreign_project":
        sealed.project_id = "wrong"
    elif tamper == "foreign_sha":
        sealed.source_sha256s = ("b" * 64,)
    elif tamper == "missing_seal":
        sealed.quantities = ()
    elif tamper == "duplicate_quantity":
        sealed.quantities = sealed.quantities * 2
    elif tamper == "family_mismatch":
        sealed.quantities[0].family = "opening_count"
    elif tamper == "customer_mismatch":
        verified.verified_quantity_ids = ("other-physical-quantity",)
    else:
        rows = rows * 2
    with pytest.raises(ValueError):
        handoff._validate_sealed_customer_handoff(sealed, rows, verified, sha)


def test_existing_signed_output_directory_is_never_reused(tmp_path, monkeypatch):
    pdf, sha, manifest = _source(tmp_path)
    output = tmp_path / "old-customer-evidence"
    output.mkdir()
    previous = output / "source_sealed_run.json"
    previous.write_bytes(b"older authentic source-signed result")
    monkeypatch.setattr(
        handoff, "inspect_source",
        lambda *_args, **_kwargs: pytest.fail("source must not rerun into prior output"),
    )
    with pytest.raises(FileExistsError):
        handoff.run_original_lot16_sealed_handoff(
            pdf, output, manifest_path=manifest,
        )
    assert previous.read_bytes() == b"older authentic source-signed result"


def test_atomic_writer_preserves_competing_source_receipt(tmp_path, monkeypatch):
    path = tmp_path / "sealed_run.json"
    true_link = handoff.os.link
    old = b"another original source publisher already committed this path"
    def _race(source, target):
        path.write_bytes(old)
        return true_link(source, target)
    monkeypatch.setattr(handoff.os, "link", _race)
    with pytest.raises(FileExistsError):
        handoff._publish_new(path, {"new": "proof"})
    assert path.read_bytes() == old
    assert not list(tmp_path.glob(".sealed_run.json.*.tmp"))


def test_atomic_writer_fails_closed_without_hardlinks(tmp_path, monkeypatch):
    path = tmp_path / "sealed_run.json"
    def _unsupported(_source, _target):
        raise OSError("no atomic link support")
    monkeypatch.setattr(handoff.os, "link", _unsupported)
    with pytest.raises(OSError, match="no atomic link support"):
        handoff._publish_new(path, {"source": "authenticated"})
    assert not path.exists()
    assert not list(tmp_path.glob(".sealed_run.json.*.tmp"))
