from __future__ import annotations

import inspect

import pytest
from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE,
    NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionProducer,
    NetWallBooleanUnionSelector,
    deterministic_net_wall_record_id,
    subtract_void_union_from_wall_polygon,
    union_wall_local_void_polygons,
)


def _selector() -> NetWallBooleanUnionSelector:
    return NetWallBooleanUnionSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="page-1",
        decision_scope_id="full-page",
        physical_wall_id="wall-1",
        trade_scope_id="wall-finish",
    )


def test_geometry_union_deduplicates_overlap_geometrically() -> None:
    left = box(0, 0, 2, 2)
    right = box(1, 0, 3, 2)
    merged = union_wall_local_void_polygons((left, right))
    assert merged.area == pytest.approx(6.0)


def test_subtraction_uses_union_not_scalar_sum() -> None:
    gross = box(0, 0, 10, 3)
    first = box(2, 0, 4, 2)
    second = box(3, 1, 5, 3)
    assert subtract_void_union_from_wall_polygon(gross, (first, second)).area == pytest.approx(23.0)


def test_geometry_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        subtract_void_union_from_wall_polygon(None, ())  # type: ignore[arg-type]


def test_authority_and_producer_are_sealed() -> None:
    with pytest.raises(ValueError):
        NetWallBooleanUnionAuthority({})
    with pytest.raises(ValueError):
        NetWallBooleanUnionProducer()


def test_public_resolver_is_selector_only() -> None:
    assert tuple(inspect.signature(NetWallBooleanUnionAuthority.resolve).parameters) == ("self", "selector")
    selector_fields = tuple(inspect.signature(NetWallBooleanUnionSelector).parameters)
    assert "physical_wall_id" in selector_fields
    for forbidden in ("polygon", "voids", "void_areas", "complete", "nearest", "radius", "confidence", "net_area"):
        assert not any(forbidden in field for field in selector_fields)


def test_from_authorities_has_no_raw_geometry_or_self_certification_inputs() -> None:
    params = tuple(inspect.signature(NetWallBooleanUnionProducer.from_authorities).parameters)
    for forbidden in (
        "gross_polygon",
        "void_polygons",
        "void_areas",
        "opening_ids",
        "deductible",
        "claimed_complete",
        "candidate_wall_ids",
        "nearest_wall_id",
    ):
        assert forbidden not in params


def test_positive_producer_construction_rejects_wrong_or_unavailable_authorities() -> None:
    """Remain fail-closed as the real upstream authority modules progressively land.

    Before an upstream module exists, construction stops with the explicit
    unavailable reason.  Once that module exists, an arbitrary caller object must
    instead be rejected as the wrong exact producer-owned type.  Both states are
    intentionally fail-closed; this regression must not depend on which prerequisite
    happened to have merged at the time the branch was created.
    """
    with pytest.raises((RuntimeError, TypeError)) as caught:
        NetWallBooleanUnionProducer.from_authorities(object(), object(), object(), object())

    if isinstance(caught.value, RuntimeError):
        assert NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE in str(caught.value)
    else:
        assert "instance required" in str(caught.value)


def test_missing_selector_record_abstains_not_zero() -> None:
    producer = NetWallBooleanUnionProducer(_seal=__import__("pb_net_wall_boolean_union_authority")._PRODUCER_SEAL)
    authority = producer.authority()
    result = authority.resolve(_selector())
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE in result.reason_codes


def test_record_id_is_deterministic_addressing_only() -> None:
    selector = _selector()
    first = deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-1",
        opening_deduction_record_ids=("d2", "d1"),
        physical_void_record_ids=("v2", "v1"),
    )
    second = deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-1",
        opening_deduction_record_ids=("d1", "d2"),
        physical_void_record_ids=("v1", "v2"),
    )
    assert first == second
