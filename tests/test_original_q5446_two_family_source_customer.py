"""Original Q5446 two-family floor integration, source and identity negatives.

Two real original PDF roles corroborate tile materials; the original plan
independently supplies both ALFRESCO and a finished ensuite. No benchmark
truth, expected area or evaluator identity enters the original-app producer.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import os

import pytest

import pb_gptmax_q5446_original_family_customer_append as m
from pb_customer_output_verification import verify_sealed_customer_output


@pytest.fixture
def original_paths():
    p=Path(os.environ.get("PLANREADER_Q5446_ORIGINAL_SOURCE_DIR","documents/sources"))
    sources=(p/"Q5446_Standard_Plans_V1_20220320.pdf",
             p/"Q5446_Standard_Inclusions_V1_20220313.pdf",
             p/"Q5446_Sales_Advice_Estimate_V1_20220320.pdf")
    if not all(f.is_file() for f in sources):
        pytest.skip("private original Q5446 source set unavailable")
    return sources


def test_original_alfresco_plus_tiled_ensuite_is_distinct_verified_customer(original_paths):
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(*original_paths)
    assert result.status=="TWO_INDEPENDENT_SOURCE_FAMILIES_CUSTOMER_VERIFIED",result.reason_codes
    assert result.source_role_coverage_verified is False
    assert result.original_alfresco is not None and result.original_tiled_room is not None
    assert result.original_alfresco.quantity.value==12.0
    assert result.original_tiled_room.quantity.value==4.247308
    assert result.original_alfresco.quantity.family=="floor_area"
    assert result.original_tiled_room.quantity.family=="floor_finish_area"
    assert len(result.customer_rows)==2
    assert result.combined_sealed_run is not None and len(result.combined_sealed_run.quantities)==2
    qids={x.quantity_id for x in result.combined_sealed_run.quantities}
    assert len(qids)==2
    assert qids=={x["quantity_id"] for x in result.customer_rows}
    assert {x["quantity_status"] for x in result.customer_rows}=={"To review"}
    verify_sealed_customer_output(result.combined_sealed_run,result.customer_rows)
    old=result.original_alfresco.sealed_run.quantities[0].to_dict()
    assert next(x.to_dict() for x in result.combined_sealed_run.quantities
                if x.quantity_id==result.original_alfresco.quantity.quantity_id)==old
    assert result.customer_rows[0]==result.original_alfresco.customer_rows[0]


@pytest.mark.parametrize("tampered_index", [0,1,2])
def test_mutated_original_source_role_abstains_without_combined_receipt(
    original_paths,tmp_path,tampered_index,
):
    paths=list(original_paths)
    changed=tmp_path/("altered_original_role_%d.pdf"%tampered_index)
    changed.write_bytes(paths[tampered_index].read_bytes()+b"\n%mutation")
    paths[tampered_index]=changed
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(*paths)
    assert result.status=="ABSTAIN"
    assert result.combined_sealed_run is None
    assert result.customer_rows==()


def test_role_substitution_cannot_launder_tile_scope(original_paths):
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(
        original_paths[0],original_paths[2],original_paths[1],
    )
    assert result.status=="ABSTAIN" and result.combined_sealed_run is None


def test_unauthenticated_workspace_and_absent_source_never_seal(original_paths,tmp_path):
    assert m.issue_original_q5446_alfresco_plus_ensuite_customer(
        *original_paths,workspace_id=0).combined_sealed_run is None
    assert m.issue_original_q5446_alfresco_plus_ensuite_customer(
        tmp_path/"missing.pdf",*original_paths[1:]).combined_sealed_run is None


def test_missing_second_physical_source_cannot_break_existing_alfresco(original_paths,monkeypatch):
    from pb_gptmax_q5446_original_tiled_floor_customer import (
        OriginalQ5446TiledFloorCustomerResult,
    )
    monkeypatch.setattr(m,"issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_args,**_kwargs: OriginalQ5446TiledFloorCustomerResult(
            "ABSTAIN",("source_face_missing",)
        ))
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(*original_paths)
    assert result.status=="ABSTAIN"
    assert result.combined_sealed_run is None
    assert result.customer_rows==()
    prior=m.issue_original_q5446_alfresco_customer_area(
        str(original_paths[0]),workspace_id=1,
    )
    assert prior.status=="FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert prior.quantity is not None and prior.quantity.value==12.0
    verify_sealed_customer_output(prior.sealed_run,prior.customer_rows)


def test_second_family_cannot_reuse_alfresco_physical_identity(original_paths,monkeypatch):
    genuine_alfresco=m.issue_original_q5446_alfresco_customer_area(
        str(original_paths[0]),workspace_id=1,
    )
    genuine_tile=m.issue_original_q5446_ground_ensuite_tiled_floor(*original_paths)
    duplicated=replace(genuine_tile,quantity=replace(genuine_tile.quantity,
        input_entity_ids=genuine_alfresco.quantity.input_entity_ids))
    monkeypatch.setattr(m,"issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_args,**_kwargs: duplicated)
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(*original_paths)
    assert result.status=="ABSTAIN"
    assert result.reason_codes==("original_ensuite_signed_customer_retention_unavailable",)


def test_second_family_cannot_drop_its_original_customer_row(original_paths,monkeypatch):
    real=m.issue_original_q5446_ground_ensuite_tiled_floor(*original_paths)
    monkeypatch.setattr(m,"issue_original_q5446_ground_ensuite_tiled_floor",
        lambda *_args,**_kwargs: replace(real,customer_rows=()))
    result=m.issue_original_q5446_alfresco_plus_ensuite_customer(*original_paths)
    assert result.status=="ABSTAIN"
    assert result.combined_sealed_run is None


def test_benchmark_reference_is_not_in_source_issuer():
    from inspect import getsource
    source=getsource(m.issue_original_q5446_alfresco_plus_ensuite_customer)
    for token in ("reference_takeoff","benchmark", "expected_quantity", "0.05"):
        assert token not in source
