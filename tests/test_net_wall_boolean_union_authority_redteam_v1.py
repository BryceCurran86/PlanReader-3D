"""Net-wall Boolean Union V1 — validator foundation.

DRAFT / TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / DO NOT MERGE.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from pb_wall_net_area_quantity import build_net_wall_area_quantity


BASE_SHA = "5b5d92583ef8a8695da90209bf05f84b7385a77a"
MODULE_NAME = "pb_net_wall_boolean_union_authority"
HAS_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_AUTHORITY,
    strict=True,
    reason="net-wall Boolean Union authority is intentionally absent",
)

_REQUIRED_EXPORTS = {
    "NetWallBooleanUnionAuthority",
    "NetWallBooleanUnionProducer",
    "NetWallBooleanUnionRecord",
    "NetWallBooleanUnionResult",
    "NetWallBooleanUnionSelector",
}

_FORBIDDEN_PUBLIC_INPUTS = {
    "gross_area",
    "gross_area_m2",
    "deduction_area",
    "deduction_areas",
    "total_deduction",
    "opening_ids",
    "opening_count",
    "complete",
    "claimed_complete",
    "void_polygons",
    "polygons",
    "wall_id",
    "host_wall_id",
    "nearest",
    "first",
    "radius",
    "confidence",
}

_REQUIRED_RECORD_FIELDS = {
    "record_id",
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "page_id",
    "decision_scope_id",
    "physical_wall_id",
    "gross_geometry_record_id",
    "opening_universe_record_id",
    "deduction_record_ids",
    "union_geometry_id",
    "net_area_m2",
}

_REQUIRED_REASONS = {
    "NET_WALL_BOOLEAN_UNION_RESOLVED",
    "NET_WALL_GROSS_UNRESOLVED",
    "NET_WALL_OPENING_UNIVERSE_INCOMPLETE",
    "NET_WALL_DEDUCTION_UNRESOLVED",
    "NET_WALL_VOID_UNRESOLVED",
    "NET_WALL_WRONG_WALL_VOID",
    "NET_WALL_FRAME_MISMATCH",
    "NET_WALL_LINEAGE_MISMATCH",
}


def _module():
    assert HAS_AUTHORITY, (
        "pb_net_wall_boolean_union_authority is the genuine missing production "
        "capability; do not satisfy this validator with a test shim"
    )
    return importlib.import_module(MODULE_NAME)


def _params(callable_obj) -> set[str]:
    return set(inspect.signature(callable_obj).parameters)


def _source_text() -> str:
    spec = importlib.util.find_spec(MODULE_NAME)
    assert spec is not None and spec.origin
    return Path(spec.origin).read_text(encoding="utf-8")


def test_current_net_wall_public_builder_does_not_accept_caller_net_value() -> None:
    params = _params(build_net_wall_area_quantity)
    assert "net_area_m2" not in params
    assert "net_area" not in params


@EXPECTED_RED
def test_positive_capability_requires_boolean_union_authority_module() -> None:
    mod = _module()
    assert _REQUIRED_EXPORTS <= set(dir(mod))


@EXPECTED_RED
def test_authority_resolve_is_selector_only() -> None:
    mod = _module()
    assert _params(mod.NetWallBooleanUnionAuthority.resolve) == {"self", "selector"}


@EXPECTED_RED
def test_publish_cannot_accept_scalar_deductions_or_caller_polygons() -> None:
    mod = _module()
    publish = getattr(mod.NetWallBooleanUnionProducer, "publish", None)
    assert publish is not None
    leaked = _params(publish) & _FORBIDDEN_PUBLIC_INPUTS
    assert not leaked, f"caller/scalar truth leaked into net-wall publish(): {sorted(leaked)}"


@EXPECTED_RED
def test_factory_consumes_authorities_not_scalar_area_lists() -> None:
    mod = _module()
    factory = getattr(mod.NetWallBooleanUnionProducer, "from_authorities", None)
    assert factory is not None
    params = _params(factory)
    assert not (params & _FORBIDDEN_PUBLIC_INPUTS)
    lowered = {name.lower() for name in params}
    assert any("deduction" in name for name in lowered)
    assert any("universe" in name or "completeness" in name for name in lowered)
    assert any("gross" in name or "wall" in name for name in lowered)


@EXPECTED_RED
def test_record_carries_union_identity_and_nullable_net_area_contract() -> None:
    mod = _module()
    record = mod.NetWallBooleanUnionRecord
    assert is_dataclass(record)
    names = {item.name for item in fields(record)}
    missing = _REQUIRED_RECORD_FIELDS - names
    assert not missing, f"missing net-wall union record fields: {sorted(missing)}"
    annotation = record.__annotations__.get("net_area_m2")
    assert "None" in str(annotation) or "Optional" in str(annotation) or "| None" in str(annotation)


@EXPECTED_RED
def test_source_uses_unary_union_at_geometry_layer() -> None:
    source = _source_text()
    assert "shapely.ops" in source
    assert "unary_union" in source


@EXPECTED_RED
def test_source_does_not_scalar_sum_opening_areas() -> None:
    source = _source_text().lower()
    forbidden = (
        "sum(deduction",
        "sum(void",
        "total_deduction +=",
        "gross_area - total_deduction",
        "gross_area-total_deduction",
    )
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"scalar net-wall deduction path present: {present}"


@EXPECTED_RED
def test_source_consumes_authenticated_void_and_deduction_layers() -> None:
    source = _source_text()
    assert "pb_physical_opening_void_authority" in source
    assert "pb_opening_deduction_authority" in source
    assert "pb_opening_universe_completeness_authority" in source


@EXPECTED_RED
def test_reason_vocabulary_covers_blocking_geometry_and_scope_states() -> None:
    mod = _module()
    missing = _REQUIRED_REASONS - set(dir(mod))
    assert not missing, f"missing fail-closed net-wall reasons: {sorted(missing)}"


@EXPECTED_RED
def test_no_public_opening_list_can_claim_complete_union_scope() -> None:
    mod = _module()
    params = _params(mod.NetWallBooleanUnionProducer.publish)
    banned = {"opening_ids", "opening_count", "complete", "claimed_complete", "void_polygons"}
    assert not (params & banned)


@EXPECTED_RED
def test_result_can_block_net_without_erasing_gross_reference() -> None:
    mod = _module()
    result = mod.NetWallBooleanUnionResult
    assert is_dataclass(result)
    names = {item.name for item in fields(result)}
    assert {"status", "reason_codes", "record"} <= names
    record_names = {item.name for item in fields(mod.NetWallBooleanUnionRecord)}
    assert "gross_geometry_record_id" in record_names
    assert "net_area_m2" in record_names


@EXPECTED_RED
def test_no_nearest_or_first_host_inference_in_union_source() -> None:
    source = _source_text().lower()
    forbidden = ("nearest_wall", "nearest_host", "first_host", "bbox_overlap_only")
    present = tuple(item for item in forbidden if item in source)
    assert not present, f"host inference leaked into Boolean-union geometry layer: {present}"
