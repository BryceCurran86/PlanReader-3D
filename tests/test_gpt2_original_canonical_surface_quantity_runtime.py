"""Canonical source-to-live-coverage retention; never automatic customer minting."""
from __future__ import annotations

from dataclasses import replace
import copy

import pytest

import pb_live_canonical_surface_quantity_retention as retention
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with, _source_area,
)
from tests.test_live_ceiling_area_quantity_publication import (
    _result, _ceiling, _shadow_quantity,
)


def _runtime_category(objects, source_quantities, canonical_quantities, family):
    summaries, gaps = collect_live_canonical_coverage(
        objects=objects,
        quantities=(*source_quantities, *canonical_quantities),
        output_rows=(),
        registry_run_scope="gpt2-original-runtime-family-retention",
    )
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    return report["family_reports"][family]


def test_original_floor_canonical_quantity_reaches_live_quantified_without_customer():
    claim = _claim_with(_source_area())
    baseline = copy.deepcopy([floor.to_dict() for floor in claim.canonical_floors])
    source_baseline = copy.deepcopy(
        [q.to_dict() for q in claim.room_area_quantity_evidence]
    )
    output = retention.live_floor_area_coverage_quantities(claim)
    assert len(output) == 1
    assert output[0].family == "floor_area"
    assert output[0].input_entity_ids == (claim.canonical_floors[0].physical_floor_surface_id,)
    family = _runtime_category(
        claim.canonical_floors, claim.room_area_quantity_evidence,
        output, "floor_slab",
    )
    assert family["stage_counts"]["QUANTIFIED"] == 1
    assert family["stage_counts"]["PUBLISHED"] == 0
    assert [floor.to_dict() for floor in claim.canonical_floors] == baseline
    assert [q.to_dict() for q in claim.room_area_quantity_evidence] == source_baseline


def test_original_ceiling_canonical_quantity_reaches_live_quantified_without_customer():
    result = _result()
    original = copy.deepcopy(result.canonical_ceilings[0].to_dict())
    output = retention.live_ceiling_area_coverage_quantities(result)
    assert len(output) == 1
    assert output[0].family == "ceiling_lining"
    assert output[0].input_entity_ids == (result.canonical_ceilings[0].canonical_ceiling_id,)
    family = _runtime_category(
        result.canonical_ceilings, result.quantity_evidence,
        output, "ceiling",
    )
    assert family["stage_counts"]["QUANTIFIED"] == 1
    assert family["stage_counts"]["PUBLISHED"] == 0
    assert result.canonical_ceilings[0].to_dict() == original


def test_provisional_floor_does_not_become_metric_or_firm_in_live_coverage():
    claim = _claim_with()
    assert retention.live_floor_area_coverage_quantities(claim) == ()
    family = _runtime_category(
        claim.canonical_floors, claim.room_area_quantity_evidence,
        (), "floor_slab",
    )
    assert family["stage_counts"]["QUANTIFIED"] == 0


def test_blocked_ceiling_does_not_become_metric_or_firm_in_live_coverage():
    bad_shadow = replace(_shadow_quantity(), metadata={
        **_shadow_quantity().metadata, "upstream_area_quantity_id": "foreign",
    })
    result = _result(shadow=bad_shadow)
    assert retention.live_ceiling_area_coverage_quantities(result) == ()
    family = _runtime_category(
        result.canonical_ceilings, result.quantity_evidence, (), "ceiling",
    )
    assert family["stage_counts"]["QUANTIFIED"] == 0


@pytest.mark.parametrize("defect", [
    "wrong_sha", "wrong_revision", "wrong_owner",
    "wrong_canonical", "wrong_document", "missing_evidence",
    "blocked", "wrong_family",
])
def test_floor_runtime_rejects_forged_or_partial_publisher_handoff(monkeypatch, defect):
    claim = _claim_with(_source_area())
    good = retention.live_floor_area_coverage_quantities(claim)[0]
    metadata = dict(good.metadata)
    changes = {}
    if defect == "wrong_sha":
        metadata["source_sha256"] = "b" * 64
    elif defect == "wrong_revision":
        metadata["revision_id"] = "other-revision"
    elif defect == "wrong_owner":
        changes["input_entity_ids"] = ("different-physical-floor",)
    elif defect == "wrong_canonical":
        metadata["canonical_floor_id"] = "other-canonical-floor"
    elif defect == "wrong_document":
        metadata["document_id"] = "alien-original-document"
    elif defect == "missing_evidence":
        changes["evidence_ids"] = ("foreign-source-receipt",)
    elif defect == "blocked":
        changes["blocking_reasons"] = ("unresolved_room_area_source",)
    else:
        changes["family"] = "ceiling_lining"
    if metadata != good.metadata:
        changes["metadata"] = metadata
    counterfeit = replace(good, **changes)
    monkeypatch.setattr(
        retention, "publish_live_floor_area_quantities",
        lambda _claim: (counterfeit,),
    )
    with pytest.raises(ValueError):
        retention.live_floor_area_coverage_quantities(claim)


@pytest.mark.parametrize("defect", [
    "wrong_sha", "wrong_revision", "wrong_owner",
    "wrong_canonical", "wrong_document", "abstained",
])
def test_ceiling_runtime_rejects_forged_or_partial_publisher_handoff(monkeypatch, defect):
    result = _result()
    good = retention.live_ceiling_area_coverage_quantities(result)[0]
    metadata = dict(good.metadata)
    changes = {}
    if defect == "wrong_sha":
        metadata["source_sha256"] = "b" * 64
    elif defect == "wrong_revision":
        metadata["revision_id"] = "another"
    elif defect == "wrong_owner":
        changes["input_entity_ids"] = ("different-ceiling",)
    elif defect == "wrong_canonical":
        metadata["canonical_ceiling_id"] = "another-ceiling"
    elif defect == "wrong_document":
        metadata["document_id"] = "foreign"
    else:
        changes["abstained"] = True
    if metadata != good.metadata:
        changes["metadata"] = metadata
    counterfeit = replace(good, **changes)
    monkeypatch.setattr(
        retention, "publish_live_ceiling_area_quantities",
        lambda _result: (counterfeit,),
    )
    with pytest.raises(ValueError):
        retention.live_ceiling_area_coverage_quantities(result)


@pytest.mark.parametrize("family", ["floor", "ceiling"])
def test_canonical_runtime_does_not_erase_distinct_source_and_metric_quantity_ids(family):
    if family == "floor":
        claim = _claim_with(_source_area())
        original = claim.room_area_quantity_evidence
        final = retention.live_floor_area_coverage_quantities(claim)
    else:
        result = _result()
        original = result.quantity_evidence
        final = retention.live_ceiling_area_coverage_quantities(result)
    assert len(original) == len(final) == 1
    assert original[0].quantity_id != final[0].quantity_id
    assert original[0].evidence_ids
    assert final[0].evidence_ids
    assert original[0].value == final[0].value


def test_duplicate_published_canonical_quantity_is_rejected_not_last_writer_wins(monkeypatch):
    claim = _claim_with(_source_area())
    good = retention.live_floor_area_coverage_quantities(claim)[0]
    monkeypatch.setattr(
        retention, "publish_live_floor_area_quantities",
        lambda _claim: (good, good),
    )
    with pytest.raises(ValueError, match="invalid published canonical floor_area quantity"):
        retention.live_floor_area_coverage_quantities(claim)


def test_runtime_live_extractor_wires_both_authoritative_family_adapters():
    """Active extractor path, not a standalone dead-end test-only helper."""
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "pb_planreader_pdf_extractor.py").read_text()
    tree = ast.parse(source)
    called = {
        call.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for call in (node,)
        if isinstance(call.func, ast.Name)
    }
    assert "live_floor_area_coverage_quantities" in called
    assert "live_ceiling_area_coverage_quantities" in called
    assert "collect_live_canonical_coverage" in called
