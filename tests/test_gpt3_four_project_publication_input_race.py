"""Full frozen V2 report must not outlive original source/customer input bytes."""
from __future__ import annotations

import json
import os

import pytest

from tools import gpt3_safe_original_report_output as writer
from tools import report_gpt3_four_project_evidence as suite


PROJECT = "au_qld_lot16_power"
ARCH = "1. Construction Plans - Lot 16 Power (REV E).pdf"


def _cli(tmp_path):
    inputs = {key: tmp_path / key for key in (
        "source", "sealed", "identity", "customer",
    )}
    for directory in inputs.values():
        directory.mkdir()
    output = tmp_path / "verified-evidence.json"
    args = [
        "--source-dir", str(inputs["source"]),
        "--sealed-dir", str(inputs["sealed"]),
        "--identity-map-dir", str(inputs["identity"]),
        "--customer-dir", str(inputs["customer"]),
        "--output", str(output),
    ]
    return inputs, output, args


def _unpublished(**_):
    # No independent source producer, identity mapping or frozen score is
    # claimed by this filesystem-race test; it exercises publication only.
    return {
        "publication_status": "UNPUBLISHED",
        "frozen_denominator": 120,
        "coverage_accuracy": None,
        "projects": [
            {"project_id": PROJECT, "publication_status": "UNAVAILABLE"}
        ],
    }


@pytest.mark.parametrize("changed", ["pdf", "customer", "missing_original_appears"])
def test_source_customer_change_during_final_report_link_cannot_publish(
    tmp_path, monkeypatch, changed,
):
    inputs, output, args = _cli(tmp_path)
    pdf = inputs["source"] / PROJECT / ARCH
    pdf.parent.mkdir()
    customer = inputs["customer"] / f"{PROJECT}.customer_rows.json"
    if changed == "pdf":
        pdf.write_bytes(b"source-original-at-start")
        altered = pdf
    elif changed == "customer":
        customer.write_bytes(b'[{"quantity_id":"initial"}]')
        altered = customer
    else:
        altered = pdf
    real_link = os.link
    linked = []

    def mutate_during_publication(staged, destination):
        real_link(staged, destination)
        linked.append(str(destination))
        altered.write_bytes(b"an external writer changed this original input")

    monkeypatch.setattr(suite, "build_four_project_evidence_ledger", _unpublished)
    monkeypatch.setattr(writer.os, "link", mutate_during_publication)
    with pytest.raises(ValueError, match="input changed during report publication"):
        suite.main(args)
    assert len(linked) == 1
    assert not output.exists()
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_external_writer_replacement_is_never_deleted_after_failed_publish(
    tmp_path, monkeypatch,
):
    inputs, output, args = _cli(tmp_path)
    initial = inputs["source"] / PROJECT / ARCH
    initial.parent.mkdir()
    initial.write_bytes(b"genuine-starting-original-byte-evidence")
    external = tmp_path / "independent-new-receipt.json"
    external.write_text('{"other_writer":true}', encoding="utf-8")
    real_link = os.link

    def replace_report_then_change_original(staged, destination):
        real_link(staged, destination)
        os.replace(external, destination)
        initial.write_bytes(b"original changed during scoring publication")

    monkeypatch.setattr(suite, "build_four_project_evidence_ledger", _unpublished)
    monkeypatch.setattr(writer.os, "link", replace_report_then_change_original)
    with pytest.raises(ValueError, match="input changed during report publication"):
        suite.main(args)
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "other_writer": True,
    }
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_stable_missing_input_unpublished_report_retains_null_score(tmp_path, monkeypatch):
    _, output, args = _cli(tmp_path)
    monkeypatch.setattr(suite, "build_four_project_evidence_ledger", _unpublished)
    assert suite.main(args) == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["coverage_accuracy"] is None
    assert report["frozen_denominator"] == 120
    with pytest.raises(FileExistsError):
        suite.main(args)
