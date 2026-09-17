"""Item 13 Opening Deduction Authority V2 independent freeze validator.

TEST ONLY / EXPECTED-RED / DRAFT / NEVER MERGE.

The baseline is post-Item-11/12 main.  A real native-PDF Physical Opening Void must
resolve first.  Deduction remains a separate proposition and requires an independent
producer-owned target-applicability authority; target_scope_id is address only.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_readiness import build_opening_deduction_quantity
from pb_physical_opening_void_authority import PHYSICAL_OPENING_VOID_RESOLVED
from tests.test_physical_opening_void_authority import _fixture


BASE_SHA = "212f5b0ff9d9e585c4b9db861cf42729166f70f5"
DEDUCTION_MODULE = "pb_opening_deduction_authority"
APPLICABILITY_MODULE = "pb_opening_deduction_applicability_authority"
HAS_DEDUCTION = importlib.util.find_spec(DEDUCTION_MODULE) is not None
HAS_APPLICABILITY = importlib.util.find_spec(APPLICABILITY_MODULE) is not None

DEDUCTION_EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_DEDUCTION,
    strict=True,
    reason="Opening Deduction production is absent on the frozen baseline",
)
APPLICABILITY_EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_APPLICABILITY,
    strict=True,
    reason="producer-owned deduction target applicability is the genuine missing prerequisite",
)

_REQUIRED_EXPORTS = {
    "OpeningDeductionAuthority",
    "OpeningDeductionProducer",
    "OpeningDeductionRecord",
    "OpeningDeductionResult",
    "OpeningDeductionSelector",
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
    "opening_universe_record_id",
    "target_scope_id",
    "applicability_record_id",
}

_REQUIRED_REASONS = {
    "OPENING_DEDUCTION_AUTHORIZED",
    "OPENING_DEDUCTION_OPENING_UNRESOLVED",
    "OPENING_DEDUCTION_HOST_UNRESOLVED",
    "OPENING_DEDUCTION_VOID_UNRESOLVED",
    "OPENING_DEDUCTION_UNIVERSE_INCOMPLETE",
    "OPENING_DEDUCTION_WALL_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED",
    "OPENING_DEDUCTION_LINEAGE_MISMATCH",
}

_FORBIDDEN_PUBLIC_INPUTS = {
    "area",
    "area_m2",
    "raw_area",
    "deductible",
    "deduction_allowed",
    "finish_applicable",
    "trade_applicable",
    "assembly_applicable",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "host_wall_id",
    "wall_id",
    "host_id",
    "void_polygon",
    "polygon",
    "u0",
    "u1",
    "z0",
    "z1",
    "opening_ids",
    "opening_count",
    "candidate_count",
    "complete",
    "claimed_complete",
    "fingerprint",
    "nearest",
    "first",
    "radius",
    "confidence",
}

_FORBIDDEN_RECORD_FIELDS = {
    "raw_area",
    "raw_area_m2",
    "caller_area",
    "caller_deductible",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "net_wall_area",
    "commercial_quantity",
    "firm_quantity",
    "jobhub",
}


def _deduction_module():
    assert HAS_DEDUCTION, "real Opening Deduction production module is missing"
    return importlib.import_module(DEDUCTION_MODULE)


def _params(callable_obj) -> set[str]:
    return set(inspect.signature(callable_obj).parameters)


def _source_text() -> str:
    spec = importlib.util.find_spec(DEDUCTION_MODULE)
    assert spec is not None and spec.origin
    return Path(spec.origin).read_text(encoding="utf-8")


def test_real_source_physical_void_baseline_is_positive_before_deduction_red() -> None:
    """A stale upstream fixture must never be mistaken for a deduction RED."""
    void_producer, opening_selector, void_selector = _fixture()
    result = void_producer.publish(
        opening_selector=opening_selector,
        selector=void_selector,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert PHYSICAL_OPENING_VOID_RESOLVED in result.reason_codes
    assert result.record is not None


def test_legacy_readiness_cannot_accept_caller_deduction_permission() -> None:
    params = _params(build_opening_deduction_quantity)
    assert not (
        params
        & {
            "deductible",
            "deduction_allowed",
            "finish_applicable",
            "trade_applicable",
            "assembly_applicable",
            "raw_area",
            "area_m2",
        }
    )


@DEDUCTION_EXPECTED_RED
def test_deduction_module_exports_sealed_authority_surface() -> None:
    mod = _deduction_module()
    assert _REQUIRED_EXPORTS <= set(dir(mod))


@DEDUCTION_EXPECTED_RED
def test_selector_is_exact_address_only() -> None:
    mod = _deduction_module()
    assert is_dataclass(mod.OpeningDeductionSelector)
    names = {item.name for item in fields(mod.OpeningDeductionSelector)}
    assert names == _REQUIRED_SELECTOR_FIELDS
    assert not (names & _FORBIDDEN_PUBLIC_INPUTS)


@DEDUCTION_EXPECTED_RED
def test_authority_and_publish_are_selector_only() -> None:
    mod = _deduction_module()
    assert _params(mod.OpeningDeductionAuthority.resolve) == {"self", "selector"}
    assert _params(mod.OpeningDeductionProducer.publish) == {"self", "selector"}


@DEDUCTION_EXPECTED_RED
def test_factory_requires_separate_target_applicability_authority() -> None:
    """Void + host + completeness cannot construct the final deduction producer."""
    mod = _deduction_module()
    params = _params(mod.OpeningDeductionProducer.from_authorities)
    assert {
        "physical_void_authority",
        "host_binding_authority",
        "opening_universe_authority",
        "target_applicability_authority",
    } <= params
    assert not (params & _FORBIDDEN_PUBLIC_INPUTS)


@DEDUCTION_EXPECTED_RED
def test_positive_record_must_retain_applicability_provenance() -> None:
    mod = _deduction_module()
    assert is_dataclass(mod.OpeningDeductionRecord)
    names = {item.name for item in fields(mod.OpeningDeductionRecord)}
    missing = _REQUIRED_RECORD_FIELDS - names
    assert not missing, f"deduction record missing required provenance: {sorted(missing)}"
    assert not (names & _FORBIDDEN_RECORD_FIELDS)


@DEDUCTION_EXPECTED_RED
def test_reason_vocabulary_covers_fail_closed_boundary() -> None:
    mod = _deduction_module()
    missing = _REQUIRED_REASONS - set(dir(mod))
    assert not missing, f"deduction reason vocabulary incomplete: {sorted(missing)}"


@DEDUCTION_EXPECTED_RED
def test_source_consumes_applicability_authority_not_target_scope_self_certification() -> None:
    source = _source_text()
    assert "pb_physical_opening_void_authority" in source
    assert "pb_opening_host_binding_authority" in source
    assert "pb_opening_universe_completeness_authority" in source
    assert APPLICABILITY_MODULE in source
    assert "OpeningDeductionApplicabilityAuthority" in source
    assert "applicability_record_id" in source
    assert "commercial_applicability" not in source


@DEDUCTION_EXPECTED_RED
def test_public_surface_has_no_raw_truth_or_applicability_flags() -> None:
    mod = _deduction_module()
    for callable_obj in (
        mod.OpeningDeductionProducer.publish,
        mod.OpeningDeductionProducer.from_authorities,
        mod.OpeningDeductionAuthority.resolve,
    ):
        leaked = _params(callable_obj) & _FORBIDDEN_PUBLIC_INPUTS
        assert not leaked, f"caller truth leaked into deduction boundary: {sorted(leaked)}"


@DEDUCTION_EXPECTED_RED
def test_source_has_no_legacy_scalar_or_selection_shortcuts() -> None:
    source = _source_text().lower()
    forbidden = (
        "width * height",
        "width*height",
        "nearest_wall",
        "nearest_host",
        "first_host",
        "caller_deductible",
        "caller_area",
        "finish_applicable=",
        "trade_applicable=",
        "assembly_applicable=",
    )
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"forbidden deduction shortcut present: {present}"


@DEDUCTION_EXPECTED_RED
def test_real_source_void_alone_cannot_construct_final_deduction_producer() -> None:
    """Executable real-source attack: physical truth alone is insufficient."""
    mod = _deduction_module()
    void_producer, opening_selector, void_selector = _fixture()
    void_result = void_producer.publish(
        opening_selector=opening_selector,
        selector=void_selector,
    )
    assert void_result.status is EvidenceResolutionStatus.CORROBORATED
    assert void_result.record is not None

    params = _params(mod.OpeningDeductionProducer.from_authorities)
    assert "target_applicability_authority" in params

    # The real void producer owns the exact sealed host/universe authorities used
    # to publish this void. Even with all three physical prerequisites present,
    # omitting target applicability must make construction structurally impossible.
    with pytest.raises(TypeError):
        mod.OpeningDeductionProducer.from_authorities(
            physical_void_authority=void_producer.authority(),
            host_binding_authority=void_producer._host,
            opening_universe_authority=void_producer._universe,
        )


@APPLICABILITY_EXPECTED_RED
def test_target_applicability_is_a_separate_producer_owned_module() -> None:
    mod = importlib.import_module(APPLICABILITY_MODULE)
    required = {
        "OpeningDeductionApplicabilityAuthority",
        "OpeningDeductionApplicabilityProducer",
        "OpeningDeductionApplicabilityRecord",
        "OpeningDeductionApplicabilityResult",
        "OpeningDeductionApplicabilitySelector",
    }
    assert required <= set(dir(mod))
    assert _params(mod.OpeningDeductionApplicabilityAuthority.resolve) == {"self", "selector"}


@DEDUCTION_EXPECTED_RED
def test_result_unknown_path_cannot_be_authoritative_numeric_zero() -> None:
    mod = _deduction_module()
    result_type = mod.OpeningDeductionResult
    assert is_dataclass(result_type)
    names = {item.name for item in fields(result_type)}
    assert {"status", "reason_codes", "record"} <= names
    if "value" in names:
        annotation = result_type.__annotations__.get("value")
        assert "None" in str(annotation) or "Optional" in str(annotation) or "| None" in str(annotation)
