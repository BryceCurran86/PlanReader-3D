"""GPT3: standalone physical opening map activation must honor source kind."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tests.test_gpt3_pending_identity_activation import (
    _activate, _manifest, ITEM, PHYSICAL, SOURCE_SHA, EVIDENCE,
)
import tools.prepare_gpt3_pending_identity_activation as activation


def _changed_target_trade(trade):
    manifest = _manifest()
    target = next(
        item for item in manifest["verified_takeoff_items"]
        if item["item_id"] == ITEM
    )
    assert target["trade_category"] == "windows"
    target["trade_category"] = trade
    return manifest


def test_exact_owner_source_opening_can_activate_its_certified_window_target():
    result, receipt = _activate()
    assert receipt["activated_count"] == 1
    assert receipt["benchmark_score_granted"] is False
    assert receipt["evaluator_invoked"] is False
    assert receipt["benchmark_accuracy"] is None
    assert result["bindings"] == [{
        "benchmark_item_id": ITEM,
        "production_family": "opening_area",
        "production_object_identity_refs": [PHYSICAL],
    }]


@pytest.mark.parametrize("trade", ["doors", "flooring", "tiling", "ceilings", "unknown"])
def test_source_signed_window_cannot_be_activated_against_wrong_frozen_trade(trade):
    # Only the in-memory source-neutral verified-item trade is mutated;
    # actual signed Lot16 QuantityEvidence and customer rows are unchanged.
    with pytest.raises(ValueError, match="bound production family cannot be reclassified|source-owned opening kind disagrees"):
        _activate(manifest=_changed_target_trade(trade))


def test_exact_preexisting_bindings_also_pass_source_signed_trade_gate(monkeypatch):
    original_veto = activation.require_signed_v2_family_trade_integrity
    captured = []

    def observe(**kwargs):
        source = tuple(kwargs["sealed_quantities"])
        candidate = tuple(kwargs["identity_bindings"])
        captured.append({
            "source_count": len(source),
            "source_sha": set(q.source_sha256 for q in source),
            "bind_count": len(candidate),
            "eligible": len(tuple(kwargs["verified_items"])),
        })
        return original_veto(**kwargs)

    monkeypatch.setattr(
        activation, "require_signed_v2_family_trade_integrity", observe,
    )
    new, receipt = _activate()
    assert receipt["activated_count"] == 1
    assert len(new["bindings"]) == 1
    assert captured == [{
        "source_count": 7,
        "source_sha": {SOURCE_SHA},
        "bind_count": 1,
        "eligible": 27,
    }]


def test_source_trades_still_checked_when_preserving_six_active_windows(monkeypatch):
    existing = json.loads((EVIDENCE / "identity_map.json").read_text())
    existing["bindings"] = [
        x for x in existing["bindings"] if x["benchmark_item_id"] != ITEM
    ]
    assert len(existing["bindings"]) == 6
    observed = []
    real = activation.require_signed_v2_family_trade_integrity

    def veto(**kwargs):
        observed.append(len(kwargs["identity_bindings"]))
        return real(**kwargs)

    monkeypatch.setattr(activation, "require_signed_v2_family_trade_integrity", veto)
    new, receipt = _activate(active=existing)
    assert receipt["activated_count"] == 1
    assert len(new["bindings"]) == 7
    assert observed == [7]


def test_unverified_source_trade_never_grants_a_score_even_when_units_look_right():
    # Authentic source is 2.16 m² WINDOW; original signed quantity remains
    # intact. Incompatible frozen trade is rejected BEFORE activation.
    tampered = _changed_target_trade("doors")
    assert next(x for x in tampered["verified_takeoff_items"]
                if x["item_id"] == ITEM)["unit"] == "m2"
    with pytest.raises(ValueError, match="source-owned opening kind disagrees"):
        _activate(manifest=tampered)


def test_historical_eight_signed_lot16_archive_stays_byte_identical():
    archive = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json")
    original = json.loads(archive.read_text(encoding="utf-8"))
    valid = sealed_source_closed_run_from_dict(original)
    assert len(valid.quantities) == 8
    assert valid.fingerprint == original["fingerprint"] == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )
