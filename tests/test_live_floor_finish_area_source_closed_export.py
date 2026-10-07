from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_floor_finish_area_source_closed_export import (
    seal_live_floor_finish_area_run,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError


def _floor() -> LiveCanonicalFloorSurfaceObject:
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id="floor-1",
        physical_floor_surface_id="floor-1",
        room_entity_id="room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="1",
        viewport_id="vp-1",
        polygon_pdf_pts=((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)),
        area_page_pts2=100.0,
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=(),
        source_room_face_record_id="face-1",
        evidence_ids=("ev-room", "ev-area", "ev-occ", "ev-def"),
        geometry_complete=True,
        metric_geometry_complete=False,
        metric_area_m2=8.64,
        metric_area_quantity_id="room-area-1",
        metric_area_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        finish_descriptor="tile",
        structural_slab_id=None,
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=False,
    )


def _quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="floor-finish-q1",
        family="floor_finish_area",
        semantic_key="floor_finish_area:floor-1:FT1:tile",
        value=8.64,
        unit="m2",
        input_entity_ids=("floor-1",),
        formula="authenticated_documented_floor_finish",
        formula_version="1",
        evidence_ids=("ev-area", "ev-occ", "ev-def"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=("authenticated_cross_view_floor_finish_area",),
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "rev-1",
            "page_no": "1",
            "viewport_id": "vp-1",
            "canonical_floor_id": "floor-1",
            "physical_floor_surface_id": "floor-1",
            "source_room_face_record_id": "face-1",
            "finish_code": "FT1",
            "semantic_finish": "tile",
            "support_snapshot_id": "semantic-snap-1",
            "finish_definition_record_id": "def-1",
            "finish_occurrence_record_id": "occ-1",
            "source_dimension_page_id": "2",
        },
    )


def _publication() -> LiveExternalPhysicalNetWallPublication:
    return LiveExternalPhysicalNetWallPublication(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_evidence=None,
        canonical_walls=(),
        external_wall_ids=(),
        gross_geometry_record_ids=(),
        whole_wall_role_record_ids=(),
        physical_void_record_ids=(),
        opening_universe_record_ids=(),
    )


def _claim(floor: LiveCanonicalFloorSurfaceObject | None = None) -> LivePhysicalNetWallClaim:
    floor = floor or _floor()
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(floor,),
        canonical_floor_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(1,),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=_publication(),
        floor_finish_quantity_evidence=(_quantity(),),
    )


def test_floor_finish_quantity_seals_on_exact_canonical_floor_lineage() -> None:
    run = seal_live_floor_finish_area_run(
        _claim(),
        workspace_id=1,
        project_id="project-1",
    )

    assert len(run.quantities) == 1
    row = run.quantities[0]
    assert row.family == "floor_finish_area"
    assert row.value == 8.64
    assert row.object_identity_refs == ("floor-1",)
    assert row.lineage_ok is True
    assert set(row.trace_canonical_entity_ids) >= {"floor-1", "room-1"}


def test_floor_finish_export_rejects_missing_semantic_snapshot() -> None:
    claim = _claim()
    quantity = claim.floor_finish_quantity_evidence[0]
    tampered = replace(
        quantity,
        metadata={
            **dict(quantity.metadata),
            "support_snapshot_id": "",
        },
    )
    claim = replace(claim, floor_finish_quantity_evidence=(tampered,))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="semantic mismatch",
    ):
        seal_live_floor_finish_area_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )


def test_floor_finish_export_rejects_semantic_drift_from_canonical_floor() -> None:
    bad_floor = replace(_floor(), finish_descriptor="vinyl")
    with pytest.raises(
        SourceClosedRunConflictError,
        match="semantic mismatch",
    ):
        seal_live_floor_finish_area_run(
            _claim(bad_floor),
            workspace_id=1,
            project_id="project-1",
        )
