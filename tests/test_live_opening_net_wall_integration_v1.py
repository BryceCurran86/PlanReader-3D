"""Unit tests for Item 21A live opening / net-wall adapter and pipeline integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest

from pb_live_opening_net_wall_integration import (
    LIVE_NET_WALL_AUTHORITY_UNAVAILABLE,
    LIVE_NET_WALL_IDENTITY_MISMATCH,
    LIVE_NET_WALL_RESOLVED,
    LIVE_NET_WALL_UPSTREAM_UNRESOLVED,
    LiveOpeningNetWallAdapter,
    collect_live_net_wall_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL,
)
from pb_opening_deduction_pipeline import (
    GenericOpeningDeductionPipeline,
    OpeningInstance,
    WallInstance,
)


@dataclass
class _Prediction:
    tag: str
    trade_type: str
    quantity: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


def _selector(wall_id: str = "perimeter_walling") -> NetWallBooleanUnionSelector:
    return NetWallBooleanUnionSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="sha-1",
        snapshot_id="snap-1",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id=wall_id,
        trade_scope_id="walls",
    )


def _record(
    wall_id: str = "perimeter_walling",
    gross_area_m2: float = 100.0,
    net_area_m2: float = 85.0,
) -> NetWallBooleanUnionRecord:
    return NetWallBooleanUnionRecord(
        record_id="union-rec-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="sha-1",
        snapshot_id="snap-1",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        physical_wall_id=wall_id,
        gross_geometry_record_id="gross-rec-1",
        opening_universe_record_id="univ-1",
        deduction_record_ids=("ded-1",),
        union_geometry_id="geom-union-1",
        net_area_m2=net_area_m2,
        gross_area_m2=gross_area_m2,
        void_union_area_m2=gross_area_m2 - net_area_m2,
        net_geometry_wkb_hex="01030000",
        physical_void_record_ids=("void-1",),
        trade_scope_id="walls",
    )


def _authority(
    selector: NetWallBooleanUnionSelector,
    *,
    record: NetWallBooleanUnionRecord | None = None,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reason: str = "test_corroborated",
) -> NetWallBooleanUnionAuthority:
    result = NetWallBooleanUnionResult(
        status=status,
        record=record if record is not None else (_record(selector.physical_wall_id) if status is EvidenceResolutionStatus.CORROBORATED else None),
        reason_codes=(reason,),
    )
    return NetWallBooleanUnionAuthority(
        {selector.key: result},
        _seal=_AUTHORITY_SEAL,
    )


def test_adapter_without_authority_abstains() -> None:
    selector = _selector()
    result = LiveOpeningNetWallAdapter().resolve_wall_net_area(
        selector,
        wall_id="perimeter_walling",
        gross_area_m2=100.0,
    )
    assert result.is_authoritative is False
    assert result.net_area_m2 is None
    assert result.evidence.value is None
    assert result.evidence.abstained is True
    assert LIVE_NET_WALL_AUTHORITY_UNAVAILABLE in result.reason_codes


def test_adapter_exact_corroborated_resolution() -> None:
    selector = _selector()
    authority = _authority(selector, record=_record(net_area_m2=85.0))
    result = LiveOpeningNetWallAdapter(authority).resolve_wall_net_area(
        selector,
        wall_id="perimeter_walling",
        gross_area_m2=100.0,
    )
    assert result.is_authoritative is True
    assert result.net_area_m2 == 85.0
    assert result.evidence.value == 85.0
    assert result.evidence.status == "corroborated"
    assert result.evidence.semantic_key == "perimeter_walling"
    assert LIVE_NET_WALL_RESOLVED in result.reason_codes


def test_adapter_upstream_conflict_stays_blocked() -> None:
    selector = _selector()
    authority = _authority(
        selector,
        status=EvidenceResolutionStatus.CONFLICT,
        reason="geometry_clash",
    )
    result = LiveOpeningNetWallAdapter(authority).resolve_wall_net_area(
        selector,
        wall_id="perimeter_walling",
    )
    assert result.is_authoritative is False
    assert result.net_area_m2 is None
    assert result.evidence.value is None
    assert result.evidence.status == "conflict"
    assert LIVE_NET_WALL_UPSTREAM_UNRESOLVED in result.reason_codes


def test_duck_typed_selector_rejected() -> None:
    selector = _selector()
    adapter = LiveOpeningNetWallAdapter(_authority(selector))
    with pytest.raises(TypeError, match="selector must be NetWallBooleanUnionSelector"):
        adapter.resolve_wall_net_area(
            selector={"physical_wall_id": "w1"}  # type: ignore[arg-type]
        )


def test_record_wall_mismatch_fails_closed() -> None:
    selector = _selector("perimeter_walling")
    authority = _authority(
        selector,
        record=_record("other_wall", net_area_m2=97.0),
    )
    result = LiveOpeningNetWallAdapter(authority).resolve_wall_net_area(
        selector,
        wall_id="perimeter_walling",
    )
    assert result.is_authoritative is False
    assert result.net_area_m2 is None
    assert result.evidence.value is None


def test_stale_record_lineage_fails_closed() -> None:
    selector = _selector("perimeter_walling")
    payload = _record("perimeter_walling", 100.0, 97.0).__dict__.copy()
    payload["document_id"] = "doc-stale"
    authority = _authority(selector, record=NetWallBooleanUnionRecord(**payload))
    result = LiveOpeningNetWallAdapter(authority).resolve_wall_net_area(
        selector,
        wall_id="perimeter_walling",
    )
    assert result.is_authoritative is False
    assert result.net_area_m2 is None
    assert result.evidence.value is None


def test_pipeline_without_authority_remains_fail_closed() -> None:
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    opening = OpeningInstance(
        opening_id="W1",
        width_m=1.0,
        height_m=1.5,
        quantity=2.0,
        bound_wall_id="perimeter_walling",
    )
    pipeline = GenericOpeningDeductionPipeline()
    result = pipeline.calculate_wall_deductions(wall, [opening])
    prediction = _Prediction(
        tag="perimeter_walling",
        trade_type="walls",
        quantity=100.0,
    )
    output = pipeline.propagate_to_predictions(
        [prediction],
        {"perimeter_walling": result},
    )[0]
    assert output.quantity is None
    assert output.metadata["publication_blocked"] is True
    assert output.metadata["net_area_m2"] is None
    assert output.metadata["provisional_net_area_m2"] == 97.0


def test_pipeline_exact_authority_resolves_but_prediction_publication_stays_blocked() -> None:
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    selector = _selector("perimeter_walling")
    authority = _authority(
        selector,
        record=_record("perimeter_walling", 100.0, 97.0),
    )
    pipeline = GenericOpeningDeductionPipeline(
        net_wall_authority=authority,
        net_wall_selectors={"perimeter_walling": selector},
    )
    results = pipeline.deduct_openings_for_all_walls([wall], [])
    assert results["perimeter_walling"].net_area_evidence is not None
    assert results["perimeter_walling"].net_area_evidence.value == 97.0

    wall_prediction = _Prediction(
        tag="perimeter_walling",
        trade_type="walls",
        quantity=100.0,
    )
    finish_prediction = _Prediction(
        tag="internal_plaster",
        trade_type="wall_finish",
        quantity=100.0,
        metadata={"physical_wall_id": "perimeter_walling"},
    )
    output = pipeline.propagate_to_predictions(
        [wall_prediction, finish_prediction],
        results,
    )
    by_tag = {prediction.tag: prediction for prediction in output}
    for tag in ("perimeter_walling", "internal_plaster"):
        assert by_tag[tag].quantity is None
        assert by_tag[tag].metadata["publication_blocked"] is True
        assert by_tag[tag].metadata["net_area_m2"] is None
        assert by_tag[tag].metadata["provisional_net_area_m2"] == 97.0
        assert by_tag[tag].metadata["resolved_physical_wall_id"] == "perimeter_walling"


def test_unbound_finish_prediction_cannot_borrow_primary_wall_diagnostics() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    result = pipeline.calculate_wall_deductions(wall, [])
    finish = _Prediction(
        tag="internal_plaster",
        trade_type="wall_finish",
        quantity=100.0,
    )
    output = pipeline.propagate_to_predictions(
        [finish],
        {"perimeter_walling": result},
    )[0]
    assert output.quantity is None
    assert output.metadata["publication_blocked"] is True
    assert output.metadata["net_area_m2"] is None
    assert output.metadata["provisional_net_area_m2"] is None
    assert output.metadata["reconciliation_status"] == "item_21a_no_exact_physical_wall_binding"


def test_wrong_wall_finish_identity_cannot_borrow_another_wall_result() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall_a = WallInstance(wall_id="wall_A", gross_area_m2=15.0)
    result_a = pipeline.calculate_wall_deductions(wall_a, [])
    finish_b = _Prediction(
        tag="internal_plaster",
        trade_type="wall_finish",
        quantity=12.0,
        metadata={"physical_wall_id": "wall_B"},
    )
    output = pipeline.propagate_to_predictions(
        [finish_b],
        {"wall_A": result_a},
    )[0]
    assert output.quantity is None
    assert output.metadata["provisional_net_area_m2"] is None
    assert output.metadata["publication_blocked"] is True


def test_pipeline_selector_map_mismatch_returns_explicit_identity_conflict() -> None:
    selector_a = _selector("wall_A")
    pipeline = GenericOpeningDeductionPipeline(
        net_wall_authority=_authority(selector_a),
        net_wall_selectors={"wall_B": selector_a},
    )
    result = pipeline.calculate_wall_deductions(
        WallInstance(wall_id="wall_B", gross_area_m2=15.0),
        [],
        selector=selector_a,
    )
    assert result.net_area_evidence is not None
    assert result.net_area_evidence.value is None
    assert result.net_area_evidence.status == "conflict"
    assert LIVE_NET_WALL_IDENTITY_MISMATCH in result.net_area_evidence.reason_codes


def test_collect_live_net_wall_shadow_summary() -> None:
    pipeline = GenericOpeningDeductionPipeline()
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
    results = pipeline.deduct_openings_for_all_walls([wall], [])
    shadow = collect_live_net_wall_shadow(results)
    assert shadow["status"] == "collected"
    assert shadow["total_walls"] == 1
    assert shadow["authoritative_count"] == 0
    assert shadow["blocked_count"] == 1
