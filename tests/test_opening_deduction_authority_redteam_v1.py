"""Opening Deduction Authority V1 — validator foundation.

DRAFT / TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / DO NOT MERGE.

This locks the public firewall and result semantics now.  Real-source behavioral
attacks must be added before the validator can be frozen, once Physical Opening
Void V2 and its positive prerequisites exist.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from pb_opening_deduction_readiness import build_opening_deduction_quantity


BASE_SHA = "5b5d92583ef8a8695da90209bf05f84b7385a77a"
MODULE_NAME = "pb_opening_deduction_authority"
HAS_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_AUTHORITY,
    strict=True,
    reason="producer-owned opening deduction authority is intentionally absent",
)

_REQUIRED_EXPORTS = {
    "OpeningDeductionAuthority",
    "OpeningDeductionProducer",
    "OpeningDeductionRecord",
    "OpeningDeductionResult",
    "OpeningDeductionSelector",
}

_FORBIDDEN_PUBLIC_INPUTS = {
    "area",
    "area_m2",
    "deductible",
    "deduction_allowed",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "host_wall_id",
    "wall_id",
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
}

_FORBIDDEN_RECORD_FIELDS = {
    "raw_area",
    "raw_area_m2",
    "caller_area",
    "caller_deductible",
    "provisional_net_area",
    "net_wall_area",
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


def _module():
    assert HAS_AUTHORITY, (
        "pb_opening_deduction_authority is the genuine missing production capability; "
        "do not satisfy this validator with a test shim"
    )
    return importlib.import_module(MODULE_NAME)


def _params(callable_obj) -> set[str]:
    return set(inspect.signature(callable_obj).parameters)


def _source_text() -> str:
    spec = importlib.util.find_spec(MODULE_NAME)
    assert spec is not None and spec.origin
    return Path(spec.origin).read_text(encoding="utf-8")


def test_legacy_readiness_still_has_no_caller_deductible_boolean() -> None:
    """Current fail-closed legacy arithmetic must not regress while V1 is absent."""
    params = _params(build_opening_deduction_quantity)
    assert "deductible" not in params
    assert "deduction_allowed" not in params
    assert "raw_area" not in params
    assert "area_m2" not in params


@EXPECTED_RED
def test_positive_capability_requires_real_deduction_authority_module() -> None:
    mod = _module()
    assert _REQUIRED_EXPORTS <= set(dir(mod))


@EXPECTED_RED
def test_selector_addresses_lineage_opening_and_target_scope_only() -> None:
    mod = _module()
    selector = mod.OpeningDeductionSelector
    assert is_dataclass(selector)
    names = {item.name for item in fields(selector)}
    assert names == _REQUIRED_SELECTOR_FIELDS
    assert not (names & _FORBIDDEN_PUBLIC_INPUTS)


@EXPECTED_RED
def test_authority_resolve_is_selector_only() -> None:
    mod = _module()
    assert _params(mod.OpeningDeductionAuthority.resolve) == {"self", "selector"}


@EXPECTED_RED
def test_publish_cannot_accept_raw_area_or_deductible_truth() -> None:
    mod = _module()
    publish = getattr(mod.OpeningDeductionProducer, "publish", None)
    assert publish is not None
    leaked = _params(publish) & _FORBIDDEN_PUBLIC_INPUTS
    assert not leaked, f"caller-shaped deduction truth leaked into publish(): {sorted(leaked)}"


@EXPECTED_RED
def test_factory_consumes_authorities_not_raw_arithmetic() -> None:
    mod = _module()
    factory = getattr(mod.OpeningDeductionProducer, "from_authorities", None)
    assert factory is not None
    params = _params(factory)
    leaked = params & _FORBIDDEN_PUBLIC_INPUTS
    assert not leaked
    lowered = {name.lower() for name in params}
    assert any("void" in name for name in lowered)
    assert any("host" in name for name in lowered)
    assert any("universe" in name or "completeness" in name for name in lowered)


@EXPECTED_RED
def test_record_references_authenticated_void_instead_of_recomputing_width_times_height() -> None:
    mod = _module()
    record = mod.OpeningDeductionRecord
    assert is_dataclass(record)
    names = {item.name for item in fields(record)}
    missing = _REQUIRED_RECORD_FIELDS - names
    assert not missing, f"missing authenticated deduction references: {sorted(missing)}"
    assert not (names & _FORBIDDEN_RECORD_FIELDS)
    assert "width" not in names
    assert "height" not in names
    assert "width_mm" not in names
    assert "height_mm" not in names


@EXPECTED_RED
def test_result_can_represent_unknown_without_zero() -> None:
    mod = _module()
    result = mod.OpeningDeductionResult
    assert is_dataclass(result)
    names = {item.name for item in fields(result)}
    assert {"status", "reason_codes", "record"} <= names
    if "value" in names:
        annotation = result.__annotations__.get("value")
        assert "None" in str(annotation) or "Optional" in str(annotation) or "| None" in str(annotation)


@EXPECTED_RED
def test_reason_vocabulary_covers_fail_closed_prerequisites() -> None:
    mod = _module()
    missing = _REQUIRED_REASONS - set(dir(mod))
    assert not missing, f"missing fail-closed reason codes: {sorted(missing)}"


@EXPECTED_RED
def test_source_depends_on_physical_void_not_legacy_width_height_arithmetic() -> None:
    source = _source_text()
    assert "pb_physical_opening_void_authority" in source
    assert "physical_void" in source.lower()
    assert "pb_opening_host_binding_authority" in source
    assert "pb_opening_universe_completeness_authority" in source


@EXPECTED_RED
def test_source_does_not_use_legacy_nearest_bbox_or_scalar_area_shortcuts() -> None:
    source = _source_text().lower()
    forbidden = (
        "nearest_wall",
        "nearest_host",
        "first_host",
        "bbox_overlap_only",
        "width * height",
        "width*height",
        "caller_deductible",
        "caller_area",
    )
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"legacy deduction shortcut present: {present}"


@EXPECTED_RED
def test_record_does_not_publish_net_wall_area() -> None:
    mod = _module()
    names = {item.name.lower() for item in fields(mod.OpeningDeductionRecord)}
    assert not any("net_wall" in name for name in names)
    assert not any("gross_wall" in name for name in names)


@EXPECTED_RED
def test_no_public_duplicate_count_can_claim_complete_opening_set() -> None:
    mod = _module()
    publish_params = _params(mod.OpeningDeductionProducer.publish)
    banned = {"opening_ids", "opening_count", "candidate_count", "complete", "claimed_complete"}
    assert not (publish_params & banned)


@EXPECTED_RED
def test_no_public_host_id_can_bypass_authenticated_binding() -> None:
    mod = _module()
    publish_params = _params(mod.OpeningDeductionProducer.publish)
    assert not (publish_params & {"wall_id", "host_wall_id", "host_id"})


@EXPECTED_RED
def test_no_public_finish_or_assembly_boolean_can_mint_applicability() -> None:
    mod = _module()
    publish_params = _params(mod.OpeningDeductionProducer.publish)
    banned = {
        "finish_applicable",
        "assembly_applicable",
        "trade_applicable",
        "deductible",
        "deduction_allowed",
    }
    assert not (publish_params & banned)
