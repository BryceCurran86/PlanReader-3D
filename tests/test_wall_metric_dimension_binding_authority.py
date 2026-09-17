from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_migration_provider_envelope import ProviderContext
from pb_wall_metric_dimension_binding_authority import (
    WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH,
    WALL_METRIC_DIMENSION_BINDING_RESOLVED,
    WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED,
    WallMetricDimensionBindingRecord,
    WallMetricDimensionBindingSelector,
    bind_wall_metric_dimensions,
)


_SOURCE_SHA = "a" * 64


def _context() -> ProviderContext:
    return ProviderContext(
        run_id="run-1",
        workspace_id="workspace-1",
        project_id="project-1",
        document_id="document-1",
        source_sha256=_SOURCE_SHA,
        revision_id="rev-1",
        current_revision_id="rev-1",
        selected_pages=(0,),
        owned_viewport_ids=("vp-1",),
        evidence_snapshot_id="evidence-snapshot-1",
        canonical_graph_snapshot_id="graph-snapshot-1",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-1", 1),),
    )


def _selector(**overrides: object) -> WallMetricDimensionBindingSelector:
    values: dict[str, object] = {
        "document_id": "document-1",
        "source_sha256": _SOURCE_SHA,
        "revision_id": "rev-1",
        "evidence_snapshot_id": "evidence-snapshot-1",
        "viewport_id": "vp-1",
        "page_no": 1,
        "physical_wall_id": "wall-A",
    }
    values.update(overrides)
    return WallMetricDimensionBindingSelector(**values)  # type: ignore[arg-type]


def _quantity(
    family: str,
    value: float,
    *,
    wall_id: str = "wall-A",
    viewport_id: str = "vp-1",
    page_no: int = 1,
    source_sha256: str = _SOURCE_SHA,
    revision_id: str = "rev-1",
    evidence_snapshot_id: str = "evidence-snapshot-1",
    graph_snapshot_id: str = "graph-snapshot-1",
    status: str = AuthorityStatus.FIRM.value,
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"qty-{family}-{wall_id}-{viewport_id}-{page_no}-{value}",
        family=family,
        semantic_key=f"{family}:{wall_id}",
        value=value,
        unit="m",
        input_entity_ids=(wall_id,),
        formula="source-backed measurement",
        formula_version="1.0",
        evidence_ids=(f"ev-{family}-{wall_id}",),
        authority=authority,
        status=status,
        confidence=0.99,
        abstained=False,
        metadata={
            "source_sha256": source_sha256,
            "revision_id": revision_id,
            "viewport_id": viewport_id,
            "page_id": f"page-{page_no}",
            "page_no": page_no,
            "evidence_snapshot_id": evidence_snapshot_id,
            "canonical_graph_snapshot_id": graph_snapshot_id,
        },
    )


def _bind(
    *,
    selector: WallMetricDimensionBindingSelector | None = None,
    length: QuantityEvidence | None = None,
    height: QuantityEvidence | None = None,
):
    return bind_wall_metric_dimensions(
        selector=selector or _selector(),
        context=_context(),
        wall_length=length or _quantity("wall_length", 6.0),
        wall_height=height or _quantity("wall_height", 2.7),
    )


def test_firm_same_wall_dimensions_publish_deterministic_binding() -> None:
    first = _bind()
    second = _bind()

    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.reason_codes == (WALL_METRIC_DIMENSION_BINDING_RESOLVED,)
    assert first.record is not None
    assert second.record is not None
    assert first.record.record_id == second.record.record_id
    assert first.record.physical_wall_id == "wall-A"
    assert first.record.length_m == pytest.approx(6.0)
    assert first.record.height_m == pytest.approx(2.7)
    assert first.record.gross_area_m2 == pytest.approx(16.2)
    assert first.record.viewport_id == "vp-1"
    assert first.record.page_no == 1
    assert first.record.context_fingerprint == _context().fingerprint()


def test_binding_contract_does_not_publish_source_space_geometry() -> None:
    result = _bind()
    assert result.record is not None

    assert not hasattr(result.record, "polygon")
    assert not hasattr(result.record, "u0_pt")
    assert not hasattr(result.record, "u1_pt")
    assert not hasattr(result.record, "geometry")


def test_wrong_physical_wall_fails_closed() -> None:
    height = _quantity("wall_height", 2.7, wall_id="wall-B")
    result = _bind(height=height)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_height_identity_mismatch" in result.reason_codes


def test_selector_viewport_mismatch_fails_before_dimension_binding() -> None:
    result = _bind(selector=_selector(viewport_id="vp-other"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert result.reason_codes == (WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH,)


def test_dimension_viewport_mismatch_fails_closed_even_when_viewport_is_trusted() -> None:
    context = ProviderContext(
        run_id="run-1",
        workspace_id="workspace-1",
        project_id="project-1",
        document_id="document-1",
        source_sha256=_SOURCE_SHA,
        revision_id="rev-1",
        current_revision_id="rev-1",
        selected_pages=(0,),
        owned_viewport_ids=("vp-1", "vp-2"),
        evidence_snapshot_id="evidence-snapshot-1",
        canonical_graph_snapshot_id="graph-snapshot-1",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-1", 1), ("vp-2", 1)),
    )
    result = bind_wall_metric_dimensions(
        selector=_selector(),
        context=context,
        wall_length=_quantity("wall_length", 6.0, viewport_id="vp-2"),
        wall_height=_quantity("wall_height", 2.7, viewport_id="vp-2"),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH in result.reason_codes
    assert "wall_length_viewport_mismatch" in result.reason_codes


def test_stale_evidence_snapshot_fails_closed() -> None:
    height = _quantity(
        "wall_height",
        2.7,
        evidence_snapshot_id="old-evidence-snapshot",
    )
    result = _bind(height=height)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_height_evidence_snapshot_stale" in result.reason_codes


def test_stale_revision_fails_closed() -> None:
    length = _quantity("wall_length", 6.0, revision_id="rev-old")
    result = _bind(length=length)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_length_revision_stale" in result.reason_codes


def test_nonfirm_dimension_fails_closed() -> None:
    height = _quantity(
        "wall_height",
        2.7,
        status=AuthorityStatus.PROVISIONAL.value,
    )
    result = _bind(height=height)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_height_not_firm" in result.reason_codes


def test_zero_dimension_fails_closed() -> None:
    height = _quantity("wall_height", 0.0)
    result = _bind(height=height)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_height_value_invalid" in result.reason_codes


def test_untrusted_height_authority_fails_closed() -> None:
    height = _quantity(
        "wall_height",
        2.7,
        authority=MeasurementAuthorityType.PDF_SCALED.value,
    )
    result = _bind(height=height)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED in result.reason_codes
    assert "wall_height_authority_not_trusted" in result.reason_codes


def test_record_cannot_be_caller_constructed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallMetricDimensionBindingRecord(
            record_id="record",
            document_id="document-1",
            source_sha256=_SOURCE_SHA,
            revision_id="rev-1",
            evidence_snapshot_id="evidence-snapshot-1",
            canonical_graph_snapshot_id="graph-snapshot-1",
            viewport_id="vp-1",
            page_no=1,
            physical_wall_id="wall-A",
            length_m=6.0,
            height_m=2.7,
            gross_area_m2=16.2,
            wall_length_quantity_id="length",
            wall_height_quantity_id="height",
            gross_area_quantity_id="gross",
            wall_length_fingerprint="length-fp",
            wall_height_fingerprint="height-fp",
            context_fingerprint="context-fp",
        )
