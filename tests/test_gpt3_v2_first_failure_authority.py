"""First-failure V2 readiness is a source diagnostics gate, not accuracy."""
from pathlib import Path
import pytest

from scripts.report_full_plan_v2_readiness import (
    _first_failing_authority_stage, diagnostic_report,
)

ROOT=Path("benchmarks/frozen_holdout/full_plan_v2")


def _first(**replacements):
    state=dict(
        source_verified=True,source_reasons=[],
        manifest_status="VERIFIED",manifest_reasons=[],
        sealed_verified=True,seal_reasons=[],
        produced_present=True,produced_valid=True,produced_count=2,
        parity_verified=True,parity_reasons=[],
    )
    state.update(replacements)
    return _first_failing_authority_stage(**state)


def test_missing_original_pdf_sha_has_first_authority_priority_over_everything():
    assert _first(
        source_verified=False,source_reasons=["source_file_missing:proof.pdf"],
        manifest_status="INCOMPLETE",manifest_reasons=["missing_room_geometry"],
        sealed_verified=False,seal_reasons=["sealed_run_missing"],
        produced_present=False,parity_verified=False,
    )==("ORIGINAL_SOURCE_SHA_AUTHORITY","source_file_missing:proof.pdf")


def test_authenticated_pdf_but_incomplete_source_geometry_stops_at_universe():
    assert _first(
        manifest_status="INCOMPLETE",
        manifest_reasons=["remaining_room_area_universe_not_built"],
        sealed_verified=False,produced_present=False,
    )==("SOURCE_UNIVERSE_CLOSURE","remaining_room_area_universe_not_built")


def test_completed_source_universe_but_missing_signed_production_run_stops_at_seal():
    assert _first(
        sealed_verified=False,
        seal_reasons=["sealed_run_missing"],
        produced_present=False,
    )==("SEALED_PRODUCTION_AUTHORITY","sealed_run_missing")


@pytest.mark.parametrize(("state","reason"),[
    ({"produced_present":False},"production_items_missing"),
    ({"produced_valid":False},"produced_items_invalid_json_or_shape"),
    ({"produced_count":0},"empty_produced_items_unverified"),
])
def test_missing_or_malformed_produced_items_never_become_complete(state,reason):
    assert _first(**state)==("PRODUCED_ITEMS",reason)


def test_signed_quantity_mismatch_is_reported_as_exact_first_parity_reason():
    assert _first(parity_verified=False,
        parity_reasons=["projection_object_identity_mismatch:floor-1"])==(
        "SIGNED_QUANTITY_PARITY","projection_object_identity_mismatch:floor-1")


def test_even_fully_matched_ids_do_not_invent_commercial_trade_authority():
    assert _first()==("COMMERCIAL_TRADE_AUTHORITY",
        "commercial_trade_authority_not_independently_verified")


def test_real_four_project_readiness_retains_unpublished_scores_and_source_gate(tmp_path):
    report=diagnostic_report(ROOT,tmp_path)
    assert report["required_project_count"]==4
    assert report["publication_status"]=="UNPUBLISHED"
    assert not report["score_claim"]
    for project in report["projects"]:
        assert project["first_failing_authority_stage"]=="ORIGINAL_SOURCE_SHA_AUTHORITY"
        assert project["first_failing_authority_reason"]=="source_files_not_supplied"
        assert project["matched_within_tolerance"] is None
        assert project["matched_outside_tolerance"] is None
        assert project["missed"] is None
        assert project["partial"] is None
        assert project["unresolved"] is None
        assert project["unsupported_extra"] is None
        assert project["coverage_accuracy"] is None
        assert project["precision_adjusted_accuracy"] is None
