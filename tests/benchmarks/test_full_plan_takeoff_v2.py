from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_EVALUATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "evaluator.py"
)
_SPEC = importlib.util.spec_from_file_location("full_plan_takeoff_v2_evaluator", _EVALUATOR_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

from full_plan_takeoff_v2_evaluator import (
    MATCHED_OUTSIDE_TOLERANCE,
    MATCHED_WITHIN_TOLERANCE,
    MISSED,
    PARTIAL,
    PROJECT_INCOMPLETE,
    PROJECT_NOT_CONFIGURED,
    PROJECT_VERIFIED,
    UNRESOLVED,
    ProducedTakeoffItemV2,
    ProjectBenchmarkManifestV2,
    SourceDocumentV2,
    VerifiedTakeoffItemV2,
    evaluate_project_v2,
    evaluate_suite_v2,
)

SHA = "a" * 64


def doc(name: str = "plans.pdf") -> SourceDocumentV2:
    return SourceDocumentV2(
        name=name,
        role="architectural_drawings",
        sha256=SHA,
        size_bytes=100,
        page_count=2,
    )
def item(
    item_id: str = "paint-1",
    *,
    refs=("surface-a", "surface-b"),
    expected=100.0,
    tolerance=0.05,
    unit="m2",
    trade="painting",
    denominator_eligible=True,
) -> VerifiedTakeoffItemV2:
    return VerifiedTakeoffItemV2(
        item_id=item_id,
        project_id="project-a",
        description="Verified paint area",
        trade_category=trade,
        unit=unit,
        expected_quantity=expected,
        tolerance_fraction=tolerance,
        expected_object_refs=refs,
        denominator_eligible=denominator_eligible,
    )


def verified_manifest(*items: VerifiedTakeoffItemV2) -> ProjectBenchmarkManifestV2:
    return ProjectBenchmarkManifestV2(
        project_id="project-a",
        status=PROJECT_VERIFIED,
        source_package_complete=True,
        source_documents=(doc(),),
        reference_takeoff_documents=(doc("takeoff.pdf"),),
        verified_items=items or (item(),),
    )


def produced(
    quantity_id: str = "q1",
    *,
    refs=("surface-a", "surface-b"),
    value=100.0,
    unit="m2",
    trade="painting",
    lineage_ok=True,
) -> ProducedTakeoffItemV2:
    return ProducedTakeoffItemV2(
        quantity_id=quantity_id,
        trade_category=trade,
        value=value,
        unit=unit,
        object_refs=refs,
        lineage_ok=lineage_ok,
    )
def test_exact_surface_set_and_quantity_within_tolerance_matches():
    result = evaluate_project_v2(verified_manifest(item()), (produced(value=103.0),))
    assert result.denominator == 1
    assert result.matched_within_tolerance == 1
    assert result.coverage_accuracy == pytest.approx(1.0)
    assert result.item_results[0].state == MATCHED_WITHIN_TOLERANCE
    assert result.unsupported_extra == 0


def test_equal_numeric_value_on_wrong_surfaces_is_not_a_match():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (produced(refs=("surface-x", "surface-y"), value=100.0),),
    )
    assert result.item_results[0].state == MISSED
    assert result.matched_within_tolerance == 0
    assert result.unsupported_extra == 1
    assert result.coverage_accuracy == pytest.approx(0.0)


def test_equal_surfaces_and_value_in_wrong_trade_is_not_a_match():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (produced(trade="plastering", value=100.0),),
    )
    assert result.item_results[0].state == MISSED
    assert result.matched_within_tolerance == 0
    assert result.unsupported_extra == 1


def test_partial_expected_surface_closure_is_partial():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (produced(refs=("surface-a",), value=50.0),),
    )
    assert result.item_results[0].state == PARTIAL
    assert result.partial == 1
    assert result.unsupported_extra == 0


def test_extra_overlapping_claim_is_unsupported_when_exact_match_exists():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (
            produced("q-exact", value=100.0),
            produced(
                "q-extra",
                refs=("surface-a", "surface-unverified"),
                value=50.0,
            ),
        ),
    )
    assert result.item_results[0].state == MATCHED_WITHIN_TOLERANCE
    assert result.unsupported_extra == 1
    assert result.unsupported_quantity_ids == ("q-extra",)
    assert result.coverage_accuracy == pytest.approx(1.0)
    assert result.precision_adjusted_accuracy == pytest.approx(0.5)


def test_duplicate_exact_surface_claims_are_unresolved():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (
            produced("q1", value=100.0),
            produced("q2", value=100.0),
        ),
    )
    assert result.item_results[0].state == UNRESOLVED
    assert result.unresolved == 1


def test_duplicate_produced_quantity_ids_fail_closed():
    with pytest.raises(ValueError, match="produced quantity ids must be unique"):
        evaluate_project_v2(
            verified_manifest(item()),
            (
                produced("q-duplicate", value=100.0),
                produced("q-duplicate", refs=("surface-x",), value=50.0),
            ),
        )
def test_exact_surfaces_outside_tolerance_is_not_accepted():
    result = evaluate_project_v2(
        verified_manifest(item(expected=100.0, tolerance=0.05)),
        (produced(value=120.0),),
    )
    assert result.item_results[0].state == MATCHED_OUTSIDE_TOLERANCE
    assert result.matched_outside_tolerance == 1
    assert result.coverage_accuracy == pytest.approx(0.0)


def test_lineage_conflict_cannot_match_even_with_right_surfaces_and_value():
    result = evaluate_project_v2(
        verified_manifest(item()),
        (produced(value=100.0, lineage_ok=False),),
    )
    assert result.item_results[0].state == MISSED
    assert result.matched_within_tolerance == 0


def test_verified_manifest_requires_reference_takeoff_and_items():
    with pytest.raises(ValueError):
        ProjectBenchmarkManifestV2(
            project_id="project-a",
            status=PROJECT_VERIFIED,
            source_package_complete=True,
            source_documents=(doc(),),
            reference_takeoff_documents=(),
            verified_items=(item(),),
        )


def test_verified_manifest_requires_complete_source_package():
    with pytest.raises(ValueError, match="complete source package"):
        ProjectBenchmarkManifestV2(
            project_id="project-a",
            status=PROJECT_VERIFIED,
            source_package_complete=False,
            source_documents=(doc(),),
            reference_takeoff_documents=(doc("takeoff.pdf"),),
            verified_items=(item(),),
        )


def test_verified_manifest_requires_denominator_item():
    with pytest.raises(ValueError, match="denominator-eligible"):
        verified_manifest(item(denominator_eligible=False))


def test_denominator_identity_must_be_unique():
    with pytest.raises(ValueError, match="unique trade/unit/object identity"):
        verified_manifest(item("paint-a"), item("paint-b"))


def test_incomplete_manifest_is_not_scored():
    manifest = ProjectBenchmarkManifestV2(
        project_id="project-a",
        status=PROJECT_INCOMPLETE,
        source_package_complete=True,
        source_documents=(doc(),),
        reference_takeoff_documents=(),
        verified_items=(),
        reason_codes=("reference_takeoff_not_supplied",),
    )
    result = evaluate_project_v2(manifest, (produced(),))
    assert result.coverage_accuracy is None
    assert result.denominator == 0
def _manifest_for(project_id: str, status: str) -> ProjectBenchmarkManifestV2:
    if status == PROJECT_VERIFIED:
        verified_item = VerifiedTakeoffItemV2(
            item_id=f"{project_id}-paint",
            project_id=project_id,
            description="Paint area",
            trade_category="painting",
            unit="m2",
            expected_quantity=10.0,
            tolerance_fraction=0.05,
            expected_object_refs=(f"{project_id}-surface",),
        )
        return ProjectBenchmarkManifestV2(
            project_id=project_id,
            status=status,
            source_package_complete=True,
            source_documents=(doc(f"{project_id}.pdf"),),
            reference_takeoff_documents=(doc(f"{project_id}-takeoff.pdf"),),
            verified_items=(verified_item,),
        )
    return ProjectBenchmarkManifestV2(
        project_id=project_id,
        status=status,
        source_package_complete=status != PROJECT_NOT_CONFIGURED,
        source_documents=() if status == PROJECT_NOT_CONFIGURED else (doc(),),
        reference_takeoff_documents=(),
        verified_items=(),
        reason_codes=("new_project_not_supplied",),
    )


def test_four_of_five_never_publishes_a_five_project_headline():
    manifests = tuple(
        _manifest_for(f"p{i}", PROJECT_VERIFIED) for i in range(1, 5)
    ) + (_manifest_for("p5", PROJECT_NOT_CONFIGURED),)
    produced_by_project = {
        f"p{i}": (
            ProducedTakeoffItemV2(
                quantity_id=f"q{i}",
                trade_category="painting",
                value=10.0,
                unit="m2",
                object_refs=(f"p{i}-surface",),
            ),
        )
        for i in range(1, 5)
    }
    result = evaluate_suite_v2(
        manifests,
        produced_by_project,
        evaluated_source_sha256s_by_project={
            f"p{i}": (SHA,) for i in range(1, 5)
        },
        reconciliation_complete_by_project={
            f"p{i}": True for i in range(1, 5)
        },
    )
    assert result.publication_status == "UNPUBLISHED"
    assert result.development_status == "PROVISIONAL_4_OF_5"
    assert result.verified_projects == 4
    assert result.coverage_accuracy == pytest.approx(1.0)
    assert any("p5:new_project_not_supplied" in reason for reason in result.reason_codes)
def test_required_project_count_mismatch_fails_closed():
    manifests = tuple(_manifest_for(f"p{i}", PROJECT_VERIFIED) for i in range(1, 5))
    result = evaluate_suite_v2(manifests, {})
    assert result.publication_status == "UNPUBLISHED"
    assert "required_project_count_not_met" in result.reason_codes


def test_five_verified_projects_require_run_integrity_before_publish():
    manifests = tuple(_manifest_for(f"p{i}", PROJECT_VERIFIED) for i in range(1, 6))
    produced_by_project = {
        f"p{i}": (
            ProducedTakeoffItemV2(
                quantity_id=f"q{i}",
                trade_category="painting",
                value=10.0,
                unit="m2",
                object_refs=(f"p{i}-surface",),
            ),
        )
        for i in range(1, 6)
    }

    blocked = evaluate_suite_v2(manifests, produced_by_project)
    assert blocked.publication_status == "UNPUBLISHED"
    assert blocked.development_status == "VERIFIED_MANIFESTS_RUN_INCOMPLETE"
    assert blocked.coverage_accuracy is None
    assert any("source_hashes_not_verified" in reason for reason in blocked.reason_codes)
    assert any("object_reconciliation_incomplete" in reason for reason in blocked.reason_codes)

    published = evaluate_suite_v2(
        manifests,
        produced_by_project,
        evaluated_source_sha256s_by_project={
            f"p{i}": (SHA,) for i in range(1, 6)
        },
        reconciliation_complete_by_project={
            f"p{i}": True for i in range(1, 6)
        },
    )
    assert published.publication_status == "PUBLISHED"
    assert published.development_status == "COMPLETE"
    assert published.coverage_accuracy == pytest.approx(1.0)


def test_project_ids_must_be_unique():
    manifests = (
        _manifest_for("p1", PROJECT_INCOMPLETE),
        _manifest_for("p1", PROJECT_INCOMPLETE),
    )
    with pytest.raises(ValueError):
        evaluate_suite_v2(manifests, {})


def test_spreadsheet_reference_takeoff_does_not_require_page_count():
    source = SourceDocumentV2(
        name="verified_takeoff.xlsx",
        role="reference_takeoff",
        sha256=SHA,
        size_bytes=100,
        page_count=None,
    )
    assert source.page_count is None


def test_denominator_item_requires_verified_surface_object_refs():
    with pytest.raises(ValueError):
        VerifiedTakeoffItemV2(
            item_id="no-surface",
            project_id="project-a",
            description="Unmapped area",
            trade_category="painting",
            unit="m2",
            expected_quantity=10.0,
            tolerance_fraction=0.05,
            expected_object_refs=(),
        )
