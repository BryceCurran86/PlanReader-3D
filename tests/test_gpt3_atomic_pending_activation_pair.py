"""Two original identity activation files must publish atomically, create-only."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tools.gpt3_atomic_pending_activation_pair import (
    FROZEN_ROOT,
    preflight_new_activation_pair,
    source_input_snapshot,
    publish_new_activation_pair,
    read_committed_active_identity_map,
    ACTIVATION_COMMIT_MARKER_VERSION,
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
    committed_receipt = json.loads(outputs[1].read_text(encoding="utf-8"))
    assert committed_receipt["source_authority"] == second["source_authority"]
    return first, committed_receipt


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
    try:
        outputs[0].symlink_to(tmp_path / "missing-other.json")
    except OSError as exc:  # Windows without the symlink privilege
        pytest.skip(f"symlink creation is not permitted on this host: {exc}")
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


def test_receipt_marker_binds_exact_map_bytes_and_source_envelope(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    _publish(inputs, outputs)
    map_bytes = outputs[0].read_bytes()
    map_payload = read_committed_active_identity_map(
        outputs[0], receipt_path=outputs[1],
    )
    assert map_payload == json.loads(map_bytes)
    receipt = json.loads(outputs[1].read_text())
    assert receipt["activation_commit_marker_version"] == ACTIVATION_COMMIT_MARKER_VERSION
    assert receipt["identity_map_sha256"] == __import__("hashlib").sha256(map_bytes).hexdigest()
    assert receipt["benchmark_score_granted"] is False


def test_nonempty_uncommitted_map_never_enters_active_scoring(tmp_path):
    active = tmp_path / "uncommitted-map.json"
    active.write_text(json.dumps({
        "schema_version": "1.0.0", "project_id": "project-1",
        "source_sha256s": ["a" * 64],
        "bindings": [{"benchmark_item_id": "untrusted"}],
    }))
    with pytest.raises(ValueError, match="requires its committed activation receipt"):
        read_committed_active_identity_map(active)
    empty = tmp_path / "empty-baseline.json"
    empty.write_text(json.dumps({
        "schema_version": "1.0.0", "project_id": "project-1",
        "source_sha256s": ["a" * 64], "bindings": [],
    }))
    assert read_committed_active_identity_map(empty)["bindings"] == []


def test_missing_or_mismatched_receipt_is_not_committed(tmp_path):
    inputs = _inputs(tmp_path)
    targets = _outputs(tmp_path)
    _publish(inputs, targets)
    original_map = targets[0].read_bytes()
    original_receipt = targets[1].read_bytes()
    targets[1].unlink()
    with pytest.raises(FileNotFoundError):
        read_committed_active_identity_map(targets[0], receipt_path=targets[1])
    targets[1].write_bytes(original_receipt)
    changed = json.loads(original_map)
    changed["bindings"].append({"other": True})
    targets[0].write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="receipt digest"):
        read_committed_active_identity_map(targets[0], receipt_path=targets[1])
    targets[0].write_bytes(original_map)
    receipt = json.loads(original_receipt)
    receipt["identity_map_project_id"] = "wrong-source-project"
    targets[1].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="source envelope differs"):
        read_committed_active_identity_map(targets[0], receipt_path=targets[1])


def test_reader_cannot_observe_activation_mid_two_link_publish(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    original_link = os.link
    seen = []

    def inspect_first_link(stage, target, *args, **kwargs):
        original_link(stage, target, *args, **kwargs)
        if Path(target) == outputs[0]:
            with pytest.raises(FileNotFoundError):
                read_committed_active_identity_map(
                    outputs[0], receipt_path=outputs[1],
                )
            seen.append("not committed")

    monkeypatch.setattr(os, "link", inspect_first_link)
    _publish(inputs, outputs)
    assert seen == ["not committed"]
    assert read_committed_active_identity_map(
        outputs[0], receipt_path=outputs[1],
    )["bindings"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGKILL crash replay")
def test_sigkill_after_map_link_leaves_inert_orphan(tmp_path):
    inputs = _inputs(tmp_path)
    outputs = _outputs(tmp_path)
    script = """
import os, signal, sys
from pathlib import Path
from tools.gpt3_atomic_pending_activation_pair import (
    publish_new_activation_pair, source_input_snapshot,
)
source, dest_map, dest_receipt = [Path(x) for x in sys.argv[1:]]
link = os.link
def terminate_after_first_link(staged, output, *args, **kwargs):
    link(staged, output, *args, **kwargs)
    os.kill(os.getpid(), signal.SIGKILL)
os.link = terminate_after_first_link
publish_new_activation_pair(
    (dest_map, dest_receipt),
    ({"schema_version": "1.0.0", "bindings": [{"test": True}]},
     {"benchmark_score_granted": False}),
    inputs=(source,), source_snapshot=source_input_snapshot((source,)),
)
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, str(inputs[0]),
         str(outputs[0]), str(outputs[1])],
        cwd=Path(__file__).resolve().parents[1], check=False,
    )
    assert proc.returncode == -signal.SIGKILL
    assert outputs[0].is_file() and not outputs[1].exists()
    with pytest.raises(FileNotFoundError):
        read_committed_active_identity_map(
            outputs[0], receipt_path=outputs[1],
        )
    with pytest.raises(ValueError, match="requires its committed activation receipt"):
        read_committed_active_identity_map(outputs[0])
    with pytest.raises(FileExistsError, match="never overwrite"):
        _publish(inputs, outputs)



@pytest.mark.parametrize("program", [opening, floor])
def test_cli_rejects_orphaned_nonempty_active_map_before_publish(tmp_path, program):
    signed, rows, pending, _, manifest, universe, proof = floor_inputs()
    if program is opening:
        mapping = {
            "pending": lot16_pending(),
            "sealed": original_lot16("source_sealed_run.json"),
            "customers": original_lot16("verified_customer_rows.json"),
            "active": original_lot16("identity_map.json"),
            "manifest": lot16_manifest(),
            "proof": json.loads(SOURCE_IDENTITY_PROOF.read_text()),
            "universe": json.loads(OBJECT_UNIVERSE.read_text()),
        }
    else:
        mapping = {
            "pending": pending, "sealed": signed, "customers": rows,
            "active": {"schema_version": "1.0.0", "project_id": "project-1",
                       "source_sha256s": ["a" * 64],
                       "bindings": [{
                           "benchmark_item_id": "independent-floor",
                           "production_family": "floor_area",
                           "production_object_identity_refs": ["floor-1"],
                       }]},
            "manifest": manifest, "proof": proof, "universe": universe,
        }
    files = _write_fixture_files(tmp_path, mapping)
    outputs = _outputs(tmp_path)
    with pytest.raises(
        ValueError, match="requires its committed activation receipt",
    ):
        program.main(_cli_args(files, outputs))
    assert not any(p.exists() for p in outputs)


def test_committed_prior_partial_map_is_verified_before_next_activation(tmp_path):
    archived = original_lot16("identity_map.json")
    prior = {
        **archived,
        "bindings": [
            row for row in archived["bindings"]
            if row["benchmark_item_id"] !=
            "lot16-1218-sgw-01-area"
        ],
    }
    files = _write_fixture_files(tmp_path, {
        "pending": lot16_pending(),
        "sealed": original_lot16("source_sealed_run.json"),
        "customers": original_lot16("verified_customer_rows.json"),
        "manifest": lot16_manifest(),
        "proof": json.loads(SOURCE_IDENTITY_PROOF.read_text()),
        "universe": json.loads(OBJECT_UNIVERSE.read_text()),
    })
    active_map = tmp_path / "previous-map.json"
    previous_receipt = tmp_path / "previous-receipt.json"
    publish_new_activation_pair(
        (active_map, previous_receipt),
        (prior, {"benchmark_score_granted": False}),
        inputs=(files["sealed"],),
        source_snapshot=source_input_snapshot((files["sealed"],)),
    )
    files["active"] = active_map
    outputs = _outputs(tmp_path)
    args = _cli_args(files, outputs) + [
        "--active-identity-receipt", str(previous_receipt),
    ]
    assert opening.main(args) == 0
    assert len(json.loads(outputs[0].read_text())["bindings"]) == 7
    assert json.loads(outputs[1].read_text())["activated_count"] == 1




def test_duplicate_json_identity_keys_fail_even_with_matching_byte_digest(tmp_path):
    inputs = _inputs(tmp_path)
    targets = _outputs(tmp_path)
    _publish(inputs, targets)
    # The receipt digest can be recomputed for malicious duplicated fields;
    # byte stability alone is not canonical identity authority.
    original = json.loads(targets[0].read_text())
    fields = [
        '"schema_version":"1.0.0"',
        '"project_id":"project-original"',
        '"project_id":"project-forged"',
        '"source_sha256s":[]',
        '"bindings":' + json.dumps(original["bindings"]),
    ]
    forged = ("{" + ",".join(fields) + "}").encode()
    receipt = json.loads(targets[1].read_text())
    receipt["identity_map_sha256"] = __import__("hashlib").sha256(forged).hexdigest()
    receipt["identity_map_project_id"] = "project-forged"
    receipt["identity_map_source_sha256s"] = []
    targets[0].write_bytes(forged)
    targets[1].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="duplicate JSON key"):
        read_committed_active_identity_map(
            targets[0], receipt_path=targets[1],
        )


def test_duplicate_receipt_marker_field_fails_closed(tmp_path):
    inputs = _inputs(tmp_path)
    targets = _outputs(tmp_path)
    _publish(inputs, targets)
    original = json.loads(targets[1].read_text())
    marker = original["identity_map_sha256"]
    # Last-key-wins readers could use the valid second fingerprint while
    # another reader uses the forged first claim.
    original.pop("identity_map_sha256")
    raw = json.dumps(original)[:-1] + (
        ',"identity_map_sha256":"bad","identity_map_sha256":'
        + json.dumps(marker) + "}"
    )
    targets[1].write_text(raw)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        read_committed_active_identity_map(
            targets[0], receipt_path=targets[1],
        )
