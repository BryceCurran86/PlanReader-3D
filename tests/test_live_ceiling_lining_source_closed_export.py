"""Tests for cross-view ceiling source-closed export."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
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
        formula="authenticated_cross_view_room_area_with_source_ceiling_finish",
        formula_version="1.0.0",
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
        reason_codes=("authenticated_cross_view_ceiling_lining_area",),
        metadata={
            "source_sha256": SOURCE_SHA,
            "revision_id": "rev-1",
            "page_no": "7",
            "viewport_id": "floor-vp",
            "source_dimension_page_id": "11",
            "support_page_id": "9",
            "support_viewport_id": "rcp-vp",
            "canonical_ceiling_id": "ceiling-1",
            "physical_ceiling_surface_id": "ceiling-1",
            "canonical_room_id": "canonical-room-1",
            "physical_room_id": "physical-room-1",
            "source_room_face_record_id": face_id,
            "figured_dimension_ids": ["dim-h", "dim-v"],
            "finish_code": "GRID",
            "semantic_finish": "ceiling_grid",
            "finish_definition_record_id": "def-grid",
            "finish_occurrence_record_id": "occ-grid",
            "finish_occurrence_evidence_id": "occ-evidence",
            "row_role": "ceiling_area",
        },
    )


def _claim(quantity: QuantityEvidence) -> LivePhysicalNetWallClaim:
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
        ceiling_lining_quantity_evidence=(quantity,),
    )


def test_ceiling_quantity_builds_complete_source_trace_and_seals() -> None:
    claim = _claim(_quantity())

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
    assert "ceiling-1" in trace.canonical_entity_ids
    assert "canonical-room-1" in trace.canonical_entity_ids
    assert set(_quantity().evidence_ids).issubset(set(trace.evidence_ids))

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


def test_tampered_source_room_face_identity_cannot_seal() -> None:
    claim = _claim(_quantity(face_id="face-other"))

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
    claim = _claim(tampered)

    with pytest.raises(SourceClosedRunConflictError):
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id="project-1",
        )
