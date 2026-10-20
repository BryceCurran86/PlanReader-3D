"""Two original identity activation files must publish atomically, create-only."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from tools.gpt3_atomic_pending_activation_pair import (
    FROZEN_ROOT,
    preflight_new_activation_pair,
    source_input_snapshot,
    publish_new_activation_pair,
)
import tools.prepare_gpt3_pending_identity_activation as opening
import tools.prepare_gpt3_pending_floor_surface_identity_activation as floor
from tests.test_gpt3_pending_floor_surface_identity_activation import (
    _inputs as floor_inputs,
)
from tests.test_gpt3_pending_identity_activation import (
    _json as original_lot16,
    _manifest as lot16_manifest,
    _empty_map as lot16_empty_map,
    _pending as lot16_pending,
    SOURCE_IDENTITY_PROOF,
    OBJECT_UNIVERSE,
)


def _inputs(tmp_path):
    files = tuple(tmp_path / f"immutable-{i}.json" for i in range(7))
    for i, path in enumerate(files):
        path.write_text(json.dumps({"source_owned": i}), encoding="utf-8")
    return files


def _outputs(tmp_path):
    return (tmp_path / "activated-map.json", tmp_path / "activated-receipt.json")


def _publish(inputs, outputs):
    before = source_input_snapshot(inputs)
    first = {"schema_version": "1.0.0", "bindings": [{"original": True}]}
    second = {"source_authority": "verified", "benchmark_score_granted": False}
    publish_new_activation_pair(
        outputs, (first, second), inputs=inputs, source_snapshot=before,
    )
    return first, second


def test_two_outputs_publish_exclusively_with_original_input_byte_preservation(tmp_path):
    inputs = _inputs(tmp_path)
    original = tuple(p.read_bytes() for p in inputs)
    targets = _outputs(tmp_path)
    first, second = _publish(inputs, targets)
    assert [json.loads(p.read_text()) for p in targets] == [first, second]
    assert tuple(p.read_bytes() for p in inputs) == original
    with pytest.raises(FileExistsError, match="never overwrite"):
        _publish(inputs, targets)
    assert [json.loads(p.read_text()) for p in targets] == [first, second]


@pytest.mark.parametrize("position", [0, 1])
def test_activation_output_cannot_alias_any_original_source_or_customer(tmp_path,position):
    inputs = _inputs(tmp_path)
    targets = list(_outputs(tmp_path))
    targets[position] = inputs[2]
    before = inputs[2].read_bytes()
    with pytest.raises(FileExistsError):
        preflight_new_activation_pair(tuple(targets), inputs=inputs)
    assert inputs[2].read_bytes() == before


def test_dangling_output_symlink_and_same_target_alias_are_refused(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    with pytest.raises(ValueError, match="independent"):
        preflight_new_activation_pair((outputs[0], outputs[0]), inputs=inputs)
    outputs[0].symlink_to(tmp_path / "missing-other.json")
    with pytest.raises(FileExistsError, match="never overwrite"):
        preflight_new_activation_pair(outputs, inputs=inputs)


def test_frozen_evaluator_and_manifest_cannot_be_activation_destinations(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    blocked = FROZEN_ROOT / "projects" / "must-not-be-created.json"
    assert not blocked.is_file()
    with pytest.raises(ValueError, match="frozen benchmark"):
        preflight_new_activation_pair((blocked, outputs[1]), inputs=inputs)
    assert not blocked.exists()


def test_input_byte_drift_during_activation_replay_blocks_both_outputs(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    before = source_input_snapshot(inputs)
    inputs[0].write_text('{"replaced":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="inputs changed"):
        publish_new_activation_pair(
            outputs, ({"map": 1}, {"receipt": 1}),
            inputs=inputs, source_snapshot=before,
        )
    assert not any(p.exists() for p in outputs)


def test_second_output_race_causes_rollback_and_no_temp_files(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    actual_link = os.link
    calls = [0]
    def fail_second(stage, destination, *args, **kwargs):
        calls[0] += 1
        if calls[0] == 2:
            raise FileExistsError("synthetic concurrent writer second output")
        return actual_link(stage, destination, *args, **kwargs)
    monkeypatch.setattr(os, "link", fail_second)
    with pytest.raises(FileExistsError, match="synthetic concurrent writer"):
        _publish(inputs, outputs)
    assert calls[0] == 2
    assert not any(p.exists() for p in outputs)
    assert not list(tmp_path.glob(".gpt3-identity-activation-*.tmp"))


def test_first_output_race_cannot_override_competing_evidence(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    actual_link = os.link
    def make_competing_original(stage, destination, *args, **kwargs):
        target = Path(destination)
        target.write_text('{"competing":true}')
        return actual_link(stage, destination, *args, **kwargs)
    monkeypatch.setattr(os, "link", make_competing_original)
    with pytest.raises(FileExistsError):
        _publish(inputs, outputs)
    assert outputs[0].read_text() == '{"competing":true}'
    assert not outputs[1].exists()


def _write_fixture_files(tmp_path, mapping):
    result = {}
    for name, payload in mapping.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        result[name] = path
    return result


def _cli_args(paths, outputs):
    return [
        "--pending-ledger", str(paths["pending"]),
        "--sealed-run", str(paths["sealed"]),
        "--customer-rows", str(paths["customers"]),
        "--active-identity-map", str(paths["active"]),
        "--source-manifest", str(paths["manifest"]),
        "--source-identity-proof", str(paths["proof"]),
        "--object-universe", str(paths["universe"]),
        "--output-map", str(outputs[0]),
        "--output-receipt", str(outputs[1]),
    ]


def test_actual_lot16_opening_activation_cli_produces_exclusive_pair(tmp_path):
    paths = _write_fixture_files(tmp_path, {
        "pending": lot16_pending(),
        "sealed": original_lot16("source_sealed_run.json"),
        "customers": original_lot16("verified_customer_rows.json"),
        "active": lot16_empty_map(),
        "manifest": lot16_manifest(),
        "proof": json.loads(SOURCE_IDENTITY_PROOF.read_text()),
        "universe": json.loads(OBJECT_UNIVERSE.read_text()),
    })
    outputs = _outputs(tmp_path)
    old = {name: path.read_bytes() for name, path in paths.items()}
    assert opening.main(_cli_args(paths, outputs)) == 0
    assert json.loads(outputs[1].read_text())["activated_count"] == 1
    with pytest.raises(FileExistsError, match="never overwrite"):
        opening.main(_cli_args(paths, outputs))
    assert {name: path.read_bytes() for name, path in paths.items()} == old


def test_real_source_neutral_floor_activation_cli_produces_exclusive_pair(tmp_path):
    signed, rows, pending, active, manifest, universe, proof = floor_inputs()
    paths = _write_fixture_files(tmp_path, {
        "pending": pending, "sealed": signed, "customers": rows,
        "active": active, "manifest": manifest,
        "proof": proof, "universe": universe,
    })
    targets = _outputs(tmp_path)
    assert floor.main(_cli_args(paths, targets)) == 0
    assert json.loads(targets[1].read_text())["activated_count"] == 1
    original_receipt = targets[1].read_bytes()
    with pytest.raises(FileExistsError, match="never overwrite"):
        floor.main(_cli_args(paths, targets))
    assert targets[1].read_bytes() == original_receipt


def test_both_activation_clis_preflight_before_consuming_any_untrusted_source(
    tmp_path, monkeypatch,
):
    forbidden = tmp_path / "existing-target.json"
    forbidden.write_text("preserve original")
    outputs = (forbidden, tmp_path / "new-receipt.json")
    paths = {
        name: tmp_path / f"missing-{name}.json"
        for name in ("pending", "sealed", "customers", "active",
                     "manifest", "proof", "universe")
    }
    for program in (opening, floor):
        with pytest.raises(FileExistsError, match="never overwrite"):
            program.main(_cli_args(paths, outputs))
    assert forbidden.read_text() == "preserve original"
    assert not outputs[1].exists()
