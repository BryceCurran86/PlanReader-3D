"""Tests for cross-view canonical ceiling source-closed export."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_ceiling_lining_integration import LiveCanonicalCeilingSurfaceObject
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_customer_output_verification import verify_sealed_customer_output
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import SourceClosedRunConflictError


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
            (10.0, 20.0),
            (110.0, 20.0),
            (110.0, 100.0),
            (10.0, 100.0),
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


def _quantity(*, face_id: str = "face-1") -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-ceiling-1",
        family="ceiling_lining",
        semantic_key="ceiling_lining:ceiling-1:GRID:ceiling_grid",
        value=9.05352,
        unit="m2",
        input_entity_ids=("ceiling-1",),
        formula="reuse_firm_documented_room_area_with_authenticated_rcp_finish",
        formula_version="1.2.0",
        evidence_ids=(
            "room-evidence",
            "room-label-evidence",
            "area-evidence",
            "occ-evidence",
            "def-evidence",
        ),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        reason_codes=("authenticated_room_area_with_rcp_ceiling_finish",),
        metadata={
            "document_id": "doc-1",
            "snapshot_id": "snap-1",
            "source_sha256": SOURCE_SHA,
            "revision_id": "rev-1",
            "page_no": 7,
            "viewport_id": "floor-vp",
            "support_page_id": "9",
            "support_viewport_id": "rcp-vp",
            "support_snapshot_id": "semantic-snap-1",
            "canonical_ceiling_id": "ceiling-1",
            "physical_ceiling_surface_id": "ceiling-1",
            "canonical_room_id": "canonical-room-1",
            "physical_room_id": "physical-room-1",
            "source_room_face_record_id": face_id,
            "source_room_index_id": "room-index-1",
            "upstream_room_area_quantity_id": "room-area-qty-1",
            "room_area_quantity_id": "room-area-qty-1",
            "measurement_authority": "documented_dimension",
            "figured_dimension_ids": ["dim-h", "dim-v"],
            "finish_code": "GRID",
            "semantic_finish": "ceiling_grid",
            "finish_definition_record_id": "def-grid",
            "finish_occurrence_record_id": "occ-grid",
            "finish_occurrence_evidence_id": "occ-evidence",
            "row_role": "ceiling_area",
        },
    )


def _canonical_ceiling(
    quantity: QuantityEvidence,
    *,
    area: float = 9.05352,
) -> LiveCanonicalCeilingSurfaceObject:
    return LiveCanonicalCeilingSurfaceObject(
        canonical_ceiling_id="ceiling-1",
        document_id="doc-1",
        snapshot_id="snap-1",
        room_entity_id="canonical-room-1",
        source_page=7,
        viewport_id="floor-vp",
        source_sha256=SOURCE_SHA,
        revision_id="rev-1",
        polygon_pdf_pts=(
            (10.0, 20.0),
            (110.0, 20.0),
            (110.0, 100.0),
            (10.0, 100.0),
        ),
        area_m2=area,
        finish_descriptor="ceiling_grid",
        room_area_quantity_id="room-area-qty-1",
        ceiling_quantity_id=quantity.quantity_id,
        source_room_index_id="room-index-1",
        evidence_ids=tuple(quantity.evidence_ids),
        physical_scale_record_id="",
        measurement_authority="documented_dimension",
        figured_dimension_ids=("dim-h", "dim-v"),
        geometry_complete=True,
        metric_area_complete=True,
        metric_geometry_complete=False,
    )


def _claim(
    quantity: QuantityEvidence,
    *,
    canonical_ceiling: LiveCanonicalCeilingSurfaceObject | None = None,
) -> LivePhysicalNetWallClaim:
    publication = LiveExternalPhysicalNetWallPublication(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("not-relevant",),
        quantity_evidence=None,
        canonical_walls=(),
        external_wall_ids=(),
        gross_geometry_record_ids=(),
        whole_wall_role_record_ids=(),
        physical_void_record_ids=(),
        opening_universe_record_ids=(),
    )
    if canonical_ceiling is None:
        canonical_ceiling = _canonical_ceiling(quantity)
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("not-relevant",),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(_room(),),
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_room_reason_codes=("resolved",),
        canonical_room_source_pages=(7,),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=publication,
        canonical_ceilings=(canonical_ceiling,),
        ceiling_lining_quantity_evidence=(quantity,),
    )


def test_canonical_ceiling_quantity_builds_complete_source_trace_and_seals() -> None:
    quantity = _quantity()
    claim = _claim(quantity)

    traces = build_live_ceiling_lining_source_traces(
        claim,
        workspace_id=1,
        project_id="project-1",
    )
    assert tuple(traces) == ("qty-ceiling-1",)
    trace = traces["qty-ceiling-1"]
    assert trace.document_id == "doc-1"
    assert trace.source_sha256 == SOURCE_SHA
    assert trace.source_page == "7"
    assert trace.viewport_id == "floor-vp"
    assert trace.metadata["support_snapshot_id"] == "semantic-snap-1"
    assert "ceiling-1" in trace.canonical_entity_ids
    assert "canonical-room-1" in trace.canonical_entity_ids
    assert set(quantity.evidence_ids).issubset(set(trace.evidence_ids))

    run = seal_live_ceiling_lining_run(
        claim,
        workspace_id=1,
        project_id="project-1",
    )
    assert len(run.quantities) == 1
    sealed = run.quantities[0]
    assert sealed.quantity_id == "qty-ceiling-1"
    assert sealed.family == "ceiling_lining"
    assert sealed.value == 9.05352
    assert sealed.lineage_ok is True
    assert sealed.lineage_reason_codes == ()


def test_firm_ceiling_seals_and_projects_to_exactly_one_customer_row() -> None:
    base = _quantity()
    quantity = replace(
        base,
        metadata={
            **dict(base.metadata),
            "commercial_projection_allowed": True,
            "section": "Internal",
            "element": "Ceiling lining area",
            "location": "OFFICE",
            "substrate": "Other",
            "finish_system": "ceiling_grid",
            "inclusion_status": "INCLUSION",
        },
    )
    claim = _claim(
        quantity,
        canonical_ceiling=replace(
            _canonical_ceiling(base),
            ceiling_quantity_id=quantity.quantity_id,
        ),
    )
    traces = build_live_ceiling_lining_source_traces(
        claim,
        workspace_id=1,
        project_id="project-1",
    )
    trace = traces[quantity.quantity_id]
    authority = CommercialMeasurementAuthority(
        method="figured_dimension",
        figured_dimension_ids=("dim-h", "dim-v"),
    )
    row = quantity_evidence_to_takeoff_output_row(
        quantity,
        trace=trace,
        authority=authority,
    )
    assert row is not None
    assert row["quantity_id"] == quantity.quantity_id
    assert row["quantity"] == 9.05352
    assert row["source_sha256"] == SOURCE_SHA
    assert row["revision_id"] == "rev-1"
    assert row["canonical_entity_ids"] == list(trace.canonical_entity_ids)
    assert row["evidence_ids"] == list(trace.evidence_ids)

    run = seal_live_ceiling_lining_run(
        claim,
        workspace_id=1,
        project_id="project-1",
    )
    report = verify_sealed_customer_output(run, [row])
    assert report.valid_quantity_count == 1
    assert report.customer_row_count == 1
    assert report.verified_quantity_ids == (quantity.quantity_id,)


def test_missing_semantic_snapshot_cannot_seal() -> None:
    quantity = _quantity()
    tampered = replace(
        quantity,
        metadata={
            **dict(quantity.metadata),
            "support_snapshot_id": "",
        },
    )
    claim = _claim(
        tampered,
        canonical_ceiling=replace(
            _canonical_ceiling(quantity),
            ceiling_quantity_id=tampered.quantity_id,
        ),
    )

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_missing_canonical_ceiling_cannot_seal() -> None:
    quantity = _quantity()
    claim = replace(_claim(quantity), canonical_ceilings=())

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_canonical_area_mismatch_cannot_seal() -> None:
    quantity = _quantity()
    claim = _claim(
        quantity,
        canonical_ceiling=_canonical_ceiling(quantity, area=9.5),
    )

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_tampered_source_room_face_identity_cannot_seal() -> None:
    quantity = _quantity(face_id="face-other")
    claim = _claim(quantity)

    with pytest.raises(SourceClosedRunConflictError):
        build_live_ceiling_lining_source_traces(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_tampered_ceiling_identity_metadata_cannot_seal() -> None:
    quantity = _quantity()
    tampered = replace(
        quantity,
        metadata={
            **dict(quantity.metadata),
            "canonical_ceiling_id": "ceiling-other",
        },
    )
    claim = _claim(
        tampered,
        canonical_ceiling=replace(
            _canonical_ceiling(quantity),
            ceiling_quantity_id=tampered.quantity_id,
        ),
    )

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_scaled_quantity_is_not_admitted_to_documented_rcp_export() -> None:
    quantity = replace(
        _quantity(),
        authority="pdf_scaled",
        metadata={
            **dict(_quantity().metadata),
            "measurement_authority": "pdf_scaled",
            "figured_dimension_ids": [],
            "scale_fingerprint": "scale-1",
        },
    )
    claim = _claim(
        quantity,
        canonical_ceiling=replace(
            _canonical_ceiling(quantity),
            ceiling_quantity_id=quantity.quantity_id,
            measurement_authority="pdf_scaled",
            figured_dimension_ids=(),
            physical_scale_record_id="scale-1",
        ),
    )

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )
