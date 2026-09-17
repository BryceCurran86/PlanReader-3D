"""Behavioral adversarial tests for Item 21A wall-identity authority boundaries."""
from __future__ import annotations

from pb_live_opening_net_wall_integration import (
    LIVE_NET_WALL_IDENTITY_MISMATCH,
    LIVE_NET_WALL_RESOLVED,
    LiveOpeningNetWallAdapter,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL,
)
from pb_opening_deduction_pipeline import GenericOpeningDeductionPipeline, WallInstance


def _selector(wall_id: str) -> NetWallBooleanUnionSelector:
    return NetWallBooleanUnionSelector(
        document_id="doc-item21a",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page-1",
        decision_scope_id="scope-wall",
        physical_wall_id=wall_id,
        trade_scope_id="walls",
    )


def _record(wall_id: str, net_area_m2: float = 12.0) -> NetWallBooleanUnionRecord:
    return NetWallBooleanUnionRecord(
        record_id=f"union-{wall_id}",
        document_id="doc-item21a",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page-1",
        decision_scope_id="scope-wall",
        physical_wall_id=wall_id,
        gross_geometry_record_id=f"gross-{wall_id}",
        opening_universe_record_id=f"universe-{wall_id}",
        deduction_record_ids=(),
        union_geometry_id=f"union-geom-{wall_id}",
        net_area_m2=net_area_m2,
        gross_area_m2=15.0,
        void_union_area_m2=3.0,
        net_geometry_wkb_hex="01030000",
        physical_void_record_ids=(),
        trade_scope_id="walls",
    )


def _authority_for(selector: NetWallBooleanUnionSelector) -> NetWallBooleanUnionAuthority:
    record = _record(selector.physical_wall_id)
    result = NetWallBooleanUnionResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        record=record,
        reason_codes=("test_authenticated_wall",),
    )
    return NetWallBooleanUnionAuthority(
        {selector.key: result},
        _seal=_AUTHORITY_SEAL,
    )


def test_cross_wall_attack_authenticated_wall_a_cannot_be_relabelled_wall_b() -> None:
    """Real attack: genuine Wall A authority cannot be published under Wall B."""
    selector_a = _selector("wall_A")
    adapter = LiveOpeningNetWallAdapter(_authority_for(selector_a))

    result = adapter.resolve_wall_net_area(
        selector=selector_a,
        wall_id="wall_B",
        gross_area_m2=15.0,
    )

    assert result.is_authoritative is False
    assert result.net_area_m2 is None
    assert result.evidence.value is None
    assert result.evidence.abstained is True
    assert result.evidence.status == "conflict"
    assert LIVE_NET_WALL_IDENTITY_MISMATCH in result.reason_codes
    assert LIVE_NET_WALL_IDENTITY_MISMATCH in result.evidence.blocking_reasons


def test_exact_wall_positive_control_remains_authoritative() -> None:
    """Exact Wall A request + selector + authenticated record remains valid."""
    selector_a = _selector("wall_A")
    adapter = LiveOpeningNetWallAdapter(_authority_for(selector_a))

    result = adapter.resolve_wall_net_area(
        selector=selector_a,
        wall_id="wall_A",
        gross_area_m2=15.0,
    )

    assert result.is_authoritative is True
    assert result.net_area_m2 == 12.0
    assert result.wall_id == "wall_A"
    assert result.evidence.value == 12.0
    assert result.evidence.semantic_key == "wall_A"
    assert result.evidence.status == "corroborated"
    assert LIVE_NET_WALL_RESOLVED in result.reason_codes


def test_pipeline_wall_instance_cannot_use_another_walls_selector() -> None:
    """WallInstance wall_B cannot obtain authority through a Wall A selector map."""
    selector_a = _selector("wall_A")
    pipeline = GenericOpeningDeductionPipeline(
        net_wall_authority=_authority_for(selector_a),
        net_wall_selectors={"wall_B": selector_a},
    )
    wall_b = WallInstance(wall_id="wall_B", gross_area_m2=15.0)

    result = pipeline.calculate_wall_deductions(wall_b, [], selector=selector_a)

    assert result.wall_id == "wall_B"
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.value is None
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.status == "conflict"
    assert LIVE_NET_WALL_IDENTITY_MISMATCH in result.net_area_evidence.reason_codes


def test_caller_selector_mapping_cannot_establish_wall_equivalence() -> None:
    """A caller-provided mapping key cannot make selector Wall A equivalent to Wall B."""
    selector_a = _selector("wall_A")
    pipeline = GenericOpeningDeductionPipeline(
        net_wall_authority=_authority_for(selector_a)
    )
    wall_b = WallInstance(wall_id="wall_B", gross_area_m2=15.0)

    results = pipeline.deduct_openings_for_all_walls(
        [wall_b],
        [],
        selectors={"wall_B": selector_a},
    )

    result = results["wall_B"]
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.value is None
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.status == "conflict"
    assert LIVE_NET_WALL_IDENTITY_MISMATCH in result.net_area_evidence.reason_codes
