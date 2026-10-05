"""Tests for authenticated internal-elevation finish semantic binding."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_internal_elevation_finish_binding_authority import (
    INTERNAL_ELEVATION_FINISH_CONFLICT,
    INTERNAL_ELEVATION_FINISH_DIRECT_ASSERTION_MISSING,
    INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH,
    INTERNAL_ELEVATION_FINISH_RESOLVED,
    INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_AMBIGUOUS,
    InternalElevationFinishBindingAuthority,
    InternalElevationFinishBindingProducer,
)
from pb_internal_elevation_wall_face_authority import (
    INTERNAL_ELEVATION_WALL_FACE_RESOLVED,
    InternalElevationWallFaceAuthority,
    InternalElevationWallFaceRecord,
    InternalElevationWallFaceResult,
    InternalElevationWallFaceSelector,
    _AUTHORITY_SEAL as WALL_FACE_AUTHORITY_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as PHYSICAL_WALL_AUTHORITY_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_material_semantic_authority import (
    SOURCE_MATERIAL_SCOPE_RESOLVED,
    SourceMaterialOccurrenceRecord,
    SourceMaterialOccurrenceScopeResult,
    SourceMaterialOccurrenceSelector,
    SourceMaterialSemanticAuthority,
    _AUTHORITY_SEAL as MATERIAL_AUTHORITY_SEAL,
)
from pb_wall_room_topology_contracts import MeasurementAuthorityType, WallCandidate

DOC = "doc-finish-binding"
REV = "revision-1"
SHA = "a" * 64
SNAP = "snapshot-1"
SRC_PAGE = "1"
TGT_PAGE = "2"
WALL = "wall-1"
TARGET_WALL = "target-wall-1"
VIEW = "elevation-vp"


def _selector() -> InternalElevationWallFaceSelector:
    return InternalElevationWallFaceSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_wall_id=WALL,
    )


def _mapping_record(**changes) -> InternalElevationWallFaceRecord:
    base = InternalElevationWallFaceRecord(
        record_id="mapping-record",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_wall_id=WALL,
        physical_face_id="physical-face-1",
        physical_wall_decision_scope_id="wall-source:page-1",
        source_room_face_id="room-face-1",
        source_room_face_record_id="room-record-1",
        target_physical_wall_id=TARGET_WALL,
        target_viewport_id=VIEW,
        target_view_type="elevation",
        cross_sheet_registration_record_id="cross-record-1",
        callout_mark="1",
        referenced_sheet_code="A20",
        callout_evidence_id="callout-evidence-1",
    )
    return replace(base, **changes)


def _wall_face_authority(record=None) -> InternalElevationWallFaceAuthority:
    selector = _selector()
    record = record or _mapping_record()
    return InternalElevationWallFaceAuthority(
        {
            selector.key: InternalElevationWallFaceResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(INTERNAL_ELEVATION_WALL_FACE_RESOLVED,),
                record=record,
            )
        },
        _seal=WALL_FACE_AUTHORITY_SEAL,
    )


def _candidate(candidate_id: str) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=VIEW,
        representation="double_line",
        centerline_pts=((20.0, 80.0), (180.0, 80.0)),
        face_a_segment_ids=(f"{candidate_id}-a",),
        face_b_segment_ids=(f"{candidate_id}-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.1,
        thickness_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION,
        length_m=1.0,
        end_node_ids=(f"{candidate_id}-n1", f"{candidate_id}-n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior="unresolved",
        level_id="L1",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _wall_record(candidate_id: str) -> PhysicalWallCandidateRecord:
    return PhysicalWallCandidateRecord(
        wall_candidate_id=candidate_id,
        wall_candidate=_candidate(candidate_id),
        physical_identity=PhysicalWallIdentity(
            wall_candidate_id=candidate_id,
            viewport_id=VIEW,
            candidate_identity_id=f"identity-{candidate_id}",
            path_fingerprint=f"path-{candidate_id}",
            source_primitive_ids=(f"primitive-{candidate_id}",),
            edge_ids=(f"edge-{candidate_id}",),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )


def _physical_wall_authority(*candidate_ids: str) -> PhysicalWallCandidateAuthority:
    decision_scope_id = f"wall-source:viewport:{TGT_PAGE}:{VIEW}:test"
    scope = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(_wall_record(candidate_id) for candidate_id in candidate_ids),
        source_observation_ids=(),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=TGT_PAGE,
        decision_scope_id=decision_scope_id,
        reason_codes=(),
        scope_kind="viewport",
        viewport_id=VIEW,
        viewport_bbox=(10.0, 10.0, 210.0, 130.0),
        viewport_view_type="elevation",
        viewport_status="resolved",
        viewport_boundary_source="vector_frame",
    )
    key = _ScopeKey(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=TGT_PAGE,
        decision_scope_id=decision_scope_id,
    )
    return PhysicalWallCandidateAuthority(
        {key: scope},
        _seal=PHYSICAL_WALL_AUTHORITY_SEAL,
    )


def _occurrence(
    *,
    record_id: str,
    code: str = "WT1",
    semantic_finish: str = "tile",
    raw_text: str = "WALL FINISH WT1",
    definition_record_id: str = "definition-wt1",
) -> SourceMaterialOccurrenceRecord:
    return SourceMaterialOccurrenceRecord(
        record_id=record_id,
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=TGT_PAGE,
        viewport_id=VIEW,
        code=code,
        semantic_finish=semantic_finish,
        definition_record_id=definition_record_id,
        bbox_pdf_pts=(20.0, 20.0, 100.0, 35.0),
        raw_text=raw_text,
        source_evidence_id=f"evidence-{record_id}",
    )


def _material_authority(*records) -> SourceMaterialSemanticAuthority:
    selector = SourceMaterialOccurrenceSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=TGT_PAGE,
        viewport_id=VIEW,
    )
    return SourceMaterialSemanticAuthority(
        {},
        {
            selector.key: SourceMaterialOccurrenceScopeResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(SOURCE_MATERIAL_SCOPE_RESOLVED,),
                scope_complete=True,
                records=tuple(records),
            )
        },
        _seal=MATERIAL_AUTHORITY_SEAL,
    )


def _producer(*records, wall_record=None, target_wall_ids=(TARGET_WALL,)):
    return InternalElevationFinishBindingProducer.from_authorities(
        wall_face_authority=_wall_face_authority(wall_record),
        material_authority=_material_authority(*records),
        physical_wall_authority=_physical_wall_authority(*target_wall_ids),
    )


def test_direct_wall_finish_semantic_binds_to_proven_physical_face() -> None:
    result = _producer(_occurrence(record_id="occ-1")).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.physical_wall_id == WALL
    assert result.record.physical_face_id == "physical-face-1"
    assert result.record.source_room_face_id == "room-face-1"
    assert result.record.material_code == "WT1"
    assert result.record.semantic_finish == "tile"
    assert result.record.trade_scope_id == "internal_tile"
    assert result.record.target_viewport_id == VIEW
    assert result.record.wall_face_mapping_record_id == "mapping-record"
    assert result.record.decision_scope_complete is False
    assert not hasattr(result.record, "quantity_m2")
    assert INTERNAL_ELEVATION_FINISH_RESOLVED in result.reason_codes


def test_code_occurrence_without_direct_wall_scope_does_not_bind() -> None:
    result = _producer(
        _occurrence(
            record_id="occ-1",
            raw_text="Refer WT1 for typical wet area finish",
        )
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert (
        INTERNAL_ELEVATION_FINISH_DIRECT_ASSERTION_MISSING
        in result.reason_codes
    )


def test_two_different_direct_wall_finishes_conflict_instead_of_ranking() -> None:
    result = _producer(
        _occurrence(record_id="occ-1"),
        _occurrence(
            record_id="occ-2",
            code="PT1",
            semantic_finish="paint",
            raw_text="WALL FINISH PT1",
            definition_record_id="definition-pt1",
        ),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert INTERNAL_ELEVATION_FINISH_CONFLICT in result.reason_codes


def test_repeated_same_direct_finish_deduplicates_semantic_identity() -> None:
    result = _producer(
        _occurrence(record_id="occ-1"),
        _occurrence(record_id="occ-2"),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.material_code == "WT1"
    assert result.record.semantic_finish == "tile"
    assert result.record.occurrence_record_ids == ("occ-1", "occ-2")
    assert result.record.source_evidence_ids == (
        "evidence-occ-1",
        "evidence-occ-2",
    )


def test_viewport_level_finish_does_not_choose_between_multiple_walls() -> None:
    result = _producer(
        _occurrence(record_id="occ-1"),
        target_wall_ids=(TARGET_WALL, "other-wall"),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert INTERNAL_ELEVATION_FINISH_TARGET_SCOPE_AMBIGUOUS in result.reason_codes


def test_unique_target_wall_must_be_the_cross_view_mapped_wall() -> None:
    result = _producer(
        _occurrence(record_id="occ-1"),
        target_wall_ids=("different-wall",),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH in result.reason_codes


def test_wall_mapping_lineage_mismatch_is_conflict() -> None:
    result = _producer(
        _occurrence(record_id="occ-1"),
        wall_record=_mapping_record(target_page_id="99"),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert INTERNAL_ELEVATION_FINISH_LINEAGE_MISMATCH in result.reason_codes


def test_binding_authority_constructors_are_sealed() -> None:
    with pytest.raises(TypeError, match="from_authorities"):
        InternalElevationFinishBindingProducer(
            wall_face_authority=_wall_face_authority(),
            material_authority=_material_authority(_occurrence(record_id="occ-1")),
            physical_wall_authority=_physical_wall_authority(TARGET_WALL),
        )
    with pytest.raises(TypeError, match="producer-owned"):
        InternalElevationFinishBindingAuthority({})
