"""Source-neutral checks: independently signed wet floors survive sibling ABSTAIN.

Never import frozen benchmark truth or rely on private PDFs in public CI.
"""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_gptmax_q5446_original_family_customer_append import Q5446TwoFamilyCustomerResult
from pb_gptmax_q5446_original_tiled_floor_customer import OriginalQ5446TiledFloorCustomerResult
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import seal_source_closed_run
from tests.test_q5446_source_role_two_family_bridge import _original_fixture, _produce
from tests.test_source_closed_project_handoff import _quantity
from tools import q5446_source_role_customer_runtime as runtime


def _independent_result(prior, project, source_sha, suffix, physical_id):
    q = replace(
        _quantity(suffix, "floor_finish_area"),
        input_entity_ids=(physical_id,),
        metadata={
            "source_sha256": source_sha,
            "commercial_projection_allowed": True,
            "tiled_floor_finish_authorized": True,
            "net_internal_finished_face_authorized": True,
        },
    )
    trace = replace(
        prior.trace, evidence_ids=q.evidence_ids,
        canonical_entity_ids=q.input_entity_ids,
    )
    sealed = seal_source_closed_run(
        (q,), project_id=project,
        traces_by_quantity_id={q.quantity_id: trace},
    )
    rows = (quantity_evidence_to_takeoff_output_row(
        q, trace=trace, authority=CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=("synthetic-source-x", "synthetic-source-y"),
        ),
    ),)
    verify_sealed_customer_output(sealed, rows)
    return OriginalQ5446TiledFloorCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW", ("synthetic-only",),
        q, trace, sealed, rows,
    )


def _setup_producer(tmp_path, monkeypatch):
    plan, sha, project, prior, _two, *_ = _original_fixture(
        tmp_path, monkeypatch,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_alfresco_plus_ensuite_customer",
        lambda *_a, **_kw: Q5446TwoFamilyCustomerResult(
            "ABSTAIN", ("third-room-unverified",),
        ),
    )
    laundry = _independent_result(
        prior, project, sha, "synthetic-laundry", "verified-laundry-face",
    )
    ensuite = _independent_result(
        prior, project, sha, "synthetic-first-ens",
        "verified-first-ensuite-face",
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_laundry_tiled_floor",
        lambda *_a, **_kw: laundry,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_first_ensuite_tiled_floor",
        lambda *_a, **_kw: ensuite,
    )
    return plan, sha, project, prior, laundry, ensuite


def test_abstained_ground_ensuite_preserves_independently_signed_siblings(
    tmp_path, monkeypatch,
):
    plan, sha, project, prior, laundry, ensuite = _setup_producer(
        tmp_path, monkeypatch,
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 3
    assert result["family_counts"] == {
        "floor_area": 1, "floor_finish_area": 2,
    }
    assert result["benchmark_score_granted"] is False
    signed = load_verified_sealed_run(output / (project + ".json"))
    rows = json.loads(
        (output / "verified_customer_rows.json").read_text(),
    )
    assert len(signed.quantities) == 3
    assert set(signed.source_sha256s) == {sha}
    assert {x.quantity_id: x.to_dict() for x in signed.quantities} == {
        x.quantity_id: x.to_dict()
        for x in (
            prior.sealed_run.quantities[0],
            laundry.sealed_run.quantities[0],
            ensuite.sealed_run.quantities[0],
        )
    }
    assert rows[0] == prior.customer_rows[0]
    assert rows[1:] == [
        laundry.customer_rows[0], ensuite.customer_rows[0],
    ]
    assert verify_sealed_customer_output(signed, rows).customer_row_count == 3


def test_individual_abstention_does_not_erase_other_sibling(
    tmp_path, monkeypatch,
):
    plan, _sha, project, _prior, _laundry, _ensuite = _setup_producer(
        tmp_path, monkeypatch,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_laundry_tiled_floor",
        lambda *_a, **_kw: OriginalQ5446TiledFloorCustomerResult(
            "ABSTAIN", ("ocr-not-proven",),
        ),
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "sealed"
    assert result["family_counts"] == {
        "floor_area": 1, "floor_finish_area": 1,
    }
    signed = load_verified_sealed_run(output / (project + ".json"))
    assert len(signed.quantities) == 2


@pytest.mark.parametrize("forgery", (
    "duplicate_face", "duplicate_quantity", "bad_sha",
    "fake_customer", "status", "false_abstain",
))
def test_spoofed_duplicate_or_unverified_sibling_cannot_publish(
    tmp_path, monkeypatch, forgery,
):
    plan, _sha, project, _prior, laundry, ensuite = _setup_producer(
        tmp_path, monkeypatch,
    )
    if forgery == "duplicate_face":
        ensuite = replace(
            ensuite, quantity=replace(
                ensuite.quantity,
                input_entity_ids=laundry.quantity.input_entity_ids,
            ),
        )
    elif forgery == "duplicate_quantity":
        ensuite = laundry
    elif forgery == "bad_sha":
        ensuite = replace(
            ensuite, quantity=replace(
                ensuite.quantity,
                metadata={
                    **ensuite.quantity.metadata,
                    "source_sha256": "0" * 64,
                },
            ),
        )
    elif forgery == "fake_customer":
        ensuite = replace(
            ensuite, customer_rows=({
                **ensuite.customer_rows[0], "quantity": 99999,
            },),
        )
    elif forgery == "status":
        ensuite = replace(ensuite, status="FIRM")
    else:
        ensuite = replace(ensuite, status="ABSTAIN")
    monkeypatch.setattr(
        runtime, "issue_original_q5446_first_ensuite_tiled_floor",
        lambda *_a, **_kw: ensuite,
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (output / (project + ".json")).exists()


def test_source_verified_ground_ensuite_is_fourth_independent_customer_row(
    tmp_path, monkeypatch,
):
    plan, sha, project, prior, laundry, first_ens = _setup_producer(
        tmp_path, monkeypatch,
    )
    original_ground = _independent_result(
        prior, project, sha, "synthetic-ground-ens",
        "verified-ground-ensuite-face",
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_a, **_kw: original_ground,
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "sealed"
    assert result["family_counts"] == {
        "floor_area": 1, "floor_finish_area": 3,
    }
    assert result["verified_customer_row_count"] == 4
    assert result["benchmark_score_granted"] is False
    signed = load_verified_sealed_run(output / (project + ".json"))
    rows = json.loads((output / "verified_customer_rows.json").read_text())
    assert set(signed.source_sha256s) == {sha}
    assert len({x.quantity_id for x in signed.quantities}) == 4
    assert len(set(
        physical_id for q in signed.quantities
        for physical_id in q.object_identity_refs
    )) == 4
    assert {q.quantity_id for q in signed.quantities} == {
        q.quantity_id for q in (
            prior.sealed_run.quantities[0],
            laundry.sealed_run.quantities[0],
            first_ens.sealed_run.quantities[0],
            original_ground.sealed_run.quantities[0],
        )
    }
    assert rows[0] == prior.customer_rows[0]
    assert verify_sealed_customer_output(signed, rows).customer_row_count == 4


def test_duplicate_ground_ensuite_physical_owner_cannot_republish(
    tmp_path, monkeypatch,
):
    plan, _sha, project, _prior, laundry, _first = _setup_producer(
        tmp_path, monkeypatch,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_a, **_kw: laundry,
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (output / (project + ".json")).exists()
