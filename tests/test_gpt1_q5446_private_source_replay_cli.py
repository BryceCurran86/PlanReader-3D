"""Owner-private Q5446 architect schedule replay CLI does not leak source PDFs."""
from __future__ import annotations

import json
import os

import pytest

from tools.run_gpt1_q5446_original_scheduled_area import main


def test_missing_original_does_not_issue_receipt_or_output(tmp_path, capsys):
    output = tmp_path / "unsealed.json"
    result = main([
        "--source-pdf", str(tmp_path / "no-original.pdf"),
        "--workspace-id", "1",
        "--output", str(output),
    ])
    assert result == 2
    assert not output.exists()
    assert "ABSTAIN" in capsys.readouterr().err


def test_invalid_workspace_does_not_write_source_handoff(tmp_path):
    original_fake = tmp_path / "tampered.pdf"
    original_fake.write_bytes(b"not the original PDF")
    assert main([
        "--source-pdf", str(original_fake),
        "--workspace-id", "0",
        "--output", str(tmp_path / "not-written.json"),
    ]) == 2
    assert not (tmp_path / "not-written.json").exists()


def test_original_positive_cli_private_receipt_is_not_customer_or_benchmark(tmp_path):
    original = os.environ.get("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not original:
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: cannot certify source replay")
    dest = tmp_path / "q5446_architecture_source_sealed_run.json"
    assert main([
        "--source-pdf", original,
        "--workspace-id", "12",
        "--output", str(dest),
    ]) == 0
    data = json.loads(dest.read_text("utf-8"))
    assert data["project_id"] == "au_qld_q5446_armstrong32_harlequin"
    assert len(data["quantities"]) == 5
    assert all(row["lineage_ok"] for row in data["quantities"])
    assert all(row["family"] == "architectural_scheduled_area"
               for row in data["quantities"])
    assert not any(row["value"] in (245.71, 298.19)
                   for row in data["quantities"])
    assert "fingerprint" in data
    # Never overwrite an independently pinned original replay.
    assert main([
        "--source-pdf", original,
        "--workspace-id", "12",
        "--output", str(dest),
    ]) == 2
