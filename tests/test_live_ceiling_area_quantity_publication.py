from __future__ import annotations

from dataclasses import replace

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_ceiling_area_quantity_publication import (
    LIVE_CEILING_AREA_QUANTITY_RESOLVED,
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_lining_integration import (
    LiveCanonicalCeilingSurfaceObject,
    LiveCeilingLiningResult,
)
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence


SOURCE_SHA = "a" * 64


def _shadow_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-shadow-ceiling-1",
        family="ceiling_lining",
        semantic_key="ceiling_lining:room-1",
        value=13.270425,
        unit="m2",
        input_entity_ids=("room-1",),
        formula="reuse_same_scope_authoritative_area_with_explicit_ceiling_finish",
        formula_version="1",
        evidence_ids=("ev-dim-h", "ev-dim-v", "ev-finish"),
        authority=MeasurementAuthorityType.MODEL_DERIVED.value,
        status=AuthorityStatus.PROVISIONAL.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={
            "source_sha256": SOURCE_SHA,
            "revision_id": "rev-1",
            "page_no": 1,
            "viewport_id": "vp-1",
            "upstream_area_quantity_id": "qty-room-area-1",
            "shadow_only": True,
            "commercial_projection_allowed": False,
        },
    )


def _ceiling(
    *,
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
    physical_scale_record_id: str = "",
    figured_dimension_ids: tuple[str, ...] = ("dim-h", "dim-v"),
) -> LiveCanonicalCeilingSurfaceObject:
    return LiveCanonicalCeilingSurfaceObject(
        canonical_ceiling_id="canonical-ceiling-1",
        document_id="doc-1",
        snapshot_id="snapshot-1",
        room_entity_id="room-1",
        source_page=1,
        viewport_id="vp-1",
        source_sha256=SOURCE_SHA,
        revision_id="rev-1",
        polygon_pdf_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        area_m2=13.270425,
        finish_descriptor="plasterboard",
        room_area_quantity_id="qty-room-area-1",
        ceiling_quantity_id="qty-shadow-ceiling-1",
        source_room_index_id="room-index-1",
        evidence_ids=("ev-dim-h", "ev-dim-v", "ev-finish"),
        physical_scale_record_id=physical_scale_record_id,
        measurement_authority=authority,
        figured_dimension_ids=figured_dimension_ids,
    )


def _result(ceiling=None, shadow=None) -> LiveCeilingLiningResult:
    return LiveCeilingLiningResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_ceiling_lining_resolved",),
        claims=(),
        canonical_ceilings=((ceiling or _ceiling()),),
        quantity_evidence=((shadow or _shadow_quantity()),),
    )


def test_documented_dimension_canonical_ceiling_publishes_firm_without_scale() -> None:
    quantities = publish_live_ceiling_area_quantities(_result())

    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.family == "ceiling_lining"
    assert quantity.value == 13.270425
    assert quantity.unit == "m2"
    assert quantity.input_entity_ids == ("canonical-ceiling-1",)
    assert quantity.authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
    assert quantity.status == AuthorityStatus.FIRM.value
    assert quantity.abstained is False
    assert quantity.reason_codes == (LIVE_CEILING_AREA_QUANTITY_RESOLVED,)
    assert quantity.metadata["figured_dimension_ids"] == ("dim-h", "dim-v")
    assert quantity.metadata["resolved_scale_id"] is None
    assert quantity.metadata["commercial_projection_allowed"] is False
    assert quantity.metadata["quantity_handoff_only"] is True


def test_scaled_canonical_ceiling_requires_physical_scale_record() -> None:
    missing = _ceiling(
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        physical_scale_record_id="",
        figured_dimension_ids=(),
    )
    assert publish_live_ceiling_area_quantities(_result(ceiling=missing)) == ()

    resolved = replace(
        missing,
        physical_scale_record_id="physical-scale-1",
    )
    quantities = publish_live_ceiling_area_quantities(_result(ceiling=resolved))
    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
    assert quantity.status == AuthorityStatus.FIRM.value
    assert quantity.metadata["resolved_scale_id"] == "physical-scale-1"
    assert quantity.metadata["figured_dimension_ids"] == ()


def test_documented_dimension_requires_figured_dimension_lineage() -> None:
    ceiling = _ceiling(figured_dimension_ids=())
    assert publish_live_ceiling_area_quantities(_result(ceiling=ceiling)) == ()


def test_shadow_quantity_must_match_exact_upstream_area_identity() -> None:
    shadow = _shadow_quantity()
    shadow = replace(
        shadow,
        metadata={
            **dict(shadow.metadata),
            "upstream_area_quantity_id": "other-room-area",
        },
    )
    assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()


def test_review_or_promoted_quantity_cannot_replace_shadow_lineage() -> None:
    shadow = replace(
        _shadow_quantity(),
        status=AuthorityStatus.REVIEW_REQUIRED.value,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        metadata={
            **dict(_shadow_quantity().metadata),
            "shadow_only": False,
            "commercial_projection_allowed": True,
        },
    )
    assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()


def test_quantity_identity_is_deterministic() -> None:
    first = publish_live_ceiling_area_quantities(_result())
    second = publish_live_ceiling_area_quantities(_result())

    assert len(first) == len(second) == 1
    assert first[0].to_dict() == second[0].to_dict()
    assert first[0].quantity_id == second[0].quantity_id
