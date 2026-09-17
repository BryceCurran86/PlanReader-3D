"""Physical Opening Void V2 — validator foundation.

DRAFT / TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / DO NOT MERGE.

This first validator pass freezes the public authority boundary and wall-local
record semantics without manufacturing the currently-missing positive height /
vertical-placement / physical-unit evidence. Behavioral real-source attacks
listed in ``docs/physical_opening_void_v2_authority_architecture.md`` must be
added and independently reviewed before this validator may be called frozen.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_dimension_authority import OpeningDimensionAuthority
from pb_opening_height_authority import OpeningHeightAuthority, OpeningHeightSelector
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementAuthority,
    OpeningVerticalPlacementSelector,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_scale_authority import PhysicalScaleAuthority, PhysicalScaleSelector


BASE_SHA = "35aad62125cdebf9332ca94ffe5e40730a960dcf"
MODULE_NAME = "pb_physical_opening_void_authority"
HAS_VOID_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_VOID_AUTHORITY,
    strict=True,
    reason=(
        "Physical Opening Void V2 production is intentionally absent; this validator "
        "must remain test-only until the current sealed prerequisite chain replays green"
    ),
)

_REQUIRED_EXPORTS = {
    "PhysicalOpeningVoidAuthority",
    "PhysicalOpeningVoidProducer",
    "PhysicalOpeningVoidRecord",
    "PhysicalOpeningVoidResult",
    "PhysicalOpeningVoidSelector",
}

_FORBIDDEN_EVIDENCE_PARAMS = {
    "host_wall_id",
    "candidate_wall_id",
    "candidate_wall_ids",
    "wall_id",
    "width",
    "width_mm",
    "height",
    "height_mm",
    "area",
    "area_m2",
    "u",
    "u0",
    "u1",
    "z",
    "z0",
    "z1",
    "x",
    "y",
    "position",
    "center",
    "centre",
    "sill",
    "sill_height",
    "head",
    "head_height",
    "scale",
    "scale_ratio",
    "px_per_m",
    "points_per_m",
    "unit_factor",
    "default_height",
    "typical_height",
    "default_sill",
    "default_head",
    "claimed_complete",
    "complete",
    "count",
    "radius",
    "nearest",
    "first",
    "confidence",
    "polygon",
    "profile",
}

_REQUIRED_SELECTOR_FIELDS = {
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "page_id",
    "decision_scope_id",
    "opening_identity_id",
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
    "opening_universe_record_id",
    "width_record_id",
    "height_record_id",
    "wall_local_frame_id",
    "unit_mapping_record_id",
    "vertical_placement_record_id",
    "u0",
    "u1",
    "z0",
    "z1",
}

_FORBIDDEN_RECORD_FIELDS = {
    "deductible",
    "deductible_area",
    "deduction_area",
    "net_wall_area",
    "finish_scope",
    "assembly",
    "commercial_quantity",
    "firm_quantity",
    "jobhub",
}

_REQUIRED_REASON_EXPORTS = {
    "PHYSICAL_OPENING_VOID_RESOLVED",
    "PHYSICAL_OPENING_VOID_OPENING_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HOST_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HOST_CONFLICT",
    "PHYSICAL_OPENING_VOID_WIDTH_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_VERTICAL_PLACEMENT_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_FRAME_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_UNIT_MAPPING_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_UNIVERSE_INCOMPLETE",
    "PHYSICAL_OPENING_VOID_PROFILE_UNSUPPORTED",
    "PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT",
    "PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH",
}


def _module():
    assert HAS_VOID_AUTHORITY, (
        "pb_physical_opening_void_authority is the genuine missing production "
        "capability; do not satisfy this validator with a test shim"
    )
    return importlib.import_module(MODULE_NAME)


def _public_parameter_names(callable_obj) -> set[str]:
    return set(inspect.signature(callable_obj).parameters)


def _source_text() -> str:
    spec = importlib.util.find_spec(MODULE_NAME)
    assert spec is not None and spec.origin
    return Path(spec.origin).read_text(encoding="utf-8")


def test_legacy_dimension_height_boundary_still_cannot_self_certify_height() -> None:
    """Width authority retains a fail-closed legacy height surface only."""
    params = set(inspect.signature(OpeningDimensionAuthority.resolve_height).parameters)
    assert params == {"self", "selector"}


def test_current_height_and_vertical_boundaries_are_selector_only() -> None:
    assert set(inspect.signature(OpeningHeightAuthority.resolve).parameters) == {
        "self",
        "selector",
    }
    assert set(inspect.signature(OpeningVerticalPlacementAuthority.resolve).parameters) == {
        "self",
        "selector",
    }
    assert {item.name for item in fields(OpeningHeightSelector)} == {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "decision_scope_id",
        "opening_record_id",
    }
    assert {item.name for item in fields(OpeningVerticalPlacementSelector)} == {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "decision_scope_id",
        "opening_record_id",
    }


def test_opening_universe_lookup_is_selector_only_not_caller_completeness() -> None:
    params = set(inspect.signature(OpeningUniverseCompletenessAuthority.resolve).parameters)
    assert params == {"self", "selector"}
    selector_fields = {item.name for item in fields(OpeningUniverseSelector)}
    assert not (selector_fields & {"complete", "claimed_complete", "count", "fingerprint"})


def test_physical_scale_lookup_is_selector_only_and_viewport_addressed() -> None:
    """Ratios and conversion factors cannot enter the sealed physical-scale lookup."""
    assert set(inspect.signature(PhysicalScaleAuthority.resolve).parameters) == {
        "self",
        "selector",
    }
    selector_fields = {item.name for item in fields(PhysicalScaleSelector)}
    assert selector_fields == {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "viewport_id",
    }
    assert not (selector_fields & {"ratio", "scale_ratio", "points_per_mm", "mm_per_point"})


@EXPECTED_RED
def test_positive_capability_requires_real_void_authority_module() -> None:
    mod = _module()
    assert _REQUIRED_EXPORTS <= set(dir(mod))


@EXPECTED_RED
def test_selector_is_lineage_and_opening_address_only() -> None:
    mod = _module()
    selector = mod.PhysicalOpeningVoidSelector
    assert is_dataclass(selector)
    selector_fields = {item.name for item in fields(selector)}
    assert selector_fields == _REQUIRED_SELECTOR_FIELDS
    assert not (selector_fields & _FORBIDDEN_EVIDENCE_PARAMS)


@EXPECTED_RED
def test_authority_resolve_is_selector_only() -> None:
    mod = _module()
    params = _public_parameter_names(mod.PhysicalOpeningVoidAuthority.resolve)
    assert params == {"self", "selector"}


@EXPECTED_RED
def test_producer_publish_cannot_accept_raw_void_truth() -> None:
    mod = _module()
    publish = getattr(mod.PhysicalOpeningVoidProducer, "publish", None)
    assert publish is not None, "production must expose one producer-owned publish boundary"
    params = _public_parameter_names(publish)
    leaked = params & _FORBIDDEN_EVIDENCE_PARAMS
    assert not leaked, f"caller evidence-shaped void parameters leaked into publish(): {sorted(leaked)}"


@EXPECTED_RED
def test_producer_factory_requires_upstream_authorities_not_raw_values() -> None:
    mod = _module()
    factory = getattr(mod.PhysicalOpeningVoidProducer, "from_authorities", None)
    assert factory is not None
    params = _public_parameter_names(factory)
    leaked = params & _FORBIDDEN_EVIDENCE_PARAMS
    assert not leaked, f"raw evidence cannot enter from_authorities(): {sorted(leaked)}"
    names = {name.lower() for name in params}
    assert any("host" in name for name in names)
    assert any("dimension" in name or "width" in name for name in names)
    assert any("universe" in name or "completeness" in name for name in names)
    assert any("vertical" in name or "placement" in name for name in names), (
        "height alone cannot establish z0/z1; a reviewed vertical-placement authority is required"
    )
    assert any("scale" in name or "unit" in name for name in names), (
        "PDF points and physical opening dimensions cannot be mixed without an authenticated unit mapping"
    )


@EXPECTED_RED
def test_record_is_wall_local_geometry_not_plan_polygon_or_deduction() -> None:
    mod = _module()
    record = mod.PhysicalOpeningVoidRecord
    assert is_dataclass(record)
    record_fields = {item.name for item in fields(record)}
    missing = _REQUIRED_RECORD_FIELDS - record_fields
    assert not missing, f"void record is missing required authority/geometry fields: {sorted(missing)}"
    assert not (record_fields & _FORBIDDEN_RECORD_FIELDS)
    assert "polygon" not in record_fields
    assert "area" not in record_fields
    assert "area_m2" not in record_fields


@EXPECTED_RED
def test_record_keeps_void_separate_from_commercial_deduction() -> None:
    mod = _module()
    record_fields = {item.name.lower() for item in fields(mod.PhysicalOpeningVoidRecord)}
    banned_fragments = ("deduct", "finish", "assembly", "commercial", "jobhub", "net_wall")
    assert not any(fragment in name for name in record_fields for fragment in banned_fragments)


@EXPECTED_RED
def test_reason_vocabulary_covers_every_blocking_prerequisite() -> None:
    mod = _module()
    missing = _REQUIRED_REASON_EXPORTS - set(dir(mod))
    assert not missing, f"missing fail-closed reason codes: {sorted(missing)}"


@EXPECTED_RED
def test_source_depends_on_authenticated_host_dimension_completeness_and_scale_layers() -> None:
    source = _source_text()
    assert "pb_physical_opening_authority" in source
    assert "pb_opening_host_binding_authority" in source
    assert "pb_opening_host_frame_authority" in source
    assert "pb_opening_dimension_authority" in source
    assert "pb_opening_height_authority" in source
    assert "pb_opening_vertical_placement_authority" in source
    assert "pb_opening_universe_completeness_authority" in source
    assert "pb_physical_scale_authority" in source
    assert "OpeningHeightSelector" in source
    assert "OpeningVerticalPlacementSelector" in source
    assert "PhysicalScaleSelector" in source
    assert "decision_scope_complete" in source
    assert "pb_page_scale_calibration_authority" not in source
    assert "measurement_authority_for_page_scale" not in source


@EXPECTED_RED
def test_source_enforces_exact_cross_authority_opening_identity_join() -> None:
    source = _source_text()
    assert "opening_identity_id" in source
    assert "opening_record_id" in source
    assert "existence_record" in source
    assert "host_binding_record_id" in source


@EXPECTED_RED
def test_source_does_not_embed_legacy_nearest_or_default_void_inference() -> None:
    source = _source_text().lower()
    forbidden_phrases = (
        "default_sill",
        "default_head",
        "typical_height",
        "default_height",
        "nearest_wall",
        "nearest_host",
        "first_host",
        "guess_sill",
        "guess_head",
        "bbox_area",
        "width * height",
        "width*height",
    )
    present = tuple(item for item in forbidden_phrases if item in source)
    assert not present, f"forbidden inferred/default void path present: {present}"


@EXPECTED_RED
def test_result_status_uses_evidence_resolution_status() -> None:
    mod = _module()
    result_type = mod.PhysicalOpeningVoidResult
    assert is_dataclass(result_type)
    result_fields = {item.name for item in fields(result_type)}
    assert {"status", "reason_codes", "record"} <= result_fields
    annotation = result_type.__annotations__.get("status")
    assert annotation is EvidenceResolutionStatus or "EvidenceResolutionStatus" in str(annotation)


@EXPECTED_RED
def test_no_public_profile_boolean_can_upgrade_unsupported_shape() -> None:
    mod = _module()
    for callable_obj in (
        mod.PhysicalOpeningVoidProducer.publish,
        mod.PhysicalOpeningVoidAuthority.resolve,
    ):
        params = _public_parameter_names(callable_obj)
        assert "profile" not in params
        assert "rectangular" not in params
        assert "is_rectangular" not in params
        assert "arch" not in params


@EXPECTED_RED
def test_no_public_host_or_completeness_claim_can_mint_void() -> None:
    mod = _module()
    params = _public_parameter_names(mod.PhysicalOpeningVoidProducer.publish)
    banned = {
        "host_wall_id",
        "wall_id",
        "host_id",
        "claimed_complete",
        "complete",
        "opening_count",
        "candidate_count",
    }
    assert not (params & banned)


@EXPECTED_RED
def test_no_public_vertical_guess_can_mint_void() -> None:
    mod = _module()
    params = _public_parameter_names(mod.PhysicalOpeningVoidProducer.publish)
    banned = {
        "sill",
        "sill_height",
        "head",
        "head_height",
        "center_z",
        "centre_z",
        "z0",
        "z1",
    }
    assert not (params & banned)


@EXPECTED_RED
def test_no_public_horizontal_guess_can_mint_void() -> None:
    mod = _module()
    params = _public_parameter_names(mod.PhysicalOpeningVoidProducer.publish)
    banned = {"u", "u0", "u1", "center_u", "centre_u", "x", "y", "position"}
    assert not (params & banned)


@EXPECTED_RED
def test_no_public_scale_or_conversion_factor_can_mint_void() -> None:
    mod = _module()
    params = _public_parameter_names(mod.PhysicalOpeningVoidProducer.publish)
    banned = {"scale", "scale_ratio", "px_per_m", "points_per_m", "unit_factor"}
    assert not (params & banned)


@EXPECTED_RED
def test_schema_exposes_no_deductible_boolean() -> None:
    mod = _module()
    record_fields = {item.name for item in fields(mod.PhysicalOpeningVoidRecord)}
    result_fields = {item.name for item in fields(mod.PhysicalOpeningVoidResult)}
    assert "deductible" not in record_fields
    assert "deductible" not in result_fields
