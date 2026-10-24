"""Exact original signed/source/customer byte retention DURING create-only export."""
from __future__ import annotations

import json

import pytest

from test_gpt3_produced_items_original_source import (
    _source_run, _original_projected_customer_row,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tools import export_gpt3_produced_items as exporter


@pytest.mark.parametrize("mutated", ["pdf", "signed", "customer"])
def test_no_produced_receipt_if_original_input_changes_inside_output_hardlink(
    mutated, tmp_path, monkeypatch,
):
    source, signed, _, quantity, trace = _source_run(tmp_path)
    customer = tmp_path / "customer.json"
    customer.write_text(
        json.dumps([_original_projected_customer_row(quantity, trace)]),
        encoding="utf-8",
    )
    paths = {"pdf": source, "signed": signed, "customer": customer}
    target = paths[mutated]
    before_others = {
        label: path.read_bytes()
        for label, path in paths.items() if label != mutated
    }
    output = tmp_path / "produced.json"
    real_link = exporter.os.link
    linked = []

    def replace_original_after_link(temporary, destination):
        real_link(temporary, destination)
        linked.append(str(destination))
        target.write_bytes(b"modified-original-input-after-new-output-link")

    monkeypatch.setattr(exporter.os, "link", replace_original_after_link)
    with pytest.raises(
        SourceClosedRunConflictError,
        match="signed source or customer input changed during produced-items publication",
    ):
        exporter.main([
            "--sealed-run", str(signed),
            "--source", str(source),
            "--customer-rows", str(customer),
            "--project-id", "project-a",
            "--output", str(output),
        ])
    assert len(linked) == 1, "mutation must occur AFTER the output hard link"
    assert not output.exists(), "created stale output must be rolled back"
    assert not list(tmp_path.glob(".produced.json.*.tmp"))
    for label, old in before_others.items():
        assert paths[label].read_bytes() == old


def test_valid_source_and_customer_still_write_exactly_one_immutable_receipt(
    tmp_path,
):
    source, signed, _, quantity, trace = _source_run(tmp_path)
    customer = tmp_path / "customer.json"
    customer.write_text(
        json.dumps([_original_projected_customer_row(quantity, trace)]),
        encoding="utf-8",
    )
    output = tmp_path / "produced.json"
    original_bytes = (source.read_bytes(), signed.read_bytes(), customer.read_bytes())
    assert exporter.main([
        "--sealed-run", str(signed),
        "--source", str(source),
        "--customer-rows", str(customer),
        "--project-id", "project-a",
        "--output", str(output),
    ]) == 0
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == quantity.quantity_id
    assert rows[0]["customer_output_parity_verified"] is True
    assert rows[0]["trade_category"] is None
    assert rows[0]["source_sha256"]
    assert (source.read_bytes(), signed.read_bytes(), customer.read_bytes()) == original_bytes
    with pytest.raises(FileExistsError):
        exporter.main([
            "--sealed-run", str(signed),
            "--source", str(source),
            "--customer-rows", str(customer),
            "--project-id", "project-a",
            "--output", str(output),
        ])
