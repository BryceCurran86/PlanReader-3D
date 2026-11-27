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


# ---------------------------------------------------------------------------
# MAX #7220049429: Independent floor_area family-only retention & bijection
# ---------------------------------------------------------------------------


def _fake_floor_family_run(sha: str, qids: tuple[str, ...] = ("floor-q1", "floor-q2", "floor-q3"), family: str = "floor_area"):
    published = tuple(
        QuantityEvidence(
            quantity_id=qid,
            family=family,
            semantic_key=f"{family}:{qid}",
            value=12.5,
            unit="m2",
            status="firm",
            abstained=False,
            authority="live_floor_area_quantity_publication",
            input_entity_ids=(f"ent-{qid}",),
            metadata={
                "source_sha256": sha,
                "commercial_projection_allowed": True,
            },
        )
        for qid in qids
    )
    sealed_rows = tuple(
        SimpleNamespace(
            quantity_id=q.quantity_id,
            family=q.family,
            semantic_key=q.semantic_key,
            value=q.value,
            unit=q.unit,
            status=q.status,
            authority=q.authority,
            confidence=q.confidence,
            abstained=q.abstained,
            object_identity_refs=tuple(sorted(q.input_entity_ids)),
            evidence_ids=tuple(sorted(q.evidence_ids)),
            blocking_reasons=tuple(sorted(q.blocking_reasons)),
            reason_codes=tuple(sorted(q.reason_codes)),
            lineage_ok=True,
        )
        for q in published
    )
    return SimpleNamespace(
        run_id="run_floor_family_01",
        source_sha256s=(sha,),
        quantities=sealed_rows,
        published_quantities=published,
        to_json=lambda: '{"run_id":"run_floor_family_01"}\n',
    )


def test_handoff_publishes_family_only_floor_area_when_floor_finish_abstains(
    tmp_path: Path, monkeypatch
) -> None:
    """Valid floor_area + abstained floor_finish writes ONLY family-only artifact & manifest, never whole-project verified_customer_rows.json."""
    pdf_path = _make_minimal_pdf(tmp_path)
    out_dir = tmp_path / "out_family_only"
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
        unresolved_walls=("wall_missing_1",),
    )
    floor_run = _fake_floor_family_run(sha)
    floor_rows = tuple(
        {"quantity_id": q.quantity_id, "quantity_family": "floor_area", "unit": "m2", "value": 12.5}
        for q in floor_run.quantities
    )

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *a, **kw: claim)
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda _c: floor_run.published_quantities)
    monkeypatch.setattr(handoff, "seal_live_floor_area_run", lambda *a, **kw: floor_run)
    monkeypatch.setattr(handoff, "project_live_floor_area_customer_rows", lambda *a, **kw: floor_rows)
    monkeypatch.setattr(
        handoff,
        "verify_sealed_customer_output",
        lambda run, rows: SimpleNamespace(
            customer_row_count=len(rows),
            verified_quantity_ids=tuple(r["quantity_id"] for r in rows),
        ),
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *a, **kw: SimpleNamespace(canonical_ceilings=(), quantities=()),
    )
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda r: ())

    summary = handoff.generate_project_handoff(
        pdf_path=pdf_path,
        workspace_id=1,
        project_id="proj_synth",
        family_group="all",
        output_dir=out_dir,
    )
    # Whole-project invariants remain strictly unsealed / unverified / no score
    assert summary["status"] == "source_attempt_recorded_unsealed"
    assert summary["combined_run_file"] is None
    assert summary["customer_rows_verified"] is False
    assert summary["customer_rows_file"] is None
    assert summary["verified_customer_row_count"] == 0
    assert summary["benchmark_score_granted"] is False
    assert not (out_dir / "verified_customer_rows.json").exists()
    assert not (out_dir / "proj_synth.json").exists()

    # Family-only floor_area artifact & manifest are explicitly verified & labelled incomplete-project
    fam_manifest = summary["family_only_verified_outputs"]["floor_area"]
    assert fam_manifest["verified"] is True
    assert fam_manifest["scope"] == "family_only_incomplete_project"
    assert fam_manifest["whole_project_verified"] is False
    assert fam_manifest["benchmark_score_granted"] is False
    assert fam_manifest["source_sha256"] == sha
    assert fam_manifest["customer_row_count"] == 3
    assert fam_manifest["verified_quantity_ids"] == ["floor-q1", "floor-q2", "floor-q3"]
    fam_file = out_dir / "verified_floor_area_family_customer_rows.json"
    assert fam_file.is_file()
    assert fam_manifest["customer_rows_file"] == str(fam_file)


def test_family_only_floor_area_rejects_wrong_source_wrong_family_and_bad_bijection(monkeypatch) -> None:
    sha = "a" * 64
    other_sha = "b" * 64
    run_wrong_sha = _fake_floor_family_run(other_sha)
    with pytest.raises(RuntimeError, match="source SHA envelope mismatch"):
        handoff._verify_independent_floor_area_family_customer_projection(
            claim=SimpleNamespace(),
            family_runs=[("floor_area", run_wrong_sha)],
            workspace_id=1,
            project_id="proj_synth",
            source_sha256=sha,
        )

    run_wrong_family = _fake_floor_family_run(sha, family="ceiling_area")
    with pytest.raises(RuntimeError, match="non-floor_area quantity"):
        handoff._verify_independent_floor_area_family_customer_projection(
            claim=SimpleNamespace(),
            family_runs=[("floor_area", run_wrong_family)],
            workspace_id=1,
            project_id="proj_synth",
            source_sha256=sha,
        )

    run_ok = _fake_floor_family_run(sha, qids=("floor-q1", "floor-q2"))
    # Wrong family in projected rows -> reject
    monkeypatch.setattr(
        handoff,
        "project_live_floor_area_customer_rows",
        lambda *a, **kw: (
            {"quantity_id": "floor-q1", "quantity_family": "wall_net_area"},
            {"quantity_id": "floor-q2", "quantity_family": "floor_area"},
        ),
    )
    with pytest.raises(RuntimeError, match="wrong family row"):
        handoff._verify_independent_floor_area_family_customer_projection(
            claim=SimpleNamespace(),
            family_runs=[("floor_area", run_ok)],
            workspace_id=1,
            project_id="proj_synth",
            source_sha256=sha,
        )

    # Duplicate/mismatched bijection (only 1 of 2 IDs verified) -> reject
    monkeypatch.setattr(
        handoff,
        "project_live_floor_area_customer_rows",
        lambda *a, **kw: (
            {"quantity_id": "floor-q1", "quantity_family": "floor_area"},
            {"quantity_id": "floor-q1", "quantity_family": "floor_area"},
        ),
    )
    monkeypatch.setattr(
        handoff,
        "verify_sealed_customer_output",
        lambda run, rows: SimpleNamespace(
            customer_row_count=2,
            verified_quantity_ids=("floor-q1",),
        ),
    )
    with pytest.raises(RuntimeError, match="bijection failed"):
        handoff._verify_independent_floor_area_family_customer_projection(
            claim=SimpleNamespace(),
            family_runs=[("floor_area", run_ok)],
            workspace_id=1,
            project_id="proj_synth",
            source_sha256=sha,
        )


def test_family_only_floor_area_projection_error_writes_no_family_file(
    tmp_path: Path, monkeypatch
) -> None:
    """If independent floor_area projection fails, no family customer file is written and manifest records verified=False."""
    pdf_path = _make_minimal_pdf(tmp_path)
    out_dir = tmp_path / "out_family_fail"
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
        unresolved_walls=("wall_missing_1",),
    )
    floor_run = _fake_floor_family_run(sha)
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *a, **kw: claim)
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda _c: floor_run.published_quantities)
    monkeypatch.setattr(handoff, "seal_live_floor_area_run", lambda *a, **kw: floor_run)
    monkeypatch.setattr(
        handoff,
        "project_live_floor_area_customer_rows",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("bijection mismatch")),
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *a, **kw: SimpleNamespace(canonical_ceilings=(), quantities=()),
    )
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda r: ())

    summary = handoff.generate_project_handoff(
        pdf_path=pdf_path,
        workspace_id=1,
        project_id="proj_synth",
        family_group="all",
        output_dir=out_dir,
    )
    assert summary["status"] == "source_attempt_recorded_unsealed"
    assert summary["customer_rows_verified"] is False
    assert not (out_dir / "verified_customer_rows.json").exists()
    assert not (out_dir / "verified_floor_area_family_customer_rows.json").exists()
    fam_manifest = summary["family_only_verified_outputs"]["floor_area"]
    assert fam_manifest["verified"] is False
    assert "bijection mismatch" in fam_manifest["error"]
