"""Development scoreboard for the active Full Plan V2 benchmark.

This module intentionally does not relax the V2 publication gate. It scores only
independently VERIFIED, denominator-eligible truth items while projects are still
being source-closed, and publishes a development headline only after every
configured project has a sealed production-output file for the same run.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .evaluator import (
        MATCHED_WITHIN_TOLERANCE,
        PROJECT_VERIFIED,
        ProducedTakeoffItemV2,
        ProjectBenchmarkManifestV2,
        evaluate_project_v2,
    )
else:
    _path = Path(__file__).with_name("evaluator.py")
    _spec = importlib.util.spec_from_file_location("full_plan_takeoff_v2_evaluator", _path)
    assert _spec is not None and _spec.loader is not None
    _module = sys.modules.get(_spec.name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_spec.name] = _module
        _spec.loader.exec_module(_module)
    ProducedTakeoffItemV2 = _module.ProducedTakeoffItemV2
    ProjectBenchmarkManifestV2 = _module.ProjectBenchmarkManifestV2
    MATCHED_WITHIN_TOLERANCE = _module.MATCHED_WITHIN_TOLERANCE
    PROJECT_VERIFIED = _module.PROJECT_VERIFIED
    evaluate_project_v2 = _module.evaluate_project_v2


@dataclass(frozen=True)
class DevelopmentProjectResultV2:
    project_id: str
    manifest_status: str
    execution_present: bool
    truth_denominator: int
    matched_within_tolerance: int
    matched_outside_tolerance: int
    missed: int
    partial: int
    unresolved: int
    unsupported_extra: int
    abstained_outputs: int
    lineage_conflicts: int
    observed_accuracy: float | None
    precision_adjusted_accuracy: float | None


@dataclass(frozen=True)
class DevelopmentFailureLedgerItemV2:
    project_id: str
    item_id: str
    state: str
    trade_category: str
    unit: str
    produced_quantity_id: str | None
    error_fraction: float | None
    expected_object_refs: tuple[str, ...]
    matched_object_refs: tuple[str, ...]


@dataclass(frozen=True)
class DevelopmentUnsupportedOutputV2:
    project_id: str
    quantity_id: str
    trade_category: str
    unit: str
    object_refs: tuple[str, ...]


@dataclass(frozen=True)
class DevelopmentFailureLedgerV2:
    failure_items: tuple[DevelopmentFailureLedgerItemV2, ...]
    unsupported_outputs: tuple[DevelopmentUnsupportedOutputV2, ...]
    missing_execution_project_ids: tuple[str, ...]


@dataclass(frozen=True)
class DevelopmentSuiteResultV2:
    status: str
    configured_projects: int
    executed_projects: int
    source_closed_truth_items: int
    non_denominator_verified_controls: int
    executed_denominator: int
    execution_coverage: float | None
    matched_within_tolerance: int
    matched_outside_tolerance: int
    missed: int
    partial: int
    unresolved: int
    hallucinations: int
    abstained_outputs: int
    lineage_conflicts: int
    observed_accuracy: float | None
    development_accuracy: float | None
    precision_adjusted_accuracy: float | None
    project_results: tuple[DevelopmentProjectResultV2, ...]
    reason_codes: tuple[str, ...]


def _scorable_manifest(manifest: ProjectBenchmarkManifestV2) -> ProjectBenchmarkManifestV2 | None:
    """Return a VERIFIED facade containing only already-verified V2 truth."""
    denominator_items = tuple(
        item for item in manifest.verified_items if item.denominator_eligible
    )
    if (
        not denominator_items
        or not manifest.source_package_complete
        or not manifest.source_documents
        or not manifest.reference_takeoff_documents
    ):
        return None
    return ProjectBenchmarkManifestV2(
        project_id=manifest.project_id,
        status=PROJECT_VERIFIED,
        source_package_complete=True,
        source_documents=manifest.source_documents,
        reference_takeoff_documents=manifest.reference_takeoff_documents,
        verified_items=manifest.verified_items,
    )


def evaluate_development_project_v2(
    manifest: ProjectBenchmarkManifestV2,
    produced_items: Iterable[ProducedTakeoffItemV2],
    *,
    execution_present: bool,
) -> DevelopmentProjectResultV2:
    produced = tuple(produced_items)
    denominator = sum(item.denominator_eligible for item in manifest.verified_items)
    abstained = sum(row.abstained for row in produced)
    lineage_conflicts = sum(not row.lineage_ok for row in produced)

    if not execution_present:
        return DevelopmentProjectResultV2(
            project_id=manifest.project_id,
            manifest_status=manifest.status,
            execution_present=False,
            truth_denominator=denominator,
            matched_within_tolerance=0,
            matched_outside_tolerance=0,
            missed=0,
            partial=0,
            unresolved=0,
            unsupported_extra=0,
            abstained_outputs=0,
            lineage_conflicts=0,
            observed_accuracy=None,
            precision_adjusted_accuracy=None,
        )

    scorable = _scorable_manifest(manifest)
    if scorable is None:
        return DevelopmentProjectResultV2(
            project_id=manifest.project_id,
            manifest_status=manifest.status,
            execution_present=True,
            truth_denominator=denominator,
            matched_within_tolerance=0,
            matched_outside_tolerance=0,
            missed=0,
            partial=0,
            unresolved=denominator,
            unsupported_extra=0,
            abstained_outputs=abstained,
            lineage_conflicts=lineage_conflicts,
            observed_accuracy=None,
            precision_adjusted_accuracy=None,
        )

    result = evaluate_project_v2(scorable, produced)
    return DevelopmentProjectResultV2(
        project_id=manifest.project_id,
        manifest_status=manifest.status,
        execution_present=True,
        truth_denominator=result.denominator,
        matched_within_tolerance=result.matched_within_tolerance,
        matched_outside_tolerance=result.matched_outside_tolerance,
        missed=result.missed,
        partial=result.partial,
        unresolved=result.unresolved,
        unsupported_extra=result.unsupported_extra,
        abstained_outputs=abstained,
        lineage_conflicts=lineage_conflicts,
        observed_accuracy=result.coverage_accuracy,
        precision_adjusted_accuracy=result.precision_adjusted_accuracy,
    )


def build_development_failure_ledger_v2(
    manifests: Iterable[ProjectBenchmarkManifestV2],
    produced_by_project: dict[str, Iterable[ProducedTakeoffItemV2]],
) -> DevelopmentFailureLedgerV2:
    """Return exact evaluator failures without changing any score or truth.

    Missing project executions are reported separately instead of being
    mislabelled as MISSED denominator objects. For executed projects, item
    states come directly from the existing V2 evaluator. Matched-within-
    tolerance rows are omitted because this is a failure ledger.
    """
    manifest_tuple = tuple(manifests)
    if len({manifest.project_id for manifest in manifest_tuple}) != len(manifest_tuple):
        raise ValueError("project ids must be unique")

    produced_map = {
        str(project_id): tuple(rows)
        for project_id, rows in produced_by_project.items()
    }
    expected_ids = {manifest.project_id for manifest in manifest_tuple}
    unexpected_ids = tuple(sorted(set(produced_map) - expected_ids))
    if unexpected_ids:
        raise ValueError(
            "produced output contains unexpected projects: " + ", ".join(unexpected_ids)
        )

    failure_items: list[DevelopmentFailureLedgerItemV2] = []
    unsupported_outputs: list[DevelopmentUnsupportedOutputV2] = []
    missing_execution: list[str] = []

    for manifest in manifest_tuple:
        produced = produced_map.get(manifest.project_id)
        if produced is None:
            missing_execution.append(manifest.project_id)
            continue

        scorable = _scorable_manifest(manifest)
        if scorable is None:
            for item in manifest.verified_items:
                if not item.denominator_eligible:
                    continue
                failure_items.append(
                    DevelopmentFailureLedgerItemV2(
                        project_id=manifest.project_id,
                        item_id=item.item_id,
                        state="UNRESOLVED",
                        trade_category=item.trade_category,
                        unit=item.unit,
                        produced_quantity_id=None,
                        error_fraction=None,
                        expected_object_refs=item.expected_object_refs,
                        matched_object_refs=(),
                    )
                )
            continue

        result = evaluate_project_v2(scorable, produced)
        items_by_id = {
            item.item_id: item
            for item in scorable.verified_items
            if item.denominator_eligible
        }
        for item_result in result.item_results:
            if item_result.state == MATCHED_WITHIN_TOLERANCE:
                continue
            item = items_by_id[item_result.item_id]
            failure_items.append(
                DevelopmentFailureLedgerItemV2(
                    project_id=manifest.project_id,
                    item_id=item_result.item_id,
                    state=item_result.state,
                    trade_category=item.trade_category,
                    unit=item.unit,
                    produced_quantity_id=item_result.produced_quantity_id,
                    error_fraction=item_result.error_fraction,
                    expected_object_refs=item.expected_object_refs,
                    matched_object_refs=item_result.matched_object_refs,
                )
            )

        produced_by_id = {row.quantity_id: row for row in produced}
        for quantity_id in result.unsupported_quantity_ids:
            row = produced_by_id[quantity_id]
            unsupported_outputs.append(
                DevelopmentUnsupportedOutputV2(
                    project_id=manifest.project_id,
                    quantity_id=quantity_id,
                    trade_category=row.trade_category,
                    unit=row.unit,
                    object_refs=row.object_refs,
                )
            )

    return DevelopmentFailureLedgerV2(
        failure_items=tuple(
            sorted(failure_items, key=lambda row: (row.project_id, row.item_id))
        ),
        unsupported_outputs=tuple(
            sorted(
                unsupported_outputs,
                key=lambda row: (row.project_id, row.quantity_id),
            )
        ),
        missing_execution_project_ids=tuple(sorted(missing_execution)),
    )


def evaluate_development_suite_v2(
    manifests: Iterable[ProjectBenchmarkManifestV2],
    produced_by_project: dict[str, Iterable[ProducedTakeoffItemV2]],
) -> DevelopmentSuiteResultV2:
    manifest_tuple = tuple(manifests)
    if len({manifest.project_id for manifest in manifest_tuple}) != len(manifest_tuple):
        raise ValueError("project ids must be unique")

    produced_map = {
        str(project_id): tuple(rows)
        for project_id, rows in produced_by_project.items()
    }
    expected_ids = {manifest.project_id for manifest in manifest_tuple}
    unexpected_ids = tuple(sorted(set(produced_map) - expected_ids))
    if unexpected_ids:
        raise ValueError(
            "produced output contains unexpected projects: " + ", ".join(unexpected_ids)
        )

    projects = tuple(
        evaluate_development_project_v2(
            manifest,
            produced_map.get(manifest.project_id, ()),
            execution_present=manifest.project_id in produced_map,
        )
        for manifest in manifest_tuple
    )
    truth_denominator = sum(project.truth_denominator for project in projects)
    executed_projects = sum(project.execution_present for project in projects)
    executed_denominator = sum(
        project.truth_denominator for project in projects if project.execution_present
    )
    matched = sum(project.matched_within_tolerance for project in projects)
    outside = sum(project.matched_outside_tolerance for project in projects)
    missed = sum(project.missed for project in projects)
    partial = sum(project.partial for project in projects)
    unresolved = sum(project.unresolved for project in projects)
    extras = sum(project.unsupported_extra for project in projects)
    abstained = sum(project.abstained_outputs for project in projects)
    lineage_conflicts = sum(project.lineage_conflicts for project in projects)
    controls = sum(
        sum(not item.denominator_eligible for item in manifest.verified_items)
        for manifest in manifest_tuple
    )
    execution_coverage = (
        executed_denominator / truth_denominator if truth_denominator else None
    )
    observed_accuracy = (
        matched / executed_denominator if executed_denominator else None
    )

    reasons: list[str] = []
    missing = tuple(
        project.project_id for project in projects if not project.execution_present
    )
    reasons.extend(f"{project_id}:production_output_missing" for project_id in missing)
    if lineage_conflicts:
        reasons.append("lineage_conflict")
    if not truth_denominator:
        reasons.append("no_source_closed_truth_items")

    complete_execution = (
        bool(manifest_tuple)
        and executed_projects == len(manifest_tuple)
        and not lineage_conflicts
        and truth_denominator > 0
    )
    development_accuracy = observed_accuracy if complete_execution else None
    precision_denominator = truth_denominator + extras
    precision_adjusted = (
        matched / precision_denominator
        if complete_execution and precision_denominator
        else None
    )
    status = (
        "COMPLETE_CURRENT_TRUTH_SET"
        if complete_execution
        else "PARTIAL_OR_BLOCKED"
    )
    return DevelopmentSuiteResultV2(
        status=status,
        configured_projects=len(manifest_tuple),
        executed_projects=executed_projects,
        source_closed_truth_items=truth_denominator,
        non_denominator_verified_controls=controls,
        executed_denominator=executed_denominator,
        execution_coverage=execution_coverage,
        matched_within_tolerance=matched,
        matched_outside_tolerance=outside,
        missed=missed,
        partial=partial,
        unresolved=unresolved,
        hallucinations=extras,
        abstained_outputs=abstained,
        lineage_conflicts=lineage_conflicts,
        observed_accuracy=observed_accuracy,
        development_accuracy=development_accuracy,
        precision_adjusted_accuracy=precision_adjusted,
        project_results=projects,
        reason_codes=tuple(sorted(set(reasons))),
    )
