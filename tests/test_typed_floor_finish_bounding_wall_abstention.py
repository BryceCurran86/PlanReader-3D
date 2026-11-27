"""Synthetic tests for typed FloorFinishBoundingWallAuthorityIncompleteError and handoff abstention."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_floor_finish_area_source_closed_export import (
    FLOOR_FINISH_BOUNDING_WALL_AUTHORITY_INCOMPLETE,
    FloorFinishBoundingWallAuthorityIncompleteError,
    build_live_floor_finish_area_source_traces,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError
import tools.run_source_closed_project_handoff as handoff


def _make_minimal_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "synthetic_plan.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 50), "FLOOR PLAN")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _make_claim(
    *,
    sha: str,
    walls: tuple,
    room_bounding_ids: tuple[str, ...],
    canonical_bounding_ids: tuple[str, ...] = (),
    claim_status=EvidenceResolutionStatus.CANDIDATE,
    wall_status=EvidenceResolutionStatus.CANDIDATE,
    room_status=EvidenceResolutionStatus.CANDIDATE,
    floor_status=EvidenceResolutionStatus.CORROBORATED,
    unresolved_walls: tuple[str, ...] = ("wall_missing_1",),
) -> LivePhysicalNetWallClaim:
    ring = ((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0))
    room = SimpleNamespace(
        canonical_room_id="room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=sha,
        snapshot_id="snap-1",
        page_id="1",
        source_room_face_record_id="face-1",
        viewport_id="vp-1",
        polygon_pdf_pts=ring,
        canonical_bounding_wall_ids=canonical_bounding_ids,
        bounding_wall_ids=room_bounding_ids,
    )
    floor = LiveCanonicalFloorSurfaceObject(
        canonical_floor_id="floor-1",
        physical_floor_surface_id="floor-1",
        room_entity_id="room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=sha,
        snapshot_id="snap-1",
        page_id="1",
        viewport_id="vp-1",
        polygon_pdf_pts=ring,
        area_page_pts2=100.0,
        bounding_wall_ids=room_bounding_ids,
        canonical_bounding_wall_ids=canonical_bounding_ids,
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
    qty = QuantityEvidence(
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
            "source_sha256": sha,
            "revision_id": "rev-1",
            "page_no": "1",
            "viewport_id": "vp-1",
            "canonical_floor_id": "floor-1",
            "physical_floor_surface_id": "floor-1",
            "source_room_face_record_id": "face-1",
            "finish_code": "FT1",
            "semantic_finish": "tile",
            "support_snapshot_id": "semantic-snap-1",
            "support_page_id": "1",
            "support_viewport_id": "finish-vp",
            "finish_definition_record_id": "def-1",
            "finish_occurrence_record_id": "occ-1",
            "finish_occurrence_evidence_id": "ev-occ",
            "source_dimension_page_id": "1",
            "figured_dimension_ids": ("dim-h-source", "dim-v-source"),
        },
    )
    pub = LiveExternalPhysicalNetWallPublication(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test_abstained",),
        quantity_evidence=None,
        canonical_walls=(),
        external_wall_ids=(),
        gross_geometry_record_ids=(),
        whole_wall_role_record_ids=(),
        physical_void_record_ids=(),
        opening_universe_record_ids=(),
    )
    return LivePhysicalNetWallClaim(
        status=claim_status,
        reason_codes=("test_claim",),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=walls,
        canonical_wall_status=wall_status,
        canonical_wall_reason_codes=("wall_candidate",),
        canonical_wall_source_pages=(1,),
        unresolved_wall_candidate_ids=unresolved_walls,
        canonical_openings=(),
        canonical_rooms=(room,),
        canonical_floors=(floor,),
        canonical_floor_status=floor_status,
        canonical_floor_reason_codes=("floor_ok",),
        canonical_floor_source_pages=(1,),
        canonical_room_status=room_status,
        canonical_room_reason_codes=("room_candidate",),
        canonical_room_source_pages=(1,),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=pub,
        floor_finish_quantity_evidence=(qty,),
    )


def test_incomplete_bounding_walls_raises_typed_subclass() -> None:
    """Missing bounding wall ID raises FloorFinishBoundingWallAuthorityIncompleteError (subclass of SourceClosedRunConflictError)."""
    sha = "a" * 64
    unrelated_wall = SimpleNamespace(
        canonical_wall_id="wall_other",
        role="internal_finished_wall_face",
        physical_identity_resolved=True,
    )
    claim = _make_claim(
        sha=sha,
        walls=(unrelated_wall,),
        room_bounding_ids=("wall_missing_1", "wall_missing_2"),
    )
    with pytest.raises(FloorFinishBoundingWallAuthorityIncompleteError) as exc_info:
        build_live_floor_finish_area_source_traces(claim, workspace_id=1, project_id="proj_synth")
    err = exc_info.value
    assert isinstance(err, SourceClosedRunConflictError)
    assert err.quantity_id == "floor-finish-q1"
    assert err.room_entity_id == "room-1"
    assert err.missing_bounding_wall_ids == ("wall_missing_1", "wall_missing_2")
    assert err.reason_code == FLOOR_FINISH_BOUNDING_WALL_AUTHORITY_INCOMPLETE


def test_non_internal_wall_role_and_unresolved_identity_raise_generic_conflict_only() -> None:
    """Other bounding-wall conflicts MUST NOT be classified as FloorFinishBoundingWallAuthorityIncompleteError."""
    sha = "b" * 64
    ext_wall = SimpleNamespace(
        canonical_wall_id="wall-1",
        role="external_wall",
        physical_identity_resolved=True,
    )
    claim = _make_claim(
        sha=sha,
        walls=(ext_wall,),
        room_bounding_ids=("wall-1",),
        canonical_bounding_ids=("wall-1",),
        unresolved_walls=(),
    )
    with pytest.raises(SourceClosedRunConflictError) as exc_info:
        build_live_floor_finish_area_source_traces(claim, workspace_id=1, project_id="proj_synth")
    assert type(exc_info.value) is SourceClosedRunConflictError
    assert not isinstance(exc_info.value, FloorFinishBoundingWallAuthorityIncompleteError)

    unresolved_id_wall = SimpleNamespace(
        canonical_wall_id="wall-1",
        role="internal_finished_wall_face",
        physical_identity_resolved=False,
    )
    claim2 = _make_claim(
        sha=sha,
        walls=(unresolved_id_wall,),
        room_bounding_ids=("wall-1",),
        canonical_bounding_ids=("wall-1",),
        unresolved_walls=(),
    )
    with pytest.raises(SourceClosedRunConflictError) as exc_info2:
        build_live_floor_finish_area_source_traces(claim2, workspace_id=1, project_id="proj_synth")
    assert type(exc_info2.value) is SourceClosedRunConflictError
    assert not isinstance(exc_info2.value, FloorFinishBoundingWallAuthorityIncompleteError)


def test_complete_bounding_walls_succeed_trace_export() -> None:
    """Complete authenticated bounding walls pass the wall-authority gate and produce traces."""
    sha = "c" * 64
    ok_wall = SimpleNamespace(
        canonical_wall_id="wall-1",
        role="internal_finished_wall_face",
        physical_identity_resolved=True,
    )
    claim = _make_claim(
        sha=sha,
        walls=(ok_wall,),
        room_bounding_ids=("wall-1",),
        canonical_bounding_ids=("wall-1",),
        claim_status=EvidenceResolutionStatus.CORROBORATED,
        wall_status=EvidenceResolutionStatus.CORROBORATED,
        room_status=EvidenceResolutionStatus.CORROBORATED,
        floor_status=EvidenceResolutionStatus.CORROBORATED,
        unresolved_walls=(),
    )
    traces = build_live_floor_finish_area_source_traces(claim, workspace_id=1, project_id="proj_synth")
    assert "floor-finish-q1" in traces


def test_handoff_catches_only_typed_abstention_continues_diagnostics_and_stays_unsealed(
    tmp_path: Path, monkeypatch
) -> None:
    """Live handoff catches FloorFinishBoundingWallAuthorityIncompleteError, runs unrelated families, and retains unsealed/no-score semantics."""
    pdf_path = _make_minimal_pdf(tmp_path)
    out_dir = tmp_path / "out"
    sha = handoff._sha256(pdf_path)

    unrelated_wall = SimpleNamespace(
        canonical_wall_id="wall_other",
        role="internal_finished_wall_face",
        physical_identity_resolved=True,
    )
    claim = _make_claim(
        sha=sha,
        walls=(unrelated_wall,),
        room_bounding_ids=("wall_missing_1",),
        unresolved_walls=("wall_missing_1", "wall_missing_2"),
    )
    ceiling_called = {"count": 0}

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *a, **kw: claim)

    def fake_ceilings(*a, **kw):
        ceiling_called["count"] += 1
        return SimpleNamespace(canonical_ceilings=(), quantities=())

    monkeypatch.setattr(handoff, "collect_live_ceiling_lining_claims", fake_ceilings)
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda r: ())

    summary = handoff.generate_project_handoff(
        pdf_path=pdf_path,
        workspace_id=1,
        project_id="proj_synth",
        family_group="all",
        output_dir=out_dir,
    )
    assert ceiling_called["count"] == 1  # unrelated family diagnostics still ran
    assert summary["status"] == "source_attempt_recorded_unsealed"
    assert summary["combined_run_file"] is None
    assert summary["combined_run_id"] is None
    assert summary["customer_rows_verified"] is False
    assert summary["customer_rows_file"] is None
    assert summary["verified_customer_row_count"] == 0
    assert summary["benchmark_score_granted"] is False
    assert summary["floor_finish_customer_first_gate"] == "FLOOR_FINISH_BOUNDING_WALL_AUTHORITY_INCOMPLETE"
    abst = summary["family_abstentions"]["floor_finish_area"]
    assert abst["status"] == "abstained"
    assert abst["reason_code"] == FLOOR_FINISH_BOUNDING_WALL_AUTHORITY_INCOMPLETE
    assert abst["affected_quantity_ids"] == ["floor-finish-q1"]
    assert abst["room_entity_id"] == "room-1"
    assert abst["missing_bounding_wall_ids"] == ["wall_missing_1"]
    assert abst["unresolved_wall_candidate_count"] == 2
    assert not (out_dir / "proj_synth.json").exists()
    assert not (out_dir / "verified_customer_rows.json").exists()


def test_handoff_propagates_generic_floor_finish_conflict(tmp_path: Path, monkeypatch) -> None:
    """Generic SourceClosedRunConflictError from floor-finish sealer MUST NOT be swallowed."""
    pdf_path = _make_minimal_pdf(tmp_path)
    out_dir = tmp_path / "out_conflict"
    sha = handoff._sha256(pdf_path)

    ext_wall = SimpleNamespace(
        canonical_wall_id="wall-1",
        role="external_wall",
        physical_identity_resolved=True,
    )
    claim = _make_claim(
        sha=sha,
        walls=(ext_wall,),
        room_bounding_ids=("wall-1",),
        canonical_bounding_ids=("wall-1",),
        unresolved_walls=(),
    )
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *a, **kw: claim)

    with pytest.raises(SourceClosedRunConflictError) as exc_info:
        handoff.generate_project_handoff(
            pdf_path=pdf_path,
            workspace_id=1,
            project_id="proj_synth",
            family_group="all",
            output_dir=out_dir,
        )
    assert not isinstance(exc_info.value, FloorFinishBoundingWallAuthorityIncompleteError)
