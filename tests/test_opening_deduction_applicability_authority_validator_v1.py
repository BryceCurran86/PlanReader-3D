"""Independent validator for Opening Deduction target-applicability authority.

TEST ONLY / EXPECTED-RED / DRAFT / NEVER MERGE.

This validator locks the proposition that an authenticated physical opening void is
not, by itself, permission to deduct from an exact wall/trade/finish/assembly target.
Applicability must be producer-owned, exact-scope, replayable, and rule-proven.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_void_authority import PHYSICAL_OPENING_VOID_RESOLVED
from tests.test_physical_opening_void_authority import _fixture


BASE_SHA = "212f5b0ff9d9e585c4b9db861cf42729166f70f5"
MODULE_NAME = "pb_opening_deduction_applicability_authority"
HAS_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None

EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_AUTHORITY,
    strict=True,
    reason="producer-owned Opening Deduction target-applicability authority is absent",
)

_REQUIRED_EXPORTS = {
    "OpeningDeductionApplicabilityAuthority",
    "OpeningDeductionApplicabilityProducer",
    "OpeningDeductionApplicabilityRecord",
    "OpeningDeductionApplicabilityResult",
    "OpeningDeductionApplicabilitySelector",
    "OpeningDeductionTargetScopeAuthority",
    "OpeningDeductionRuleAuthority",
}

_REQUIRED_SELECTOR_FIELDS = {
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "page_id",
    "decision_scope_id",
    "opening_identity_id",
    "target_scope_id",
}

_REQUIRED_RECORD_FIELDS = {
    "record_id",
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "page_id",
    "decision_scope_id",
    "opening_identity_id",
    "host_binding_record_id",
    "physical_void_record_id",
    "target_scope_id",
    "target_scope_record_id",
    "rule_record_id",
    "rule_version",
}

_REQUIRED_REASON_CODES = {
    "OPENING_DEDUCTION_APPLICABILITY_RESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT",
}

_FORBIDDEN_PUBLIC_INPUTS = {
    "applicable",
    "is_applicable",
    "deductible",
    "deduction_allowed",
    "trade_applicable",
    "finish_applicable",
    "assembly_applicable",
    "commercial_applicability",
    "host_wall_id",
    "wall_id",
    "trade",
    "trade_id",
    "finish",
    "finish_id",
    "assembly",
    "assembly_id",
    "rule",
    "rule_id",
    "rule_version",
    "area",
    "area_m2",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "u0",
    "u1",
    "z0",
    "z1",
    "nearest",
    "first",
    "default",
    "confidence",
}

_FORBIDDEN_RECORD_FIELDS = {
    "raw_area",
    "raw_area_m2",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "net_wall_area",
    "gross_wall_area",
    "commercial_quantity",
    "firm_quantity",
    "jobhub",
}


def _module():
    assert HAS_AUTHORITY, (
        "pb_opening_deduction_applicability_authority is the genuine missing "
        "production capability; do not satisfy this validator with a test shim"
    )
    return importlib.import_module(MODULE_NAME)


def _params(callable_obj) -> set[str]:
    return set(inspect.signature(callable_obj).parameters)


def _source_text() -> str:
    spec = importlib.util.find_spec(MODULE_NAME)
    assert spec is not None and spec.origin
    return Path(spec.origin).read_text(encoding="utf-8")


def test_real_source_physical_void_is_positive_but_not_applicability_truth() -> None:
    """The upstream physical proposition is healthy before applicability is tested."""
    producer, opening_selector, selector = _fixture()
    result = producer.publish(opening_selector=opening_selector, selector=selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert PHYSICAL_OPENING_VOID_RESOLVED in result.reason_codes
    assert result.record is not None


@EXPECTED_RED
def test_module_exports_separate_producer_owned_applicability_surface() -> None:
    mod = _module()
    assert _REQUIRED_EXPORTS <= set(dir(mod))


@EXPECTED_RED
def test_selector_is_address_only_not_applicability_truth() -> None:
    mod = _module()
    selector = mod.OpeningDeductionApplicabilitySelector
    assert is_dataclass(selector)
    names = {item.name for item in fields(selector)}
    assert names == _REQUIRED_SELECTOR_FIELDS
    assert not (names & _FORBIDDEN_PUBLIC_INPUTS)


@EXPECTED_RED
def test_authority_resolve_and_publish_are_selector_only() -> None:
    mod = _module()
    assert _params(mod.OpeningDeductionApplicabilityAuthority.resolve) == {
        "self",
        "selector",
    }
    assert _params(mod.OpeningDeductionApplicabilityProducer.publish) == {
        "self",
        "selector",
    }


@EXPECTED_RED
def test_factory_consumes_sealed_upstream_authorities_not_caller_truth() -> None:
    mod = _module()
    factory = mod.OpeningDeductionApplicabilityProducer.from_authorities
    params = _params(factory)
    assert {
        "physical_void_authority",
        "host_binding_authority",
        "target_scope_authority",
        "rule_authority",
    } <= params
    leaked = params & _FORBIDDEN_PUBLIC_INPUTS
    assert not leaked, f"caller applicability truth leaked into factory: {sorted(leaked)}"


@EXPECTED_RED
def test_positive_record_retains_exact_target_rule_and_physical_provenance() -> None:
    mod = _module()
    record = mod.OpeningDeductionApplicabilityRecord
    assert is_dataclass(record)
    names = {item.name for item in fields(record)}
    missing = _REQUIRED_RECORD_FIELDS - names
    assert not missing, f"missing applicability provenance: {sorted(missing)}"
    assert not (names & _FORBIDDEN_RECORD_FIELDS)


@EXPECTED_RED
def test_target_scope_and_rule_are_separate_producer_owned_authorities() -> None:
    mod = _module()
    target = mod.OpeningDeductionTargetScopeAuthority
    rule = mod.OpeningDeductionRuleAuthority
    assert _params(target.resolve) == {"self", "selector"}
    assert _params(rule.resolve) == {"self", "selector"}


@EXPECTED_RED
def test_reason_vocabulary_locks_scope_lineage_and_rule_conflicts() -> None:
    mod = _module()
    missing = _REQUIRED_REASON_CODES - set(dir(mod))
    assert not missing, f"missing applicability reason codes: {sorted(missing)}"


@EXPECTED_RED
def test_public_boundary_has_no_caller_applicability_or_geometry_shortcuts() -> None:
    mod = _module()
    for callable_obj in (
        mod.OpeningDeductionApplicabilityAuthority.resolve,
        mod.OpeningDeductionApplicabilityProducer.publish,
        mod.OpeningDeductionApplicabilityProducer.from_authorities,
    ):
        leaked = _params(callable_obj) & _FORBIDDEN_PUBLIC_INPUTS
        assert not leaked, f"caller truth leaked into public boundary: {sorted(leaked)}"


@EXPECTED_RED
def test_source_does_not_reuse_legacy_commercial_metadata_or_default_rules() -> None:
    source = _source_text().lower()
    forbidden = (
        "commercial_applicability",
        "deductible=true",
        "deduction_allowed=true",
        "finish_applicable=true",
        "trade_applicable=true",
        "assembly_applicable=true",
        "nearest_target",
        "first_target",
        "default_target",
        "pb_australian_takeoff_standards_v178",
        "calculate_wall_takeoff",
    )
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"legacy/default applicability shortcut present: {present}"


@EXPECTED_RED
def test_source_requires_exact_physical_void_host_target_and_rule_joins() -> None:
    source = _source_text()
    required_fragments = (
        "pb_physical_opening_void_authority",
        "pb_opening_host_binding_authority",
        "physical_void_record_id",
        "host_binding_record_id",
        "target_scope_record_id",
        "rule_record_id",
        "rule_version",
    )
    missing = tuple(fragment for fragment in required_fragments if fragment not in source)
    assert not missing, f"missing exact applicability joins: {missing}"


@EXPECTED_RED
def test_applicability_result_can_fail_closed_without_positive_record() -> None:
    mod = _module()
    result = mod.OpeningDeductionApplicabilityResult
    assert is_dataclass(result)
    names = {item.name for item in fields(result)}
    assert {"status", "reason_codes", "record"} <= names
    annotation = result.__annotations__.get("record")
    assert "None" in str(annotation) or "Optional" in str(annotation) or "| None" in str(annotation)


@EXPECTED_RED
def test_applicability_record_does_not_mint_downstream_authorities() -> None:
    mod = _module()
    names = {item.name.lower() for item in fields(mod.OpeningDeductionApplicabilityRecord)}
    forbidden_tokens = ("net_wall", "firm", "commercial_quantity", "jobhub")
    assert not any(any(token in name for token in forbidden_tokens) for name in names)


@EXPECTED_RED
def test_two_conflicting_rules_cannot_be_resolved_by_first_latest_or_confidence() -> None:
    source = _source_text().lower()
    assert "rule_conflict" in source
    forbidden = (
        "max(confidence",
        "sorted(rules)[0]",
        "rules[0]",
        "latest_rule",
        "first_rule",
    )
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"rule conflict uses heuristic winner: {present}"


@EXPECTED_RED
def test_same_size_openings_cannot_collapse_identity_inside_applicability() -> None:
    source = _source_text().lower()
    # Identity joins must exist; dimension/area equality must not be the dedupe key.
    assert "opening_identity_id" in source
    forbidden = ("dedupe_by_dimensions", "dedupe_by_area", "width_height_key")
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"applicability dedupes physical openings by geometry: {present}"
