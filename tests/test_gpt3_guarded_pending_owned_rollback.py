"""Guarded V2 must not delete another writer's signed/identity output on rollback."""
from __future__ import annotations

import json
import os

import pytest

import tools.run_gpt3_guarded_pending_reconciliation as module
from tools.gpt3_atomic_pending_activation_pair import (
    read_committed_active_identity_map,
    ACTIVATION_COMMIT_MARKER_VERSION,
)


def test_second_link_failure_cannot_delete_external_replacement_of_first_output(
    tmp_path, monkeypatch,
):
    source = tmp_path / "source-original.json"
    source.write_text('{"original":true}', encoding="utf-8")
    inputs = (source,)
    outputs = tuple(tmp_path / x for x in ("map.json", "activation.json", "exact.json"))
    before = source.read_bytes()
    external = tmp_path / "outside.json"
    external.write_text('{"owner":"another writer"}', encoding="utf-8")
    original_link = os.link
    calls: list[str] = []

    def replace_first_output_then_fail_second(staged, destination):
        calls.append(str(destination))
        if len(calls) == 2:
            # The first published path belongs to another process now;
            # the old file descriptor/staging inode still exists separately.
            os.replace(external, outputs[0])
            raise FileExistsError("synthetic second output collision")
        return original_link(staged, destination)

    monkeypatch.setattr(module.os, "link", replace_first_output_then_fail_second)
    with pytest.raises(FileExistsError, match="second output collision"):
        module._write_triplet(
            outputs,
            ({"id": "actual"}, {"activated_count": 1}, {"scored": False}),
            inputs=inputs,
        )
    assert len(calls) == 2
    assert json.loads(outputs[0].read_text(encoding="utf-8")) == {
        "owner": "another writer",
    }
    assert not outputs[1].exists()
    assert not outputs[2].exists()
    assert not external.exists(), "the independent writer moved its file"
    assert not list(tmp_path.glob(".gpt3-activation-*.tmp"))
    assert source.read_bytes() == before


def test_three_outputs_rollback_when_source_changes_during_final_link(
    tmp_path, monkeypatch,
):
    source = tmp_path / "original-source.json"
    source.write_text('{"immutable":true}', encoding="utf-8")
    outputs = tuple(tmp_path / x for x in ("map.json", "activation.json", "score.json"))
    expected = module._snapshot_inputs((source,))
    original_link = os.link
    count = 0

    def change_input_after_last_link(staged, destination):
        nonlocal count
        count += 1
        original_link(staged, destination)
        if count == 3:
            source.write_text('{"externally_modified":true}', encoding="utf-8")

    monkeypatch.setattr(module.os, "link", change_input_after_last_link)
    with pytest.raises(ValueError, match="input"):
        module._write_triplet(
            outputs, ({"a": 1}, {"b": 2}, {"c": 3}),
            inputs=(source,), expected_input_hashes=expected,
        )
    assert count == 3
    assert not any(path.exists() for path in outputs)
    assert not list(tmp_path.glob(".gpt3-activation-*.tmp"))
    assert source.read_text(encoding="utf-8") == '{"externally_modified":true}'


def test_positive_three_output_create_only_stays_same(tmp_path):
    source = tmp_path / "signed-original.json"
    source.write_text('{"sealed":true}', encoding="utf-8")
    outputs = tuple(tmp_path / x for x in ("map.json", "receipt.json", "score.json"))
    expected = module._snapshot_inputs((source,))
    payload = ({"map": 1}, {"receipt": 2}, {"score": None})
    module._write_triplet(
        outputs, payload, inputs=(source,), expected_input_hashes=expected,
    )
    values = [json.loads(p.read_text(encoding="utf-8")) for p in outputs]
    assert values[0] == payload[0]
    assert values[2] == payload[2]
    assert values[1]["receipt"] == payload[1]["receipt"]
    assert values[1]["activation_commit_marker_version"] == ACTIVATION_COMMIT_MARKER_VERSION
    assert read_committed_active_identity_map(
        outputs[0], receipt_path=outputs[1],
    ) == payload[0]
    assert module.read_committed_guarded_exact_report(
        outputs[0], outputs[1], outputs[2],
    ) == payload[2]
    with pytest.raises(FileExistsError):
        module._write_triplet(
            outputs, payload, inputs=(source,), expected_input_hashes=expected,
        )


def test_report_without_final_receipt_is_not_committed(tmp_path):
    source = tmp_path / "signed.json"
    source.write_text('{"signed":true}')
    outputs = tuple(tmp_path / name for name in (
        "map.json", "receipt.json", "report.json",
    ))
    module._write_triplet(
        outputs,
        ({"bindings": [{"x": 1}]}, {"activated_count": 1}, {"matched": 1}),
        inputs=(source,),
    )
    assert module.read_committed_guarded_exact_report(
        outputs[0], outputs[1], outputs[2],
    ) == {"matched": 1}
    outputs[1].unlink()
    with pytest.raises(FileNotFoundError):
        module.read_committed_guarded_exact_report(
            outputs[0], outputs[1], outputs[2],
        )


def test_report_tamper_after_commit_never_reaches_guarded_reader(tmp_path):
    source = tmp_path / "signed.json"
    source.write_text('{"signed":true}')
    outputs = tuple(tmp_path / name for name in (
        "map.json", "receipt.json", "report.json",
    ))
    module._write_triplet(
        outputs,
        ({"bindings": [{"x": 1}]},
         {"activated_count": 1}, {"matched": 1}),
        inputs=(source,),
    )
    outputs[2].write_text('{"matched":999}')
    with pytest.raises(ValueError, match="report does not match activation commit digest"):
        module.read_committed_guarded_exact_report(
            outputs[0], outputs[1], outputs[2],
        )


def test_receipt_swap_between_map_and_report_read_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "signed.json"
    source.write_text('{"signed":true}')
    outputs = tuple(tmp_path / name for name in (
        "map.json", "receipt.json", "report.json",
    ))
    module._write_triplet(
        outputs,
        ({"bindings": [{"x": 1}]}, {"activated_count": 1}, {"matched": 1}),
        inputs=(source,),
    )
    actual_reader = module.read_committed_active_identity_map

    def replace_receipt_after_first_verification(*args, **kwargs):
        result = actual_reader(*args, **kwargs)
        marker = json.loads(outputs[1].read_text())
        marker["activated_count"] = 42
        outputs[1].write_text(json.dumps(marker))
        return result

    monkeypatch.setattr(
        module, "read_committed_active_identity_map",
        replace_receipt_after_first_verification,
    )
    with pytest.raises(ValueError, match="receipt changed across map verification"):
        module.read_committed_guarded_exact_report(
            outputs[0], outputs[1], outputs[2],
        )


def test_duplicate_score_report_json_key_is_not_authenticated(tmp_path):
    source = tmp_path / "signed.json"
    source.write_text('{"signed":true}')
    outputs = tuple(tmp_path / name for name in (
        "map.json", "receipt.json", "report.json",
    ))
    module._write_triplet(
        outputs,
        ({"bindings": [{"x": 1}]}, {"activated_count": 1}, {"matched": 1}),
        inputs=(source,),
    )
    forged = b'{"matched":0,"matched":1}\n'
    marker = json.loads(outputs[1].read_text())
    marker["exact_report_sha256"] = __import__("hashlib").sha256(forged).hexdigest()
    outputs[2].write_bytes(forged)
    outputs[1].write_text(json.dumps(marker))
    with pytest.raises(ValueError, match="duplicate JSON key"):
        module.read_committed_guarded_exact_report(
            outputs[0], outputs[1], outputs[2],
        )
