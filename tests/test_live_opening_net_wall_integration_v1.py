"""Unit tests for Item 21A live opening / net-wall adapter and pipeline integration.

Validates fail-closed invariants:
- missing net-wall authority leaves quantities abstained;
- exact corroborated net-wall authority may resolve at the adapter/pipeline result layer;
- prediction publication remains blocked in Item 21A;
- conflicting, stale, or mismatched evidence fails closed;
- shadow diagnostics report authority state without minting authority.

GenericPlanReaderExtractor wiring is intentionally outside this Item 21A PR and is
therefore not represented by skipped tests here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pytest

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
from pb_live_opening_net_wall_integration import (
    LIVE_NET_WALL_AUTHORITY_UNAVAILABLE,
    LIVE_NET_WALL_RESOLVED,
    LIVE_NET_WALL_UPSTREAM_UNRESOLVED,
    LiveOpeningNetWallAdapter,
    collect_live_net_wall_shadow,
)


@dataclass
class _Prediction:
    """Minimal test fixture for prediction propagation."""

    tag: str
    trade_type: str
    quantity: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


def _make_selector(wall_id: str = "perimeter_walling") -> NetWallBooleanUnionSelector:
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


def _make_corroborated_record(
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


def _make_authority(
    mapping: dict[Any, NetWallBooleanUnionResult] | None = None,
) -> NetWallBooleanUnionAuthority:
    results = {}
    if mapping:
        for key_or_selector, value in mapping.items():
            key = (
                key_or_selector.key
                if hasattr(key_or_selector, "key")
                else key_or_selector
            )
            results[key] = value
    return NetWallBooleanUnionAuthority(results, _seal=_AUTHORITY_SEAL)


class TestLiveOpeningNetWallAdapter:
    """LiveOpeningNetWallAdapter fail-closed semantics."""

    def test_adapter_without_authority_abstains(self) -> None:
        adapter = LiveOpeningNetWallAdapter(net_wall_authority=None)
        sel = _make_selector()
        res = adapter.resolve_wall_net_area(
            sel, wall_id="perimeter_walling", gross_area_m2=100.0
        )

        assert not res.is_authoritative
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True
        assert res.evidence.value is None
        assert res.evidence.status == "abstained"
        assert LIVE_NET_WALL_AUTHORITY_UNAVAILABLE in res.reason_codes

    def test_adapter_without_selector_abstains(self) -> None:
        auth = _make_authority()
        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            selector=None,
            wall_id="perimeter_walling",
            gross_area_m2=100.0,
        )

        assert not res.is_authoritative
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True

    def test_adapter_corroborated_resolution(self) -> None:
        sel = _make_selector()
        record = _make_corroborated_record(
            gross_area_m2=100.0,
            net_area_m2=85.0,
        )
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            record=record,
            reason_codes=("test_corroborated",),
        )
        auth = _make_authority({sel: res_obj})

        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            sel,
            wall_id="perimeter_walling",
            gross_area_m2=100.0,
        )

        assert res.is_authoritative is True
        assert res.net_area_m2 == 85.0
        assert res.evidence.abstained is False
        assert res.evidence.status == "corroborated"
        assert res.evidence.value == 85.0
        assert res.evidence.family == "wall_net_area"
        assert res.union_record_id == "union-rec-1"
        assert LIVE_NET_WALL_RESOLVED in res.reason_codes
        assert "test_corroborated" in res.reason_codes

    def test_adapter_conflict_resolution_abstains(self) -> None:
        sel = _make_selector()
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CONFLICT,
            record=None,
            reason_codes=("geometry_clash",),
        )
        auth = _make_authority({sel: res_obj})

        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            sel,
            wall_id="perimeter_walling",
            gross_area_m2=100.0,
        )

        assert res.is_authoritative is False
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True
        assert res.evidence.status == "conflict"
        assert res.evidence.value is None
        assert LIVE_NET_WALL_UPSTREAM_UNRESOLVED in res.reason_codes
        assert "geometry_clash" in res.reason_codes

    def test_adapter_upstream_abstained_resolution(self) -> None:
        sel = _make_selector()
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            record=None,
            reason_codes=("missing_gross_wall_record",),
        )
        auth = _make_authority({sel: res_obj})

        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            sel,
            wall_id="perimeter_walling",
            gross_area_m2=100.0,
        )

        assert res.is_authoritative is False
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True
        assert res.evidence.status == "abstained"
        assert res.evidence.value is None


class TestGenericOpeningDeductionPipelineIntegration:
    """Pipeline integration with NetWallBooleanUnionAuthority."""

    def test_pipeline_without_authority_remains_fail_closed(self) -> None:
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

        assert result.net_area_evidence is not None
        assert result.net_area_evidence.abstained is True
        assert result.net_area_evidence.value is None

        preds = [
            _Prediction(
                tag="perimeter_walling",
                trade_type="walls",
                quantity=100.0,
            )
        ]
        out = pipeline.propagate_to_predictions(
            preds,
            {"perimeter_walling": result},
        )
        assert out[0].quantity is None
        assert out[0].metadata["publication_blocked"] is True
        assert out[0].metadata["net_area_m2"] is None
        assert out[0].metadata["provisional_net_area_m2"] == 97.0

    def test_pipeline_with_corroborated_authority_resolves_but_prediction_stays_blocked(
        self,
    ) -> None:
        wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
        opening = OpeningInstance(
            opening_id="W1",
            width_m=1.0,
            height_m=1.5,
            quantity=2.0,
            bound_wall_id="perimeter_walling",
        )

        sel = _make_selector("perimeter_walling")
        record = _make_corroborated_record(
            gross_area_m2=100.0,
            net_area_m2=97.0,
        )
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            record=record,
            reason_codes=("authoritative_union_match",),
        )
        auth = _make_authority({sel: res_obj})

        pipeline = GenericOpeningDeductionPipeline(
            net_wall_authority=auth,
            net_wall_selectors={"perimeter_walling": sel},
        )
        results = pipeline.deduct_openings_for_all_walls([wall], [opening])
        res = results["perimeter_walling"]

        assert res.net_area_m2 == 97.0
        assert res.total_deducted_area_m2 == 3.0
        assert res.net_area_evidence is not None
        assert res.net_area_evidence.abstained is False
        assert res.net_area_evidence.value == 97.0
        assert res.net_area_evidence.status == "corroborated"

        preds = [
            _Prediction(
                tag="perimeter_walling",
                trade_type="walls",
                quantity=100.0,
            ),
            _Prediction(
                tag="internal_plaster",
                trade_type="wall_finish",
                quantity=100.0,
            ),
        ]
        out = pipeline.propagate_to_predictions(preds, results)
        by_tag = {prediction.tag: prediction for prediction in out}

        assert by_tag["perimeter_walling"].quantity is None
        assert by_tag["perimeter_walling"].metadata["publication_blocked"] is True
        assert by_tag["perimeter_walling"].metadata["provisional_net_area_m2"] == 97.0
        assert by_tag["perimeter_walling"].metadata["net_area_m2"] is None

        assert by_tag["internal_plaster"].quantity is None
        assert by_tag["internal_plaster"].metadata["publication_blocked"] is True
        assert by_tag["internal_plaster"].metadata["provisional_net_area_m2"] == 97.0

    def test_pipeline_with_conflicted_authority_fails_closed(self) -> None:
        wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
        opening = OpeningInstance(
            opening_id="W1",
            width_m=1.0,
            height_m=1.5,
            quantity=2.0,
            bound_wall_id="perimeter_walling",
        )

        sel = _make_selector("perimeter_walling")
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CONFLICT,
            record=None,
            reason_codes=("geometry_discrepancy",),
        )
        auth = _make_authority({sel: res_obj})

        pipeline = GenericOpeningDeductionPipeline(
            net_wall_authority=auth,
            net_wall_selectors={"perimeter_walling": sel},
        )
        results = pipeline.deduct_openings_for_all_walls([wall], [opening])
        res = results["perimeter_walling"]

        assert res.net_area_evidence is not None
        assert res.net_area_evidence.abstained is True
        assert res.net_area_evidence.status == "conflict"

        preds = [
            _Prediction(
                tag="perimeter_walling",
                trade_type="walls",
                quantity=100.0,
            )
        ]
        out = pipeline.propagate_to_predictions(preds, results)
        assert out[0].quantity is None
        assert out[0].metadata["publication_blocked"] is True


class TestShadowAndAdapterIntegration:
    """Shadow collection and adapter boundary regressions."""

    def test_collect_live_net_wall_shadow_summary(self) -> None:
        pipeline = GenericOpeningDeductionPipeline()
        wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=100.0)
        unresolved_opening = OpeningInstance(
            opening_id="W1",
            width_m=None,
            height_m=None,
            quantity=1.0,
        )
        wall_results = pipeline.deduct_openings_for_all_walls(
            [wall],
            [unresolved_opening],
        )

        shadow = collect_live_net_wall_shadow(wall_results)
        assert shadow["status"] == "collected"
        assert shadow["total_walls"] == 1
        assert shadow["authoritative_count"] == 0
        assert shadow["blocked_count"] == 1
        assert shadow["walls"][0]["wall_id"] == "perimeter_walling"
        assert shadow["walls"][0]["is_authoritative"] is False
        assert shadow["walls"][0]["net_area_m2"] is None

    def test_duck_typed_selector_rejected(self) -> None:
        auth = _make_authority()
        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        with pytest.raises(TypeError, match="selector must be NetWallBooleanUnionSelector"):
            adapter.resolve_wall_net_area(
                selector={"physical_wall_id": "w1"}  # type: ignore[arg-type]
            )

    def test_wrong_wall_id_record_fails_closed(self) -> None:
        sel = _make_selector("perimeter_walling")
        record = _make_corroborated_record(
            wall_id="other_wall",
            gross_area_m2=100.0,
            net_area_m2=97.0,
        )
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            record=record,
            reason_codes=("corroborated",),
        )
        auth = _make_authority({sel: res_obj})
        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            sel,
            wall_id="perimeter_walling",
        )
        assert res.is_authoritative is False
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True

    def test_mismatched_lineage_fails_closed(self) -> None:
        sel = _make_selector("perimeter_walling")
        rec_dict = _make_corroborated_record(
            "perimeter_walling",
            100.0,
            97.0,
        ).__dict__.copy()
        rec_dict["document_id"] = "doc-stale-999"
        record = NetWallBooleanUnionRecord(**rec_dict)
        res_obj = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            record=record,
            reason_codes=("corroborated",),
        )
        auth = _make_authority({sel: res_obj})
        adapter = LiveOpeningNetWallAdapter(net_wall_authority=auth)
        res = adapter.resolve_wall_net_area(
            sel,
            wall_id="perimeter_walling",
        )
        assert res.is_authoritative is False
        assert res.net_area_m2 is None
        assert res.evidence.abstained is True
