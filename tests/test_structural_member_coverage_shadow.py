from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_structural_member_authority import (
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)
from pb_structural_member_coverage_shadow import (
    collect_structural_member_coverage_shadow,
    empty_structural_member_coverage_shadow,
)


def _physical_verandah_pdf(
    tmp_path: Path,
    *,
    filename: str = "physical_verandah.pdf",
    centers: tuple[float, ...] = (160.0, 260.0, 360.0, 460.0),
) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)
    page.insert_text((275, 226), "VERANDAH", fontsize=10)
    for x in (198.0, 298.0, 398.0):
        page.insert_text((x, 275), "2,500", fontsize=8)
    for x in centers:
        page.draw_rect(
            fitz.Rect(x - 2.0, 248.0, x + 2.0, 252.0),
            color=(0.4, 0.4, 0.4),
            fill=(0.8, 0.8, 0.8),
            width=0.5,
        )
    path = tmp_path / filename
    doc.save(str(path))
    doc.close()
    return path


def _text_only_verandah_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)
    for x in (198.0, 298.0, 398.0):
        page.insert_text((x, 220), "2,500", fontsize=8)
        page.insert_text((x, 270), "2,500", fontsize=8)
    page.insert_text((275, 245), "VERANDAH", fontsize=10)
    page.insert_text((255, 290), "100mm RHS Steel Poles", fontsize=8)
    path = tmp_path / "text_only_verandah.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _plain_plan_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)
    path = tmp_path / "plain_plan.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _pred_map(extractor: GenericPlanReaderExtractor, path: Path) -> dict:
    return {p.tag: p for p in extractor.extract_from_pdf(path)}


def test_constructor_starts_with_explicit_not_collected_shadow():
    extractor = GenericPlanReaderExtractor()
    assert extractor.structural_member_coverage_shadow == {
        "status": "abstained",
        "reason_codes": ["not_collected"],
        "registry_run_id": None,
        "physical_member_ids": [],
        "quantity_id": None,
        "object_universe_snapshot": None,
        "quantity_evidence": None,
        "coverage_registry_summary": None,
    }


def test_complete_physical_supports_populate_exact_shadow_without_changing_prediction(
    tmp_path: Path,
):
    path = _physical_verandah_pdf(tmp_path)
    extractor = GenericPlanReaderExtractor()
    pred_map = _pred_map(extractor, path)

    assert pred_map["verandah_pillars"].quantity == 4.0
    shadow = extractor.structural_member_coverage_shadow
    assert shadow["status"] == "corroborated"
    assert shadow["object_universe_snapshot"]["enumeration_status"] == "COMPLETE"
    assert shadow["quantity_evidence"]["abstained"] is False
    assert shadow["quantity_evidence"]["value"] == 4.0

    prediction_ids = tuple(sorted(pred_map["verandah_pillars"].metadata["physical_member_ids"]))
    snapshot_ids = tuple(shadow["object_universe_snapshot"]["admitted_object_ids"])
    quantity_ids = tuple(shadow["quantity_evidence"]["input_entity_ids"])
    assert snapshot_ids == prediction_ids
    assert quantity_ids == prediction_ids
    assert shadow["physical_member_ids"] == list(prediction_ids)
    assert shadow["quantity_id"] == shadow["quantity_evidence"]["quantity_id"]

    source_sha = pred_map["verandah_pillars"].metadata["source_sha256"]
    assert shadow["registry_run_id"] == f"extractor-structural:{source_sha}"
    assert shadow["object_universe_snapshot"]["source_sha256"] == source_sha

    summary = shadow["coverage_registry_summary"]
    quantity_id = shadow["quantity_id"]
    category = shadow["object_universe_snapshot"]["category"]
    assert summary["manifest"]["expected_object_universe_keys"] == [
        ["structural_member", category]
    ]
    assert summary["object_counts_by_coverage_state"]["PARTIAL"] == 4
    assert summary["object_ids_by_coverage_state"]["PARTIAL"] == list(prediction_ids)
    assert summary["quantity_ids_by_census_state"]["DANGLING_QUANTITY"] == [quantity_id]
    assert summary["quantity_evidence_universe_complete"] is True
    assert summary["takeoff_output_row_universe_complete"] is False
    assert summary["quantity_census_conclusive"] is False
    assert summary["takeoff_output_row_universe_snapshots"][0]["enumeration_status"] == (
        "NOT_ENUMERATED"
    )
    assert summary["takeoff_output_row_universe_snapshots"][0]["reason_codes"] == [
        "expected_takeoff_row_universe_snapshot_missing"
    ]
    assert all(record["quantity_ids"] == [quantity_id] for record in summary["object_records"])
    assert all(record["takeoff_row_ids"] == [] for record in summary["object_records"])


def test_text_only_support_evidence_never_becomes_complete_or_firm(tmp_path: Path):
    path = _text_only_verandah_pdf(tmp_path)
    extractor = GenericPlanReaderExtractor()
    pred_map = _pred_map(extractor, path)

    assert "verandah_pillars" not in pred_map
    shadow = extractor.structural_member_coverage_shadow
    assert shadow["status"] != "corroborated"
    assert shadow["object_universe_snapshot"]["enumeration_status"] == "INCOMPLETE"
    assert shadow["object_universe_snapshot"]["admitted_object_ids"] == []
    assert shadow["quantity_evidence"]["abstained"] is True
    assert shadow["quantity_evidence"]["value"] is None
    assert shadow["quantity_evidence"]["input_entity_ids"] == []


def test_shadow_collection_failure_cannot_change_live_prediction(tmp_path: Path, monkeypatch):
    import pb_structural_member_coverage_shadow as shadow_module

    path = _physical_verandah_pdf(tmp_path, filename="shadow_failure.pdf")
    enabled_extractor = GenericPlanReaderExtractor()
    enabled_predictions = [
        prediction.to_dict() for prediction in enabled_extractor.extract_from_pdf(path)
    ]
    assert enabled_extractor.structural_member_coverage_shadow["status"] == "corroborated"

    def explode(*args, **kwargs):
        raise RuntimeError("synthetic shadow failure")

    monkeypatch.setattr(
        shadow_module,
        "collect_structural_member_coverage_shadow",
        explode,
    )
    extractor = GenericPlanReaderExtractor()
    pred_map = _pred_map(extractor, path)

    assert [prediction.to_dict() for prediction in pred_map.values()] == enabled_predictions
    assert pred_map["verandah_pillars"].quantity == 4.0
    assert pred_map["verandah_pillars"].metadata["derivation"] == (
        "physical_structural_member_authority"
    )
    assert extractor.structural_member_coverage_shadow == {
        "status": "abstained",
        "reason_codes": ["shadow_collection_failed"],
        "registry_run_id": None,
        "physical_member_ids": [],
        "quantity_id": None,
        "object_universe_snapshot": None,
        "quantity_evidence": None,
        "coverage_registry_summary": None,
    }


def test_shadow_resets_between_documents_when_extractor_is_reused(tmp_path: Path):
    physical = _physical_verandah_pdf(tmp_path, filename="first.pdf")
    plain = _plain_plan_pdf(tmp_path)
    extractor = GenericPlanReaderExtractor()

    first = _pred_map(extractor, physical)
    assert first["verandah_pillars"].quantity == 4.0
    assert extractor.structural_member_coverage_shadow["status"] == "corroborated"

    _pred_map(extractor, plain)
    assert extractor.structural_member_coverage_shadow == {
        "status": "abstained",
        "reason_codes": ["not_collected"],
        "registry_run_id": None,
        "physical_member_ids": [],
        "quantity_id": None,
        "object_universe_snapshot": None,
        "quantity_evidence": None,
        "coverage_registry_summary": None,
    }


def test_shadow_collector_has_no_commercial_row_or_jobhub_dependency():
    path = Path(__file__).resolve().parents[1] / "pb_structural_member_coverage_shadow.py"
    text = path.read_text(encoding="utf-8")
    assert "pb_quantity_takeoff_adapter" not in text
    assert "pb_takeoff_output_authority" not in text
    assert "pb_planreader_jobhub_publish_contract" not in text
    assert "TakeoffOutputRow" not in text


def _producer_resolution():
    selector = StructuralMemberSelector(
        document_id="doc-coverage",
        revision_id="rev-coverage",
        source_sha256="a" * 64,
        snapshot_id="snapshot-coverage",
        decision_scope_id="scope-coverage",
        member_kind="pier",
    )
    observations = tuple(
        StructuralMemberObservation(
            observation_id=f"obs-{index}",
            member_kind="pier",
            page_id="1",
            view_id="plan-1",
            view_type="plan",
            source_evidence_ids=(f"evidence-{index}",),
            source_primitive_ids=(f"primitive-{index}",),
        )
        for index in range(2)
    )
    return StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        observations=observations,
        view_scopes=(StructuralMemberViewScope("1", "plan-1", "plan", True),),
    ).publish()


def test_collector_preserves_exact_producer_lineage_and_is_replayable():
    resolution = _producer_resolution()
    before = copy.deepcopy(resolution)
    first = collect_structural_member_coverage_shadow(resolution, registry_run_id="run-1")
    replay = collect_structural_member_coverage_shadow(resolution, registry_run_id="run-1")
    expected_ids = sorted(member.physical_member_id for member in resolution.members)
    assert first == replay
    assert first["status"] == "corroborated"
    assert first["physical_member_ids"] == expected_ids
    assert first["quantity_evidence"]["input_entity_ids"] == expected_ids
    assert first["object_universe_snapshot"]["admitted_object_ids"] == expected_ids
    assert first["object_universe_snapshot"]["source_document_id"] == "doc-coverage"
    assert first["quantity_evidence"]["metadata"]["snapshot_id"] == "snapshot-coverage"
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    assert resolution == before


def test_diagnostic_sink_retains_original_typed_quantity_without_changing_shadow_payload():
    resolution = _producer_resolution()
    before = copy.deepcopy(resolution)
    original = collect_structural_member_coverage_shadow(resolution, registry_run_id="run-sink")
    retained = []
    captured = collect_structural_member_coverage_shadow(
        resolution, registry_run_id="run-sink", quantity_evidence_sink=retained.append,
    )
    assert len(retained) == 1
    assert retained[0].to_dict() == original["quantity_evidence"]
    assert retained[0].input_entity_ids == tuple(original["physical_member_ids"])
    assert captured == original
    assert resolution == before


@pytest.mark.parametrize("defect", ["blank_id", "duplicate_id", "wrong_kind", "no_members"])
def test_malformed_corroborated_result_cannot_keep_corroborated_shadow(defect):
    resolution = _producer_resolution()
    member = resolution.members[0]
    members = {
        "blank_id": (replace(member, physical_member_id=""),),
        "duplicate_id": (member, member),
        "wrong_kind": (replace(member, member_kind="beam"),),
        "no_members": (),
    }[defect]
    malformed = replace(resolution, members=members)
    payload = collect_structural_member_coverage_shadow(malformed, registry_run_id="run-1")
    assert payload["status"] == "abstained"
    assert "structural_member_enumeration_identity_invalid" in payload["reason_codes"]
    assert "structural_member_physical_identity_invalid" in payload["reason_codes"]
    assert payload["physical_member_ids"] == []
    assert payload["object_universe_snapshot"]["enumeration_status"] == "INCOMPLETE"
    assert payload["quantity_evidence"]["abstained"] is True
    assert payload["quantity_evidence"]["value"] is None


@pytest.mark.parametrize("status", [
    EvidenceResolutionStatus.ABSTAINED,
    EvidenceResolutionStatus.CONFLICT,
    EvidenceResolutionStatus.CANDIDATE,
])
def test_blocked_producer_reason_and_status_survive_shadow(status):
    resolution = replace(
        _producer_resolution(), status=status, members=(), reason_codes=("source-blocker",)
    )
    payload = collect_structural_member_coverage_shadow(resolution, registry_run_id="run-1")
    assert payload["status"] == status.value
    assert "source-blocker" in payload["reason_codes"]
    assert "structural_member_enumeration_incomplete" in payload["reason_codes"]
    assert payload["quantity_evidence"]["abstained"] is True
    assert payload["physical_member_ids"] == []


def test_invalid_status_string_cannot_be_treated_as_typed_corroboration():
    malformed = replace(_producer_resolution(), status="corroborated")
    payload = collect_structural_member_coverage_shadow(malformed, registry_run_id="run-1")
    assert payload["status"] == "abstained"
    assert "structural_member_resolution_status_invalid" in payload["reason_codes"]
    assert payload["quantity_evidence"]["value"] is None
    assert payload["physical_member_ids"] == []


def test_quantity_lineage_blocker_downgrades_shadow_without_changing_producer():
    resolution = _producer_resolution()
    malformed = replace(
        resolution, selector=replace(resolution.selector, decision_scope_id="")
    )
    payload = collect_structural_member_coverage_shadow(malformed, registry_run_id="run-1")
    assert payload["status"] == "abstained"
    assert "structural_member_selector_lineage_invalid" in payload["reason_codes"]
    assert payload["quantity_evidence"]["value"] is None
    assert malformed.status is EvidenceResolutionStatus.CORROBORATED


@pytest.mark.parametrize("value", [None, {}, ("physical-member",)])
def test_collector_rejects_caller_supplied_objects(value):
    with pytest.raises(TypeError, match="StructuralMemberResolution"):
        collect_structural_member_coverage_shadow(value, registry_run_id="run-1")


def test_collector_rejects_unbound_run_and_source_lineage():
    resolution = _producer_resolution()
    with pytest.raises(ValueError):
        collect_structural_member_coverage_shadow(resolution, registry_run_id=" ")
    malformed = replace(
        resolution, selector=replace(resolution.selector, source_sha256="bad-source")
    )
    with pytest.raises(ValueError):
        collect_structural_member_coverage_shadow(malformed, registry_run_id="run-1")


def test_empty_shadow_payloads_do_not_share_mutable_state():
    first = empty_structural_member_coverage_shadow()
    first["physical_member_ids"].append("caller-object")
    assert empty_structural_member_coverage_shadow()["physical_member_ids"] == []
