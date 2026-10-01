"""Leak-free evaluator for the full-plan takeoff reconciliation benchmark V2.

Evaluation truth enters only here, after production extraction has been sealed.
Matches are exact physical-object/surface identity joins; labels and numeric
similarity are never matching inputs.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

MATCHED_WITHIN_TOLERANCE = "MATCHED_WITHIN_TOLERANCE"
MATCHED_OUTSIDE_TOLERANCE = "MATCHED_OUTSIDE_TOLERANCE"
MISSED = "MISSED"
PARTIAL = "PARTIAL"
UNRESOLVED = "UNRESOLVED"
UNSUPPORTED_EXTRA = "UNSUPPORTED_EXTRA"
ITEM_STATES = (
    MATCHED_WITHIN_TOLERANCE,
    MATCHED_OUTSIDE_TOLERANCE,
    MISSED,
    PARTIAL,
    UNRESOLVED,
    UNSUPPORTED_EXTRA,
)

PROJECT_VERIFIED = "VERIFIED"
PROJECT_INCOMPLETE = "INCOMPLETE"
PROJECT_NOT_CONFIGURED = "NOT_CONFIGURED"
_PROJECT_STATES = {PROJECT_VERIFIED, PROJECT_INCOMPLETE, PROJECT_NOT_CONFIGURED}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
def _required(value: object, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{name} must be non-empty")
    return clean


def _tuple(values: Iterable[object], name: str) -> tuple[str, ...]:
    clean = tuple(sorted({_required(value, name) for value in values}))
    return clean


def _unit(value: object) -> str:
    return _required(value, "unit").strip().lower()


@dataclass(frozen=True)
class SourceDocumentV2:
    name: str
    role: str
    sha256: str
    size_bytes: int
    page_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required(self.name, "name"))
        object.__setattr__(self, "role", _required(self.role, "role"))
        sha = _required(self.sha256, "sha256").lower()
        if not _SHA256_RE.fullmatch(sha):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        object.__setattr__(self, "sha256", sha)
        if self.size_bytes <= 0:
            raise ValueError("source document size must be positive")
        if self.page_count is not None and self.page_count <= 0:
            raise ValueError("page_count must be positive when supplied")
@dataclass(frozen=True)
class VerifiedTakeoffItemV2:
    item_id: str
    project_id: str
    description: str
    trade_category: str
    unit: str
    expected_quantity: float
    tolerance_policy_id: str
    tolerance_fraction: float
    expected_object_refs: tuple[str, ...]
    source_document_refs: tuple[str, ...]
    source_location_refs: tuple[str, ...]
    denominator_eligible: bool = True
    verification_status: str = PROJECT_VERIFIED

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _required(self.item_id, "item_id"))
        object.__setattr__(self, "project_id", _required(self.project_id, "project_id"))
        object.__setattr__(self, "description", _required(self.description, "description"))
        object.__setattr__(
            self, "trade_category", _required(self.trade_category, "trade_category").lower()
        )
        object.__setattr__(self, "unit", _unit(self.unit))
        if not math.isfinite(self.expected_quantity) or self.expected_quantity < 0:
            raise ValueError("expected_quantity must be finite and non-negative")
        object.__setattr__(
            self,
            "tolerance_policy_id",
            _required(self.tolerance_policy_id, "tolerance_policy_id"),
        )
        if not math.isfinite(self.tolerance_fraction) or not 0 <= self.tolerance_fraction <= 1:
            raise ValueError("tolerance_fraction must be between 0 and 1")
        refs = _tuple(self.expected_object_refs, "expected_object_refs")
        source_docs = _tuple(self.source_document_refs, "source_document_refs")
        source_locations = _tuple(self.source_location_refs, "source_location_refs")
        if self.denominator_eligible and not refs:
            raise ValueError("denominator-eligible takeoff item requires expected_object_refs")
        object.__setattr__(self, "expected_object_refs", refs)
        object.__setattr__(self, "source_document_refs", source_docs)
        object.__setattr__(self, "source_location_refs", source_locations)
        if self.denominator_eligible and (not source_docs or not source_locations):
            raise ValueError(
                "denominator-eligible item requires reference document and location lineage"
            )
        status = _required(self.verification_status, "verification_status").upper()
        if status != PROJECT_VERIFIED:
            raise ValueError("takeoff items entering the denominator must be independently VERIFIED")
        object.__setattr__(self, "verification_status", status)


@dataclass(frozen=True)
class ProducedTakeoffItemV2:
    quantity_id: str
    trade_category: str
    value: float | None
    unit: str
    object_refs: tuple[str, ...]
    lineage_ok: bool = True
    abstained: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity_id", _required(self.quantity_id, "quantity_id"))
        object.__setattr__(
            self, "trade_category", _required(self.trade_category, "trade_category").lower()
        )
        object.__setattr__(self, "unit", _unit(self.unit))
        object.__setattr__(self, "object_refs", _tuple(self.object_refs, "object_refs"))
        if self.value is not None and (not math.isfinite(self.value) or self.value < 0):
            raise ValueError("produced value must be finite and non-negative")
@dataclass(frozen=True)
class ProjectBenchmarkManifestV2:
    project_id: str
    status: str
    source_package_complete: bool
    source_documents: tuple[SourceDocumentV2, ...]
    reference_takeoff_documents: tuple[SourceDocumentV2, ...]
    verified_items: tuple[VerifiedTakeoffItemV2, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        project_id = _required(self.project_id, "project_id")
        object.__setattr__(self, "project_id", project_id)
        status = _required(self.status, "status").upper()
        if status not in _PROJECT_STATES:
            raise ValueError(f"unknown project status: {status}")
        object.__setattr__(self, "status", status)
        if type(self.source_package_complete) is not bool:
            raise TypeError("source_package_complete must be bool")
        if any(item.project_id != project_id for item in self.verified_items):
            raise ValueError("verified item project_id must match manifest")
        ids = [item.item_id for item in self.verified_items]
        if len(ids) != len(set(ids)):
            raise ValueError("verified item ids must be unique")
        source_names = [doc.name for doc in self.source_documents]
        if len(source_names) != len(set(source_names)):
            raise ValueError("source document names must be unique")
        source_hashes = [doc.sha256 for doc in self.source_documents]
        if len(source_hashes) != len(set(source_hashes)):
            raise ValueError("source document hashes must be unique")
        reference_names = [doc.name for doc in self.reference_takeoff_documents]
        if len(reference_names) != len(set(reference_names)):
            raise ValueError("reference takeoff document names must be unique")
        reference_hashes = [doc.sha256 for doc in self.reference_takeoff_documents]
        if len(reference_hashes) != len(set(reference_hashes)):
            raise ValueError("reference takeoff document hashes must be unique")
        reference_name_set = set(reference_names)
        for item in self.verified_items:
            if not set(item.source_document_refs).issubset(reference_name_set):
                raise ValueError(
                    "verified item source_document_refs must name reference takeoff documents"
                )
        denominator_keys = [
            (item.trade_category, item.unit, item.expected_object_refs)
            for item in self.verified_items
            if item.denominator_eligible
        ]
        if len(denominator_keys) != len(set(denominator_keys)):
            raise ValueError(
                "denominator items must have unique trade/unit/object identity"
            )
        if status == PROJECT_VERIFIED:
            if not self.source_package_complete:
                raise ValueError("VERIFIED project requires complete source package")
            if not self.source_documents or not self.reference_takeoff_documents:
                raise ValueError("VERIFIED project requires source and reference takeoff documents")
            if not self.verified_items:
                raise ValueError("VERIFIED project requires verified takeoff items")
            if not any(item.denominator_eligible for item in self.verified_items):
                raise ValueError(
                    "VERIFIED project requires at least one denominator-eligible item"
                )
        if status != PROJECT_VERIFIED and not self.reason_codes:
            raise ValueError("non-VERIFIED project requires reason_codes")


@dataclass(frozen=True)
class ItemResultV2:
    item_id: str
    state: str
    produced_quantity_id: str | None
    error_fraction: float | None
    matched_object_refs: tuple[str, ...]
@dataclass(frozen=True)
class ProjectResultV2:
    project_id: str
    manifest_status: str
    denominator: int
    matched_within_tolerance: int
    matched_outside_tolerance: int
    missed: int
    partial: int
    unresolved: int
    unsupported_extra: int
    coverage_accuracy: float | None
    precision_adjusted_accuracy: float | None
    item_results: tuple[ItemResultV2, ...]
    unsupported_quantity_ids: tuple[str, ...]


@dataclass(frozen=True)
class SuiteResultV2:
    publication_status: str
    development_status: str
    configured_projects: int
    verified_projects: int
    denominator: int
    matched_within_tolerance: int
    unsupported_extra: int
    coverage_accuracy: float | None
    precision_adjusted_accuracy: float | None
    project_results: tuple[ProjectResultV2, ...]
    reason_codes: tuple[str, ...]


def _error_fraction(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else math.inf
    return abs(actual - expected) / expected


def evaluate_project_v2(
    manifest: ProjectBenchmarkManifestV2,
    produced_items: Iterable[ProducedTakeoffItemV2],
) -> ProjectResultV2:
    produced = tuple(produced_items)
    if manifest.status != PROJECT_VERIFIED:
        return ProjectResultV2(
            project_id=manifest.project_id,
            manifest_status=manifest.status,
            denominator=0,
            matched_within_tolerance=0,
            matched_outside_tolerance=0,
            missed=0,
            partial=0,
            unresolved=0,
            unsupported_extra=0,
            coverage_accuracy=None,
            precision_adjusted_accuracy=None,
            item_results=(),
            unsupported_quantity_ids=(),
        )
    quantity_ids = [row.quantity_id for row in produced]
    if len(quantity_ids) != len(set(quantity_ids)):
        raise ValueError("produced quantity ids must be unique")
    consumed: set[str] = set()
    related: set[str] = set()
    results: list[ItemResultV2] = []

    for item in manifest.verified_items:
        if not item.denominator_eligible:
            continue
        expected_refs = set(item.expected_object_refs)
        if not expected_refs:
            results.append(ItemResultV2(item.item_id, UNRESOLVED, None, None, ()))
            continue

        compatible = tuple(
            row for row in produced
            if (
                row.trade_category == item.trade_category
                and row.unit == item.unit
                and not row.abstained
                and row.lineage_ok
            )
        )
        exact = tuple(row for row in compatible if set(row.object_refs) == expected_refs)
        overlap = tuple(row for row in compatible if set(row.object_refs) & expected_refs)

        if len(exact) > 1:
            related.update(row.quantity_id for row in exact)
            results.append(ItemResultV2(item.item_id, UNRESOLVED, None, None, ()))
            continue
        if len(exact) == 0:
            related.update(row.quantity_id for row in overlap)
            state = PARTIAL if overlap else MISSED
            matched_refs = tuple(sorted(set().union(*(set(row.object_refs) for row in overlap)))) if overlap else ()
            results.append(ItemResultV2(item.item_id, state, None, None, matched_refs))
            continue

        row = exact[0]
        if row.value is None:
            results.append(ItemResultV2(item.item_id, UNRESOLVED, row.quantity_id, None, row.object_refs))
            related.add(row.quantity_id)
            continue

        error = _error_fraction(float(row.value), float(item.expected_quantity))
        state = (
            MATCHED_WITHIN_TOLERANCE
            if error <= item.tolerance_fraction
            else MATCHED_OUTSIDE_TOLERANCE
        )
        consumed.add(row.quantity_id)
        related.add(row.quantity_id)
        results.append(ItemResultV2(item.item_id, state, row.quantity_id, error, row.object_refs))

    unsupported = tuple(sorted(
        row.quantity_id
        for row in produced
        if not row.abstained and row.lineage_ok and row.quantity_id not in related
    ))
    denominator = sum(1 for item in manifest.verified_items if item.denominator_eligible)
    within = sum(result.state == MATCHED_WITHIN_TOLERANCE for result in results)
    outside = sum(result.state == MATCHED_OUTSIDE_TOLERANCE for result in results)
    missed = sum(result.state == MISSED for result in results)
    partial = sum(result.state == PARTIAL for result in results)
    unresolved = sum(result.state == UNRESOLVED for result in results)
    coverage = within / denominator if denominator else None
    adjusted_denominator = denominator + len(unsupported)
    adjusted = within / adjusted_denominator if adjusted_denominator else None

    return ProjectResultV2(
        project_id=manifest.project_id,
        manifest_status=manifest.status,
        denominator=denominator,
        matched_within_tolerance=within,
        matched_outside_tolerance=outside,
        missed=missed,
        partial=partial,
        unresolved=unresolved,
        unsupported_extra=len(unsupported),
        coverage_accuracy=coverage,
        precision_adjusted_accuracy=adjusted,
        item_results=tuple(results),
        unsupported_quantity_ids=unsupported,
    )


def evaluate_suite_v2(
    manifests: Iterable[ProjectBenchmarkManifestV2],
    produced_by_project: dict[str, Iterable[ProducedTakeoffItemV2]],
    *,
    required_project_count: int = 5,
    evaluated_source_sha256s_by_project: dict[str, Iterable[str]] | None = None,
    reconciliation_complete_by_project: dict[str, bool] | None = None,
) -> SuiteResultV2:
    manifest_tuple = tuple(manifests)
    if len({manifest.project_id for manifest in manifest_tuple}) != len(manifest_tuple):
        raise ValueError("project ids must be unique")

    produced_map = {
        str(project_id): tuple(rows)
        for project_id, rows in produced_by_project.items()
    }
    results = tuple(
        evaluate_project_v2(manifest, produced_map.get(manifest.project_id, ()))
        for manifest in manifest_tuple
    )
    verified = sum(manifest.status == PROJECT_VERIFIED for manifest in manifest_tuple)
    configured = sum(manifest.status != PROJECT_NOT_CONFIGURED for manifest in manifest_tuple)
    denominator = sum(result.denominator for result in results)
    within = sum(result.matched_within_tolerance for result in results)
    extras = sum(result.unsupported_extra for result in results)
    reasons: list[str] = []
    run_blocked = False
    source_hashes = evaluated_source_sha256s_by_project or {}
    reconciliation = reconciliation_complete_by_project or {}
    manifest_ids = {manifest.project_id for manifest in manifest_tuple}
    unexpected_project_ids = tuple(sorted(set(produced_map) - manifest_ids))
    if unexpected_project_ids:
        run_blocked = True
        for project_id in unexpected_project_ids:
            reasons.append(f"{project_id}:unexpected_produced_project")
            extras += sum(
                1
                for row in produced_map[project_id]
                if not row.abstained and row.lineage_ok
            )
    if len(manifest_tuple) != required_project_count:
        reasons.append("required_project_count_not_met")
    for manifest in manifest_tuple:
        if manifest.status != PROJECT_VERIFIED:
            reasons.extend(f"{manifest.project_id}:{reason}" for reason in manifest.reason_codes)
            continue
        if manifest.project_id not in produced_map:
            reasons.append(f"{manifest.project_id}:extraction_not_complete")
            run_blocked = True
        elif any(not row.lineage_ok for row in produced_map[manifest.project_id]):
            reasons.append(f"{manifest.project_id}:lineage_conflict")
            run_blocked = True
        expected_hashes = tuple(sorted(doc.sha256 for doc in manifest.source_documents))
        actual_hashes = tuple(
            sorted(
                {
                    str(value).strip().lower()
                    for value in source_hashes.get(manifest.project_id, ())
                    if str(value).strip()
                }
            )
        )
        if actual_hashes != expected_hashes:
            reasons.append(f"{manifest.project_id}:source_hashes_not_verified")
            run_blocked = True
        if reconciliation.get(manifest.project_id) is not True:
            reasons.append(f"{manifest.project_id}:object_reconciliation_incomplete")
            run_blocked = True

    complete = (
        len(manifest_tuple) == required_project_count
        and verified == required_project_count
        and not reasons
    )
    publication_status = "PUBLISHED" if complete else "UNPUBLISHED"
    if complete:
        development_status = "COMPLETE"
    elif verified == required_project_count:
        development_status = "VERIFIED_MANIFESTS_RUN_INCOMPLETE"
    elif verified == required_project_count - 1:
        development_status = f"PROVISIONAL_{verified}_OF_{required_project_count}"
    else:
        development_status = f"INCOMPLETE_{verified}_OF_{required_project_count}"

    coverage = within / denominator if denominator and not run_blocked else None
    adjusted_denominator = denominator + extras
    adjusted = (
        within / adjusted_denominator
        if adjusted_denominator and not run_blocked
        else None
    )
    return SuiteResultV2(
        publication_status=publication_status,
        development_status=development_status,
        configured_projects=configured,
        verified_projects=verified,
        denominator=denominator,
        matched_within_tolerance=within,
        unsupported_extra=extras,
        coverage_accuracy=coverage,
        precision_adjusted_accuracy=adjusted,
        project_results=results,
        reason_codes=tuple(sorted(set(reasons))),
    )
