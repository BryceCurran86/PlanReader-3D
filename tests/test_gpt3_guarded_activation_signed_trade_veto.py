"""GPT3 guarded activation cannot skip signed family/trade veto into frozen V2."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.run_gpt3_guarded_pending_reconciliation as activation
from tests.test_gpt3_guarded_pending_reconciliation import (
    _run,
    _pending,
    _partial_map,
    _json,
    EVIDENCE,
    MANIFEST,
    OBJECT_UNIVERSE,
    SOURCE_IDENTITY_PROOF,
)


def test_real_pre_certified_seven_row_lot16_activation_still_scores_exact_seven():
    mapped, receipt, report = _run()
    assert receipt["activated_count"] == 1
    assert len(mapped["bindings"]) == 7
    assert report["matched_within_tolerance"] == 7
    assert report["denominator"] == 27
    assert report["source_sha_verified"] is True
    assert receipt["benchmark_score_granted"] is False


def test_guarded_activation_vetoes_window_area_mapped_to_frozen_door_before_evaluator(
    monkeypatch,
):
    original_activate = activation.build_activation
    reached = []

    def faulty_identity_crosswalk(**kwargs):
        mapped, receipt = original_activate(**kwargs)
        assert receipt["activated_count"] == 1
        for binding in mapped["bindings"]:
            if binding["benchmark_item_id"] == _pending()["benchmark_item_id"]:
                # Deliberately bypass ONLY the independent identity-map
                # producer's target election to probe the next release gate.
                # Physical source remains a genuine signed Lot16 window.
                binding["benchmark_item_id"] = "lot16-2127-stacker-01-area"
                break
        else:
            raise AssertionError("original pending window was never activated")
        return mapped, receipt

    def forbidden_evaluator_import():
        reached.append("evaluator")
        raise AssertionError("frozen evaluator must not run on incompatible trade")

    monkeypatch.setattr(activation, "build_activation", faulty_identity_crosswalk)
    monkeypatch.setattr(activation, "_exact_report_module", forbidden_evaluator_import)
    with pytest.raises(ValueError, match="source-owned opening kind disagrees"):
        _run()
    assert not reached


def test_guarded_activation_preserves_original_full_signed_source_receipt(
    monkeypatch,
):
    """Negative veto receives parsed V1 receipts, not untrusted row captions."""
    real_veto = activation.require_signed_v2_family_trade_integrity
    seen = []

    def observe(**kwargs):
        rows = tuple(kwargs["sealed_quantities"])
        seen.append({
            "count": len(rows),
            "sha": tuple(sorted(set(row.source_sha256 for row in rows))),
            "families": {row.family for row in rows},
            "bindings": len(kwargs["identity_bindings"]),
            "eligible": len(tuple(kwargs["verified_items"])),
        })
        return real_veto(**kwargs)

    monkeypatch.setattr(
        activation, "require_signed_v2_family_trade_integrity", observe,
    )
    mapped, receipt, report = _run()
    assert report["matched_within_tolerance"] == 7
    assert seen == [{
        "count": 7,
        "sha": (
            "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        ),
        "families": {"opening_area"},
        "bindings": 7,
        "eligible": 27,
    }]


def test_incompatible_trade_is_never_saved_as_guarded_exact_report(tmp_path, monkeypatch):
    """The same active map can't yield a published scored output through CLI."""
    active = _partial_map()
    archive = _json(EVIDENCE / "source_sealed_run.json")
    manifest = _json(MANIFEST)
    source_proof = _json(SOURCE_IDENTITY_PROOF)
    universe = _json(OBJECT_UNIVERSE)
    customers = _json(EVIDENCE / "verified_customer_rows.json")
    for name, payload in (
        ("pending", _pending()), ("sealed", archive),
        ("customers", customers), ("active", active),
        ("proof", source_proof), ("universe", universe),
    ):
        (tmp_path / f"{name}.json").write_text(json.dumps(payload))

    original_activate = activation.build_activation
    def wrong_kind(**kwargs):
        candidate, receipt = original_activate(**kwargs)
        for row in candidate["bindings"]:
            if row["benchmark_item_id"] == _pending()["benchmark_item_id"]:
                row["benchmark_item_id"] = "lot16-2127-stacker-01-area"
        return candidate, receipt

    monkeypatch.setattr(activation, "build_activation", wrong_kind)
    outputs = tuple(tmp_path / n for n in ("new-map.json", "receipt.json", "score.json"))
    args = []
    for opt, file in [
        ("--pending-ledger", tmp_path / "pending.json"),
        ("--sealed-run", tmp_path / "sealed.json"),
        ("--customer-rows", tmp_path / "customers.json"),
        ("--active-identity-map", tmp_path / "active.json"),
        ("--manifest", MANIFEST),
        ("--source-identity-proof", tmp_path / "proof.json"),
        ("--object-universe", tmp_path / "universe.json"),
        ("--output-map", outputs[0]),
        ("--output-activation-receipt", outputs[1]),
        ("--output-report", outputs[2]),
    ]:
        args.extend((opt, str(file)))
    with pytest.raises(ValueError, match="source-owned opening kind disagrees"):
        activation.main(args)
    assert not any(path.exists() for path in outputs)


def test_source_trade_guard_requires_original_canonical_frozen_manifest():
    with pytest.raises(ValueError, match="canonical frozen manifest"):
        _run.__globals__["module"].build_guarded_exact_report(
            pending_ledger=_pending(),
            sealed_run_payload=_json(EVIDENCE / "source_sealed_run.json"),
            customer_rows=_json(EVIDENCE / "verified_customer_rows.json"),
            active_identity_map_payload=_partial_map(),
            source_manifest=_json(MANIFEST),
            source_identity_proof=_json(SOURCE_IDENTITY_PROOF),
            object_universe=_json(OBJECT_UNIVERSE),
            manifest_path=Path("/tmp/forged-manifest.json"),
        )
