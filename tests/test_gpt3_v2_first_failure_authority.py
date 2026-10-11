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
        produced_reasons=[],
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
    ({"produced_valid":False,"produced_reasons":["produced_items_invalid_json_or_shape"]},"produced_items_invalid_json_or_shape"),
    ({"produced_count":0},"empty_produced_items_unverified"),
])
def test_missing_or_malformed_produced_items_never_become_complete(state,reason):
    assert _first(**state)==("PRODUCED_ITEMS",reason)


@pytest.mark.parametrize("actual_reason",[
    "duplicate_produced_quantity_ids",
    "produced_quantity_id_missing_or_invalid",
    "produced_items_invalid_json_or_shape",
])
def test_exact_produced_id_failure_is_reported_instead_of_generic_json_error(actual_reason):
    assert _first(produced_valid=False,produced_reasons=[actual_reason])==(
        "PRODUCED_ITEMS",actual_reason)


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


def test_original_pdf_rotated_after_initial_sha_before_final_readiness_is_rejected(
    tmp_path,monkeypatch
):
    import hashlib
    import json
    import scripts.report_full_plan_v2_readiness as readiness
    project_id="au_qld_synthetic_source_rotation"
    root=tmp_path/"frozen-fixture"
    proj=root/"projects"/project_id
    proj.mkdir(parents=True)
    (root/"manifest.json").write_text(json.dumps({
        "projects":[project_id],"required_project_count":1,
    }),encoding="utf-8")
    source_root=tmp_path/"original-source"
    source_dir=source_root/project_id
    source_dir.mkdir(parents=True)
    original=b"%PDF-known-original-bytes"
    source=source_dir/"evidence.pdf"
    source.write_bytes(original)
    (proj/"source_manifest.json").write_text(json.dumps({
        "project_id":project_id,
        "status":"VERIFIED",
        "reason_codes":[],
        "verified_takeoff_items":[],
        "source_documents":[{
            "name":"evidence.pdf",
            "sha256":hashlib.sha256(original).hexdigest(),
            "size_bytes":len(original),
        }],
    }),encoding="utf-8")

    def sealed_stage_after_source_read(*args,**kwargs):
        source.write_bytes(b"%PDF-other-after-first-source-hash")
        return False,None,["sealed_run_missing"]
    monkeypatch.setattr(readiness,"_sealed_run_proof",sealed_stage_after_source_read)
    result=readiness.diagnostic_report(
        root,tmp_path/"produced",source_root=source_root,sealed_root=tmp_path/"sealed",
    )["projects"][0]
    assert result["source_sha_verified"] is False
    assert result["reconciliation_complete"] is False
    assert result["first_failing_authority_stage"]=="ORIGINAL_SOURCE_SHA_AUTHORITY"
    assert "source_changed_during_readiness" in result["blockers"]
    assert "source_file_size_mismatch:evidence.pdf" in result["blockers"]
    assert result["coverage_accuracy"] is None
    assert result["precision_adjusted_accuracy"] is None



def test_produced_item_replaced_after_initial_parse_invalidates_readiness(
    tmp_path, monkeypatch
):
    import json
    import scripts.report_full_plan_v2_readiness as readiness

    project_id = "synthetic_original_source_proof"
    root = tmp_path / "frozen_fixture"
    project_dir = root / "projects" / project_id
    project_dir.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "projects": [project_id], "required_project_count": 1,
    }), encoding="utf-8")
    (project_dir / "source_manifest.json").write_text(json.dumps({
        "project_id": project_id, "status": "VERIFIED",
        "source_documents": [{"name": "original.pdf", "sha256": "a"*64,
                              "size_bytes": 4}],
        "reason_codes": [], "verified_takeoff_items": [],
    }), encoding="utf-8")
    produced_root = tmp_path / "produced"
    produced_path = produced_root / project_id / "produced_items.json"
    produced_path.parent.mkdir(parents=True)
    produced_path.write_text('[{"quantity_id":"q1","value":3.0}]', encoding="utf-8")

    monkeypatch.setattr(readiness, "_source_sha_proof",
                        lambda *_args: (True, []))
    def rotated_after_initial_read(*args, **kwargs):
        produced_path.write_text('[{"quantity_id":"q2","value":99.0}]',
                                 encoding="utf-8")
        return True, 1, []
    monkeypatch.setattr(readiness, "_sealed_run_proof",
                        rotated_after_initial_read)
    monkeypatch.setattr(readiness, "_sealed_projection_proof",
                        lambda *_args, **_kwargs: (True, []))

    project = readiness.diagnostic_report(
        root, produced_root,
        source_root=tmp_path / "original",
        sealed_root=tmp_path / "sealed",
    )["projects"][0]
    assert "produced_items_changed_during_readiness" in project["blockers"]
    assert project["first_failing_authority_stage"] == "PRODUCED_ITEMS"
    assert project["first_failing_authority_reason"] == "produced_items_changed_during_readiness"
    assert project["reconciliation_complete"] is False
    assert project["coverage_accuracy"] is None
    assert project["precision_adjusted_accuracy"] is None
