"""Tests for firm ceiling quantity publication from final room-area authority."""
from __future__ import annotations

from dataclasses import replace

import pb_cross_view_ceiling_finish_authority as finish_authority
import pb_cross_view_ceiling_quantity_authority as ceiling_quantity
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
)
from pb_source_room_area_bridge import SourceRoomAreaBridgeResult
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication


SOURCE_SHA = "a" * 64


def _room() -> LiveCanonicalRoomObject:
    return LiveCanonicalRoomObject(
        canonical_room_id="canonical-room-1",
        physical_room_id="physical-room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SOURCE_SHA,
        snapshot_id="snap-1",
        page_id="7",
        viewport_id="floor-vp",
        decision_scope_id="scope-1",
        polygon_pdf_pts=(
            (0.0, 0.0),
            (100.0, 0.0),
            (100.0, 80.0),
            (0.0, 80.0),
        ),
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=("cw1", "cw2", "cw3", "cw4"),
        wall_relationships_complete=True,
        area_page_pts2=8000.0,
        source_room_face_record_id="face-1",
        evidence_ids=("room-evidence",),
        geometry_complete=True,
        metric_geometry_complete=False,
        room_label="OFFICE",
        room_label_binding_record_id="label-binding-1",
        room_label_evidence_ids=("room-label-evidence",),
    )


def _rooms() -> LiveCanonicalRoomComposition:
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        rooms=(_room(),),
        source_pages=(7,),
    )


def _bridge(
    *,
    face_id: str = "face-1",
    quantity_id: str = "room-area-qty-1",
    authority: str = "documented_dimension",
) -> SourceRoomAreaBridgeResult:
    entity = EntityEvidence(
        candidate_entity_id="source-room-1",
        candidate_type="room",
        evidence_ids=(face_id, "room-geometry-evidence"),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        reason_codes=("source_room_face_entity_bound",),
        metadata={
            "source_sha256": SOURCE_SHA,
            "revision_id": "rev-1",
            "page_id": "7",
            "page_no": 7,
            "viewport_id": "floor-vp",
            "source_room_index_id": "room-index-1",
        },
    )
    metadata = {
        "source_sha256": SOURCE_SHA,
        "revision_id": "rev-1",
        "page_no": 7,
        "viewport_id": "floor-vp",
        "room_label": "OFFICE",
    }
    if authority == "documented_dimension":
        metadata["figured_dimension_ids"] = ["dim-h", "dim-v"]
        metadata["scale_fingerprint"] = None
    else:
        metadata["figured_dimension_ids"] = []
        metadata["scale_fingerprint"] = "scale-fingerprint-1"

    quantity = QuantityEvidence(
        quantity_id=quantity_id,
        family="room_area",
        semantic_key="room_area:source-room-1",
        value=9.05352,
        unit="m2",
        input_entity_ids=("source-room-1",),
        formula="authoritative_explicit_area",
        formula_version="1.1.0",
        evidence_ids=(face_id, "room-geometry-evidence"),
        authority=authority,
        status="firm",
        confidence=1.0,
        abstained=False,
        metadata=metadata,
    )
    document = DocumentEvidence(
        document_id="doc-1",
        source_sha256=SOURCE_SHA,
        page_count=1,
        evidence_ids=(face_id, "room-geometry-evidence"),
        producer="test",
        producer_version="1",
    )
    return SourceRoomAreaBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        room_index=None,
        document=document,
        entities=(entity,),
        quantities=(quantity,),
    )


def _finish(*, face_id: str = "face-1"):
    record = finish_authority.CrossViewCeilingFinishRecord(
        record_id="ceiling-finish-record",
        physical_room_id="physical-room-1",
        canonical_room_id="canonical-room-1",
        source_room_face_record_id=face_id,
        room_label="OFFICE",
        support_page_id="9",
        support_viewport_id="rcp-vp",
        support_source_partition_id="partition-9",
        support_block_no=12,
        room_label_observation_ids=("rcp-label-obs",),
        room_label_receipt_ids=("rcp-label-receipt",),
        finish_code="GRID",
        semantic_finish="ceiling_grid",
        definition_record_id="def-grid",
        definition_evidence_ids=("def-evidence",),
        occurrence_record_id="occ-grid",
        occurrence_evidence_id="occ-evidence",
        occurrence_observation_ids=("rcp-finish-obs",),
        occurrence_receipt_ids=("rcp-finish-receipt",),
        occurrence_bbox_pdf_pts=(100.0, 70.0, 125.0, 82.0),
        support_snapshot_id="semantic-snap-1",
        _seal=finish_authority._RECORD_SEAL,
    )
    return finish_authority.CrossViewCeilingFinishResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        records=(record,),
        unresolved_physical_room_ids=(),
    )


def test_final_documented_room_area_and_rcp_finish_publish_firm_ceiling_quantity() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(_bridge(),),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.unresolved_physical_room_ids == ()
    assert len(result.records) == 1
    record = result.records[0]
    quantity = record.quantity
    assert record.canonical_ceiling_id == record.physical_ceiling_surface_id
    assert record.physical_room_id == "physical-room-1"
    assert record.upstream_room_area_quantity_id == "room-area-qty-1"
    assert quantity.family == "ceiling_lining"
    assert quantity.value == 9.05352
    assert quantity.unit == "m2"
    assert quantity.authority == "documented_dimension"
    assert quantity.status == "firm"
    assert quantity.abstained is False
    assert quantity.input_entity_ids == (record.canonical_ceiling_id,)
    assert quantity.metadata["figured_dimension_ids"] == ["dim-h", "dim-v"]
    assert quantity.metadata["upstream_room_area_quantity_id"] == "room-area-qty-1"
    assert quantity.metadata["support_page_id"] == "9"
    assert quantity.metadata["support_viewport_id"] == "rcp-vp"
    assert quantity.metadata["support_snapshot_id"] == "semantic-snap-1"
    assert quantity.metadata["row_role"] == "ceiling_area"
    assert quantity.metadata["commercial_projection_allowed"] is True
    assert quantity.metadata.get("quantity_handoff_only") is not True
    assert len(result.canonical_ceilings) == 1
    canonical = result.canonical_ceilings[0]
    assert canonical.canonical_ceiling_id == record.canonical_ceiling_id
    assert canonical.room_entity_id == "canonical-room-1"
    assert canonical.room_area_quantity_id == "room-area-qty-1"
    assert canonical.ceiling_quantity_id == quantity.quantity_id
    assert canonical.measurement_authority == "documented_dimension"
    assert canonical.figured_dimension_ids == ("dim-h", "dim-v")
    assert canonical.finish_descriptor == "ceiling_grid"


def test_scaled_room_area_stays_out_of_documented_rcp_ceiling_path() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(_bridge(authority="pdf_scaled"),),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.canonical_ceilings == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_firm_canonical_ceiling_quantity_advances_ag09_to_quantified() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(_bridge(),),
        finishes=_finish(),
    )

    summaries, gaps = collect_live_canonical_coverage(
        objects=result.canonical_ceilings,
        quantities=result.quantities,
        registry_run_scope="cross-view-ceiling-firm",
    )
    assert gaps == {}
    report = build_runtime_coverage_publication(
        summaries,
        family_gaps=gaps,
    )
    ceiling = report["family_reports"]["ceiling"]
    assert ceiling["classification"] == "PARTIAL"
    assert ceiling["stage_counts"] == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 1,
        "PUBLISHED": 0,
    }


def test_source_room_face_mismatch_remains_unresolved() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(_bridge(face_id="face-other"),),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_multiple_firm_room_area_claims_for_same_physical_room_conflict() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(
            _bridge(quantity_id="room-area-qty-1"),
            _bridge(quantity_id="room-area-qty-2"),
        ),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_ceiling_identity_and_quantity_id_are_deterministic() -> None:
    kwargs = {
        "rooms": _rooms(),
        "room_area_bridges": (_bridge(),),
        "finishes": _finish(),
    }
    first = ceiling_quantity.publish_cross_view_ceiling_quantities(**kwargs)
    second = ceiling_quantity.publish_cross_view_ceiling_quantities(**kwargs)

    assert len(first.records) == 1
    assert len(second.records) == 1
    assert (
        first.records[0].canonical_ceiling_id
        == second.records[0].canonical_ceiling_id
    )
    assert (
        first.records[0].quantity.quantity_id
        == second.records[0].quantity.quantity_id
    )


def test_identical_room_area_quantity_id_replay_is_idempotent() -> None:
    bridge = _bridge()
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(bridge, bridge),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.unresolved_physical_room_ids == ()
    assert len(result.quantities) == 1
    assert result.quantities[0].value == 9.05352


def test_conflicting_room_area_quantity_id_replay_does_not_publish_ceiling() -> None:
    bridge = _bridge()
    original_quantity = bridge.quantities[0]
    mismatched_claims = (
        replace(original_quantity, value=10.0),
        replace(
            original_quantity,
            metadata={
                **original_quantity.metadata,
                "figured_dimension_ids": ["different-h", "different-v"],
            },
        ),
        replace(original_quantity, evidence_ids=("face-1", "different-source-evidence")),
    )
    for mismatched in mismatched_claims:
        contradictory_bridge = replace(bridge, quantities=(mismatched,))
        result = ceiling_quantity.publish_cross_view_ceiling_quantities(
            rooms=_rooms(),
            room_area_bridges=(bridge, contradictory_bridge),
            finishes=_finish(),
        )

        assert result.status is EvidenceResolutionStatus.CONFLICT
        assert result.reason_codes == (
            ceiling_quantity.CROSS_VIEW_CEILING_QUANTITY_CONFLICT,
        )
        assert result.unresolved_physical_room_ids == ("physical-room-1",)
        assert result.records == ()
        assert result.quantities == ()
        assert result.canonical_ceilings == ()


def test_conflicting_room_area_quantity_id_order_cannot_select_winner() -> None:
    bridge = _bridge()
    changed = replace(
        bridge,
        quantities=(replace(bridge.quantities[0], value=10.0),),
    )
    for bridges in ((bridge, changed), (changed, bridge)):
        result = ceiling_quantity.publish_cross_view_ceiling_quantities(
            rooms=_rooms(),
            room_area_bridges=bridges,
            finishes=_finish(),
        )
        assert result.status is EvidenceResolutionStatus.CONFLICT
        assert not result.quantities


def test_non_metric_documented_room_area_cannot_promote_firm_rcp_ceiling_m2() -> None:
    bridge = _bridge()
    invalid = replace(
        bridge,
        quantities=(replace(bridge.quantities[0], unit="ft2"),),
    )
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(invalid,),
        finishes=_finish(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.unresolved_physical_room_ids == ("physical-room-1",)
    assert result.records == ()
    assert result.quantities == ()
    assert result.canonical_ceilings == ()


def test_blocked_firm_room_area_does_not_publish_rcp_ceiling_m2() -> None:
    bridge = _bridge()
    blocked = replace(
        bridge,
        quantities=(
            replace(
                bridge.quantities[0],
                blocking_reasons=("measurement_authority_unresolved",),
            ),
        ),
    )
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(blocked,),
        finishes=_finish(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.unresolved_physical_room_ids == ("physical-room-1",)
    assert result.records == ()
    assert result.quantities == ()
    assert result.canonical_ceilings == ()
