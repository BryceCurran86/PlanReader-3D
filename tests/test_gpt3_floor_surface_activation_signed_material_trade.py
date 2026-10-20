"""GPT3: independently source-proven floor finish ≠ any arbitrary frozen trade."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    seal_live_floor_finish_area_run,
)
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tests.test_gpt3_pending_floor_surface_identity_activation import (
    _inputs, _claim,
)
from tools.prepare_gpt3_pending_floor_surface_identity_activation import (
    build_floor_surface_activation,
)


def _run(*, finish="tile", trade="tiling", key=None):
    sealed, customers, pending, active, manifest, universe, proof = _inputs()
    manifest = deepcopy(manifest)
    manifest["verified_takeoff_items"][0]["trade_category"] = trade
    if finish != "tile" or key is not None:
        # Source-neutral INPUT fixture: reissue a valid signed source/customer
        # receipt from the actual producer rather than mutating a V1 signed
        # JSON body after the fact. Does not assert original Mary PDF support.
        original = _claim()
        source_floor = replace(
            original.canonical_floors[0],
            finish_descriptor=finish,
        )
        original_quantity = original.floor_finish_quantity_evidence[0]
        original_metadata = dict(original_quantity.metadata)
        original_metadata["semantic_finish"] = finish
        source_quantity = replace(
            original_quantity,
            semantic_key=key if key is not None else (
                f"floor_finish_area:floor-1:FT3:{finish}"
            ),
            metadata=original_metadata,
        )
        source_claim = replace(
            original,
            canonical_floors=(source_floor,),
            floor_finish_quantity_evidence=(source_quantity,),
        )
        signed = seal_live_floor_finish_area_run(
            source_claim, workspace_id=1, project_id="project-1",
        )
        customer = project_live_floor_finish_customer_rows(
            source_claim, workspace_id=1, project_id="project-1",
        )
        sealed = signed.to_dict()
        customers = list(customer)
    return build_floor_surface_activation(
        pending_ledger=pending,
        sealed_run_payload=sealed,
        customer_rows=customers,
        active_identity_map_payload=active,
        source_manifest=manifest,
        source_identity_proof=proof,
        object_universe=universe,
    )


def test_original_source_tile_to_tiling_activation_remains_exactly_authorized():
    candidate, receipt = _run(finish="tile", trade="tiling")
    assert candidate["bindings"] == [{
        "benchmark_item_id": "item-1",
        "production_family": "floor_finish_area",
        "production_object_identity_refs": ["floor-1"],
    }]
    assert receipt["activated_count"] == 1
    assert receipt["benchmark_score_granted"] is False
    assert receipt["evaluator_invoked"] is False


@pytest.mark.parametrize("finish", ["vinyl", "epoxy"])
def test_source_signed_nontile_cannot_activate_renamed_ft3_tiling(finish):
    with pytest.raises(ValueError, match="original source finish is not tile"):
        _run(finish=finish, trade="tiling")


@pytest.mark.parametrize("trade", ["doors", "windows", "ceilings", "concreting", "unknown"])
def test_exact_floor_evidence_cannot_activate_completely_wrong_frozen_trade(trade):
    with pytest.raises(ValueError, match="bound production family cannot be reclassified"):
        _run(finish="tile", trade=trade)


@pytest.mark.parametrize("finish", ["vinyl", "epoxy", "tile"])
def test_genuine_other_flooring_semantics_remain_independently_admissible(finish):
    identity_map, receipt = _run(finish=finish, trade="flooring")
    assert len(identity_map["bindings"]) == 1
    assert receipt["activated_count"] == 1
    assert receipt["benchmark_accuracy"] is None


@pytest.mark.parametrize("key", [
    "floor_finish_area:floor-1:FT3",
    "floor_finish_area:floor-1:FT3:vinyl:tile",
    "floor_finish_area:other-floor:FT3:tile",
])
def test_forged_noncanonical_floor_finish_cannot_activate(key):
    with pytest.raises(ValueError):
        _run(finish="tile", key=key)


def test_original_lot16_eight_signed_archive_unchanged():
    path = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json")
    archive = json.loads(path.read_text())
    parsed = sealed_source_closed_run_from_dict(archive)
    assert parsed.fingerprint == archive["fingerprint"] == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )


def test_shared_signed_trade_veto_runs_before_activation_receipt(monkeypatch):
    import tools.prepare_gpt3_pending_floor_surface_identity_activation as module
    seen = []
    real = module.require_signed_v2_family_trade_integrity

    def spy(**kwargs):
        signed = kwargs["sealed_quantities"]
        seen.append((
            tuple(row.semantic_key for row in signed),
            tuple(row["benchmark_item_id"] for row in kwargs["identity_bindings"]),
        ))
        return real(**kwargs)

    monkeypatch.setattr(module, "require_signed_v2_family_trade_integrity", spy)
    candidate, receipt = _run()
    assert receipt["activated_count"] == 1
    assert seen == [(
        ("floor_finish_area:floor-1:FT3:tile",),
        ("item-1",),
    )]
