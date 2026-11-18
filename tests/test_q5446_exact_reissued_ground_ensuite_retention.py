"""Only byte-identical, source-sealed ground ENS reissuance may be skipped.

The original two-family issuer and independent ground-ENS issuer can discover
the SAME original physical face. Redundant source proof must not erase every
other signed customer row, nor create a duplicate billable bathroom.
"""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_gptmax_q5446_original_tiled_floor_customer import (
    OriginalQ5446TiledFloorCustomerResult,
)
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import (
    combine_source_closed_runs, seal_source_closed_run,
)
from tests.test_q5446_independent_source_floor_append import (
    _independent_result, _setup_producer,
)
from tests.test_q5446_source_role_two_family_bridge import (
    _original_fixture, _produce,
)
from tools import q5446_source_role_customer_runtime as runtime


def _two_family_with_independent_ground_ensuite(tmp_path, monkeypatch):
    plan, sha, project, original, two, *_ = _original_fixture(
        tmp_path, monkeypatch,
    )
    tile = two.original_tiled_room
    q = replace(
        tile.quantity,
        metadata={**tile.quantity.metadata,
                  "room_label": "ENS",
                  "commercial_projection_allowed": True,
                  "source_sha256": sha,
                  "tiled_floor_finish_authorized": True,
                  "net_internal_finished_face_authorized": True},
    )
    tile_seal = seal_source_closed_run(
        (q,), project_id=project,
        traces_by_quantity_id={q.quantity_id: tile.trace},
    )
    row = quantity_evidence_to_takeoff_output_row(
        q, trace=tile.trace, authority=CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=("synthetic-original-p1-x", "synthetic-original-p1-y"),
        ),
    )
    signed_tiled = OriginalQ5446TiledFloorCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW", ("synthetic-original-ground-ensuite",),
        q, tile.trace, tile_seal, (row,),
    )
    assert verify_sealed_customer_output(tile_seal, (row,)).customer_row_count == 1
    joined = combine_source_closed_runs(
        (original.sealed_run, tile_seal), project_id=project,
    )
    rows = (*original.customer_rows, row)
    assert verify_sealed_customer_output(joined, rows).customer_row_count == 2
    two = replace(
        two, original_tiled_room=signed_tiled,
        combined_sealed_run=joined, customer_rows=rows,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_alfresco_plus_ensuite_customer",
        lambda *_a, **_kw: two,
    )
    laundry = _independent_result(
        original, project, sha, "synthetic-laundry",
        "source-owned-laundry-unique-face",
    )
    first = _independent_result(
        original, project, sha, "synthetic-upper-ensuite",
        "source-owned-first-ens-unique-face",
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_laundry_tiled_floor",
        lambda *_a, **_kw: laundry,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_first_ensuite_tiled_floor",
        lambda *_a, **_kw: first,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_a, **_kw: signed_tiled,
    )
    return plan, sha, project, original, laundry, first, signed_tiled


def test_exact_sibling_ground_ensuite_replay_skips_without_losing_customer_rows(
    tmp_path, monkeypatch,
):
    plan, sha, project, original, laundry, first, ground = (
        _two_family_with_independent_ground_ensuite(tmp_path, monkeypatch)
    )
    result, out = _produce(tmp_path, plan, project)
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 4
    assert result["family_counts"] == {
        "floor_area": 1, "floor_finish_area": 3,
    }
    assert result["benchmark_score_granted"] is False
    assert result["source_role_coverage_verified"] is False
    sealed = load_verified_sealed_run(out / (project + ".json"))
    rows = json.loads((out / "verified_customer_rows.json").read_text())
    assert len(sealed.quantities) == len(rows) == 4
    assert {q.quantity_id for q in sealed.quantities} == {
        original.quantity.quantity_id, ground.quantity.quantity_id,
        laundry.quantity.quantity_id, first.quantity.quantity_id,
    }
    assert len({p for q in sealed.quantities
                for p in q.object_identity_refs}) == 4
    assert len({x["quantity_id"] for x in rows}) == 4
    assert verify_sealed_customer_output(sealed, rows).customer_row_count == 4
    assert rows[:2] == list(original.customer_rows) + list(ground.customer_rows)
    assert "official_four_project_accuracy" in result
    assert result["official_four_project_accuracy"] is None


@pytest.mark.parametrize("kind", [
    "different_customer", "different_quantity", "different_room_label",
    "different_source_face", "wrong_issuer",
])
def test_replayed_ground_ensuite_forgery_or_sibling_remains_a_fail_closed_veto(
    tmp_path, monkeypatch, kind,
):
    plan, _sha, project, original, laundry, first, ground = (
        _two_family_with_independent_ground_ensuite(tmp_path, monkeypatch)
    )
    if kind == "different_customer":
        ground = replace(ground, customer_rows=({
            **ground.customer_rows[0], "quantity": 99999,
        },))
    elif kind == "different_quantity":
        ground = replace(ground, quantity=replace(ground.quantity, value=99999))
    elif kind == "different_room_label":
        ground = replace(ground, quantity=replace(
            ground.quantity,
            metadata={**ground.quantity.metadata, "room_label": "LDRY"},
        ))
    elif kind == "different_source_face":
        ground = replace(ground, quantity=replace(
            ground.quantity,
            input_entity_ids=laundry.quantity.input_entity_ids,
        ))
    else:
        # A replay by the WRONG issuer must not consume the original
        # ground-ENS duplicate exception even if its receipt matches.
        monkeypatch.setattr(
            runtime, "issue_original_q5446_first_ensuite_tiled_floor",
            lambda *_a, **_kw: ground,
        )
    if kind != "wrong_issuer":
        monkeypatch.setattr(
            runtime, "issue_original_q5446_ground_ensuite_tiled_floor",
            lambda *_a, **_kw: ground,
        )
    result, out = _produce(tmp_path, plan, project)
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (out / (project + ".json")).exists()
    assert not (out / "verified_customer_rows.json").exists()
