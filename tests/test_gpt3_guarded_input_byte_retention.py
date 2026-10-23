"""Source-neutral mutation regressions for GPT3 guarded V2 activation."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

import tools.run_gpt3_guarded_pending_reconciliation as module


def _outputs(root: Path) -> tuple[Path, Path, Path]:
    return tuple(root / name for name in ("map.json", "activation.json", "score.json"))


def test_untouched_inputs_publish_all_three_exclusive_outputs(tmp_path: Path):
    original = tmp_path / "source.json"
    original.write_text('{"source":"immutable"}', encoding="utf-8")
    inputs = (original,)
    snapshot = module._snapshot_inputs(inputs)
    outputs = _outputs(tmp_path)

    module._write_triplet(
        outputs, ({"mapping": 1}, {"activation": 1}, {"score": None}),
        inputs=inputs, expected_input_hashes=snapshot,
    )

    saved_map, saved_receipt, saved_report = (
        json.loads(path.read_text(encoding="utf-8")) for path in outputs
    )
    assert saved_map == {"mapping": 1}
    assert saved_report == {"score": None}
    # The final receipt is the commit marker, not a verbatim copy of the
    # caller's activation payload. Verify both exact on-disk byte digests.
    assert saved_receipt["activation"] == 1
    assert saved_receipt["activation_commit_marker_version"] == (
        module.ACTIVATION_COMMIT_MARKER_VERSION
    )
    assert saved_receipt["identity_map_sha256"] == sha256(outputs[0].read_bytes()).hexdigest()
    assert saved_receipt["exact_report_sha256"] == sha256(outputs[2].read_bytes()).hexdigest()
    assert saved_receipt["identity_map_project_id"] is None
    assert saved_receipt["identity_map_source_sha256s"] is None
    assert module.read_committed_guarded_exact_report(*outputs) == {"score": None}
    assert original.read_text(encoding="utf-8") == '{"source":"immutable"}'


def test_changed_source_input_blocks_outputs_before_first_link(tmp_path: Path):
    original = tmp_path / "signed.json"
    original.write_text('{"seal":"first"}', encoding="utf-8")
    inputs = (original,)
    snapshot = module._snapshot_inputs(inputs)
    original.write_text('{"seal":"replaced"}', encoding="utf-8")
    outputs = _outputs(tmp_path)

    with pytest.raises(ValueError, match="input changed during scoring"):
        module._write_triplet(
            outputs, ({}, {}, {}), inputs=inputs,
            expected_input_hashes=snapshot,
        )

    assert all(not path.exists() for path in outputs)
    assert original.read_text(encoding="utf-8") == '{"seal":"replaced"}'


def test_changed_source_input_during_hardlinks_rolls_back_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    original = tmp_path / "customer.json"
    original.write_text('[{"quantity_id":"old"}]', encoding="utf-8")
    inputs = (original,)
    snapshot = module._snapshot_inputs(inputs)
    outputs = _outputs(tmp_path)
    link = module.os.link
    calls = []

    def mutate_after_first_link(source, target):
        link(source, target)
        calls.append(target)
        if len(calls) == 1:
            original.write_text('[{"quantity_id":"replacement"}]', encoding="utf-8")

    monkeypatch.setattr(module.os, "link", mutate_after_first_link)
    with pytest.raises(ValueError, match="input changed during scoring"):
        module._write_triplet(
            outputs, ({"map": True}, {"receipt": True}, {"score": None}),
            inputs=inputs, expected_input_hashes=snapshot,
        )
    # The changed input must fail closed immediately after the FIRST map link;
    # continuing to publish a report or marker would violate crash safety.
    assert len(calls) == 1
    assert all(not path.exists() and not path.is_symlink() for path in outputs)
    assert not list(tmp_path.glob(".gpt3-activation-*.tmp"))
    assert original.read_text(encoding="utf-8") == '[{"quantity_id":"replacement"}]'


def test_cli_rejects_signed_input_change_during_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    inputs = [
        tmp_path / name for name in (
            "pending.json", "signed.json", "customers.json",
            "identity-map.json", "manifest.json",
            "scope.json", "object-universe.json",
        )
    ]
    for path in inputs:
        if path.name == "customers.json":
            content = "[]"
        elif path.name == "identity-map.json":
            # A truly empty active baseline is the only receiptless bootstrap.
            content = '{"bindings":[]}'
        else:
            content = "{}"
        path.write_text(content, encoding="utf-8")
    outputs = _outputs(tmp_path)

    def simulate_scoring_after_source_mutation(**_kwargs):
        inputs[1].write_text('{"same_name":"changed_signed_bytes"}', encoding="utf-8")
        return ({"bindings": []}, {"activated_count": 1}, {"denominator": 27})

    monkeypatch.setattr(module, "build_guarded_exact_report", simulate_scoring_after_source_mutation)
    argv = [
        "--pending-ledger", str(inputs[0]),
        "--sealed-run", str(inputs[1]),
        "--customer-rows", str(inputs[2]),
        "--active-identity-map", str(inputs[3]),
        "--manifest", str(inputs[4]),
        "--source-identity-proof", str(inputs[5]),
        "--object-universe", str(inputs[6]),
        "--output-map", str(outputs[0]),
        "--output-activation-receipt", str(outputs[1]),
        "--output-report", str(outputs[2]),
    ]

    with pytest.raises(ValueError, match="input changed during scoring"):
        module.main(argv)
    assert all(not path.exists() for path in outputs)
