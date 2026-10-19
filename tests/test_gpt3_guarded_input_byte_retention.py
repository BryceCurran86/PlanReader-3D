"""Source-neutral mutation regressions for GPT3 guarded V2 activation."""
from __future__ import annotations

import json
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

    assert [json.loads(path.read_text(encoding="utf-8")) for path in outputs] == [
        {"mapping": 1}, {"activation": 1}, {"score": None},
    ]
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
    assert len(calls) == 3
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
        path.write_text("[]" if path.name == "customers.json" else "{}", encoding="utf-8")
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
