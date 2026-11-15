"""Source-neutral two-family role adapter tests; no benchmark/source gold inputs.

A synthesized source can test rejection and customer-body retention, but cannot
grant original PDF geometry or the Q5446 frozen development accuracy score.
"""
from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

import pytest

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_gptmax_q5446_original_family_customer_append import Q5446TwoFamilyCustomerResult
from pb_gptmax_q5446_original_tiled_floor_customer import (
    OriginalQ5446TiledFloorCustomerResult,
)
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import (
    combine_source_closed_runs,
    seal_source_closed_run,
)
from tests.test_q5446_source_role_customer_runtime import _setup
from tests.test_source_closed_project_handoff import _quantity
from tools import q5446_source_role_customer_runtime as runtime


def _original_fixture(tmp_path, monkeypatch):
    plan, source_sha, project, prior = _setup(tmp_path, monkeypatch)
    inclusions = plan.parent / "independent-inclusions.pdf"
    sales = plan.parent / "independent-sales.pdf"
    inclusions.write_bytes(b"synthetic separate inclusions source; no real finish authority")
    sales.write_bytes(b"synthetic separate sales source; no real finish authority")
    monkeypatch.setattr(runtime, "SOURCE_IDS", {
        "standard_inclusions": sha256(inclusions.read_bytes()).hexdigest(),
        "scope_and_allowance_reference": sha256(sales.read_bytes()).hexdigest(),
    })

    tile = replace(
        _quantity("synthetic-independent-tile-floor", "floor_finish_area"),
        input_entity_ids=("independent-finished-floor-face",),
        metadata={"source_sha256": source_sha,
                  "tiled_floor_finish_authorized": True,
                  "net_internal_finished_face_authorized": True},
    )
    trace = replace(prior.trace, evidence_ids=tile.evidence_ids,
                    canonical_entity_ids=tile.input_entity_ids)
    tile_seal = seal_source_closed_run(
        (tile,), project_id=project,
        traces_by_quantity_id={tile.quantity_id: trace},
    )
    row = quantity_evidence_to_takeoff_output_row(
        tile, trace=trace,
        authority=CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=("synthetic-x-witness", "synthetic-y-witness"),
        ),
    )
    combined = combine_source_closed_runs(
        (prior.sealed_run, tile_seal), project_id=project,
    )
    rows = (*prior.customer_rows, row)
    assert verify_sealed_customer_output(combined, rows).customer_row_count == 2
    tiled = OriginalQ5446TiledFloorCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW", ("synthetic-test-only",),
        tile, trace, tile_seal, (row,),
    )
    result = Q5446TwoFamilyCustomerResult(
        status="TWO_INDEPENDENT_SOURCE_FAMILIES_CUSTOMER_VERIFIED",
        reason_codes=("source-neutral-test-only",),
        source_role_coverage_verified=False,
        original_alfresco=prior,
        original_tiled_room=tiled,
        combined_sealed_run=combined,
        customer_rows=rows,
    )
    return plan, source_sha, project, prior, result, inclusions, sales


def _produce(tmp_path, plan, project):
    output = tmp_path / "sealed-output"
    output.mkdir()
    return runtime.produce_q5446_source_role(
        pdf_path=plan, project_id=project, output_dir=output,
    ), output


def test_companion_sources_use_sha_not_filename_and_preserve_full_prior(tmp_path, monkeypatch):
    plan, source_sha, project, prior, two, inclusions, sales = _original_fixture(
        tmp_path, monkeypatch,
    )
    calls = []
    def valid_two(*paths, **_kwargs):
        calls.append(tuple(paths))
        return two
    monkeypatch.setattr(runtime, "issue_original_q5446_alfresco_plus_ensuite_customer", valid_two)
    assert runtime._authenticated_companion_roles(plan) == (inclusions, sales)
    result, output = _produce(tmp_path, plan, project)
    assert calls == [(plan, inclusions, sales)]
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 2
    assert result["family_counts"] == {"floor_area": 1, "floor_finish_area": 1}
    assert result["source_role_coverage_verified"] is False
    assert result["benchmark_score_granted"] is False
    signed = load_verified_sealed_run(output / (project + ".json"))
    rows = json.loads((output / "verified_customer_rows.json").read_text())
    assert len(signed.quantities) == len(rows) == 2
    assert {q.family for q in signed.quantities} == {"floor_area", "floor_finish_area"}
    assert set(signed.source_sha256s) == {source_sha}
    assert any(q.to_dict() == prior.sealed_run.quantities[0].to_dict()
               for q in signed.quantities)
    assert rows[0] == prior.customer_rows[0]
    assert verify_sealed_customer_output(signed, rows).customer_row_count == 2


@pytest.mark.parametrize("companion_failure", ("missing", "tampered", "duplicate", "absent_result"))
def test_missing_untrusted_or_abstaining_second_family_retains_alfresco(
    tmp_path, monkeypatch, companion_failure,
):
    plan, _sha, project, prior, _two, inclusions, sales = _original_fixture(
        tmp_path, monkeypatch,
    )
    if companion_failure == "missing":
        inclusions.unlink()
    if companion_failure == "tampered":
        sales.write_bytes(sales.read_bytes() + b"tampered")
    if companion_failure == "duplicate":
        (sales.parent / "same-sha-copy.PDF").write_bytes(sales.read_bytes())
    calls = []
    def abstain(*_args, **_kwargs):
        calls.append(1)
        return Q5446TwoFamilyCustomerResult("ABSTAIN", ("source-unavailable",))
    monkeypatch.setattr(runtime, "issue_original_q5446_alfresco_plus_ensuite_customer", abstain)
    result, output = _produce(tmp_path, plan, project)
    assert len(calls) == (1 if companion_failure == "absent_result" else 0)
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 1
    assert result["family_counts"] == {"floor_area": 1}
    assert result["benchmark_score_granted"] is False
    signed = load_verified_sealed_run(output / (project + ".json"))
    rows = json.loads((output / "verified_customer_rows.json").read_text())
    assert len(signed.quantities) == len(rows) == 1
    assert signed.quantities[0].to_dict() == prior.sealed_run.quantities[0].to_dict()
    assert rows[0] == prior.customer_rows[0]


@pytest.mark.parametrize("forged", ("changed_prior", "changed_customer", "fake_coverage", "invalid_count"))
def test_forged_extra_family_cannot_publish_even_one_combined_row(
    tmp_path, monkeypatch, forged,
):
    plan, _sha, project, prior, two, _incl, _sales = _original_fixture(
        tmp_path, monkeypatch,
    )
    if forged == "changed_prior":
        bad_prior = replace(prior, customer_rows=({
            **prior.customer_rows[0], "quantity": 12345,
        },))
        two = replace(two, original_alfresco=bad_prior)
    elif forged == "changed_customer":
        two = replace(two, customer_rows=(two.customer_rows[0], {
            **two.customer_rows[1], "quantity": 12345,
        }))
    elif forged == "fake_coverage":
        two = replace(two, source_role_coverage_verified=True)
    else:
        two = replace(two, customer_rows=two.customer_rows[:1])
    monkeypatch.setattr(runtime, "issue_original_q5446_alfresco_plus_ensuite_customer",
                        lambda *_a, **_k: two)
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "no_sealable_quantities"
    assert result["customer_rows_verified"] is False
    assert result["benchmark_score_granted"] is False
    assert not (output / (project + ".json")).exists()
    assert not (output / "verified_customer_rows.json").exists()
