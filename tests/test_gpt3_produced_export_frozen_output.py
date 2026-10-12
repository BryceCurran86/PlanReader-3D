"""A customer produced-items export must never overwrite Full Plan V2 benchmark truth."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import export_gpt3_produced_items as exporter
from test_gpt3_produced_items_original_source import _source_run


def _fake_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "checkout"
    (repo_root / "tools").mkdir(parents=True)
    monkeypatch.setattr(
        exporter, "__file__", str(repo_root / "tools" / "export_gpt3_produced_items.py")
    )
    return repo_root / "benchmarks" / "frozen_holdout" / "full_plan_v2"


def _cli_args(source, seal, output):
    return [
        "--sealed-run", str(seal),
        "--source", str(source),
        "--project-id", "project-a",
        "--output", str(output),
    ]


@pytest.mark.parametrize("relative", [
    "au_qld_maryborough_service_station/source_manifest.json",
    "au_qld_lot16_power/reference_takeoff.json",
    "au_qld_3laurel/object_universe.json",
    "run_exact_project_reconciliation.py",
])
def test_export_cannot_replace_any_frozen_benchmark_file(tmp_path, monkeypatch, relative):
    frozen_root = _fake_repo(tmp_path, monkeypatch)
    target = frozen_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    original = b"unaltered benchmark truth and evaluator"
    target.write_bytes(original)
    source, seal, _, _, _ = _source_run(tmp_path)
    with pytest.raises(ValueError, match="must not overwrite frozen V2 benchmark inputs"):
        exporter.main(_cli_args(source, seal, target))
    assert target.read_bytes() == original


def test_export_does_not_create_new_files_inside_frozen_benchmark(tmp_path, monkeypatch):
    frozen_root = _fake_repo(tmp_path, monkeypatch)
    frozen_root.mkdir(parents=True, exist_ok=True)
    source, seal, _, _, _ = _source_run(tmp_path)
    target = frozen_root / "new-produced-items.json"
    with pytest.raises(ValueError, match="must not overwrite frozen V2 benchmark inputs"):
        exporter.main(_cli_args(source, seal, target))
    assert not target.exists()


def test_output_symlink_alias_to_frozen_manifest_is_denied(tmp_path, monkeypatch):
    frozen_root = _fake_repo(tmp_path, monkeypatch)
    frozen_root.mkdir(parents=True, exist_ok=True)
    original = frozen_root / "reference_takeoff.json"
    original.write_bytes(b"immutable original source truth")
    alias = tmp_path / "output.json"
    try:
        alias.symlink_to(original)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    source, seal, _, _, _ = _source_run(tmp_path)
    with pytest.raises(ValueError, match="must not overwrite frozen V2 benchmark inputs"):
        exporter.main(_cli_args(source, seal, alias))
    assert original.read_bytes() == b"immutable original source truth"
    assert alias.is_symlink()


def test_legitimate_source_owned_output_outside_frozen_root_still_publishes(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    destination = tmp_path / "customer-artifacts" / "produced_items.json"
    assert exporter.main(_cli_args(source, seal, destination)) == 0
    rows = json.loads(destination.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == "qty-room-1"
    assert rows[0]["trade_category"] is None
    assert rows[0]["customer_output_parity_verified"] is False


def test_exported_signed_produced_receipt_can_never_be_overwritten_on_rerun(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    output = tmp_path / "customer" / "produced_items.json"
    args = _cli_args(source, seal, output)
    assert exporter.main(args) == 0
    old = output.read_bytes()
    with pytest.raises(FileExistsError, match="existing produced-items receipt"):
        exporter.main(args)
    assert output.read_bytes() == old
    assert not list(output.parent.glob(".produced_items.json.*.tmp"))


def test_existing_customer_receipt_is_never_replaced_even_by_different_project(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    output = tmp_path / "produced_items.json"
    original = b"previous independently signed customer result"
    output.write_bytes(original)
    with pytest.raises(FileExistsError, match="existing produced-items receipt"):
        exporter.main(_cli_args(source, seal, output))
    assert output.read_bytes() == original


def test_dangling_customer_output_symlink_cannot_be_replaced(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    destination = tmp_path / "produced_items.json"
    missing = tmp_path / "other-customer.json"
    destination.symlink_to(missing)
    with pytest.raises(FileExistsError, match="existing produced-items receipt"):
        exporter.main(_cli_args(source, seal, destination))
    assert destination.is_symlink()
    assert not missing.exists()


def test_unsupported_atomic_create_operation_fails_closed_and_cleans_temporary(
    tmp_path, monkeypatch,
):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    destination = tmp_path / "customer" / "produced_items.json"

    def _no_hardlinks(*args, **kwargs):
        raise OSError("filesystem does not support atomic hard links")

    monkeypatch.setattr(exporter.os, "link", _no_hardlinks)
    with pytest.raises(OSError, match="does not support"):
        exporter.main(_cli_args(source, seal, destination))
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp"))


def test_competing_output_writer_race_cannot_be_overwritten(tmp_path, monkeypatch):
    _fake_repo(tmp_path, monkeypatch)
    source, seal, _, _, _ = _source_run(tmp_path)
    destination = tmp_path / "customer" / "produced_items.json"
    original_link = exporter.os.link
    competitor_receipt = b"other publisher has already claimed this exact output"

    def _race(*args, **kwargs):
        destination.write_bytes(competitor_receipt)
        return original_link(*args, **kwargs)

    monkeypatch.setattr(exporter.os, "link", _race)
    with pytest.raises(FileExistsError):
        exporter.main(_cli_args(source, seal, destination))
    assert destination.read_bytes() == competitor_receipt
    assert not list(destination.parent.glob(".produced_items.json.*.tmp"))
