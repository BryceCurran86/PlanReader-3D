"""Tests for authenticated internal-elevation wall-face mapping."""
from __future__ import annotations

import fitz
import pytest

import pb_internal_elevation_wall_face_authority as mapping
from pb_cross_sheet_callout_evidence import CalloutReferenceEvidence
from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationRecord,
    CrossSheetRegistrationResult,
    CrossSheetRegistrationSelector,
    _AUTHORITY_SEAL as CROSS_AUTHORITY_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as WALL_AUTHORITY_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceRecord,
    SourceRoomFaceScopeResult,
    SourceRoomFaceSelector,
    _AUTHORITY_SEAL as ROOM_AUTHORITY_SEAL,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
    _stamp_segment_page_viewports_product,
)
from pb_wall_room_topology_contracts import MeasurementAuthorityType, WallCandidate

DOC = "doc-internal-elevation-test"
SRC_PAGE = "1"
TGT_PAGE = "2"
SRC_WALL = "wall-src"
TGT_WALL = "wall-elev"


def _pdf(callout_pos=(45.0, 50.0)) -> bytes:
    doc = fitz.open()
    src = doc.new_page(width=220.0, height=140.0)
    src.insert_text(fitz.Point(*callout_pos), "1/A20", fontsize=10)
    tgt = doc.new_page(width=220.0, height=140.0)
    tgt.draw_rect(fitz.Rect(10.0, 10.0, 210.0, 130.0), color=(0, 0, 0))
    tgt.insert_text((80.0, 125.0), "ELEVATION 1", fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def _ingest(source_bytes: bytes):
    source = SourceVisibilityProducer(
        producer_method="internal-elevation-wall-face-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=DOC,
        source_bytes=source_bytes,
        source_locator="memory:internal-elevation-test.pdf",
    )
    return source, published


def _candidate(candidate_id: str, *, viewport_id: str, pts) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="double_line",
        centerline_pts=pts,
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


def _wall_record(candidate_id: str, *, viewport_id: str, pts) -> PhysicalWallCandidateRecord:
    return PhysicalWallCandidateRecord(
        wall_candidate_id=candidate_id,
        wall_candidate=_candidate(candidate_id, viewport_id=viewport_id, pts=pts),
        physical_identity=PhysicalWallIdentity(
            wall_candidate_id=candidate_id,
            viewport_id=viewport_id,
            candidate_identity_id=f"identity-{candidate_id}",
            path_fingerprint=f"path-{candidate_id}",
            source_primitive_ids=(f"primitive-{candidate_id}",),
            edge_ids=(f"edge-{candidate_id}",),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )


def _wall_authority(published) -> PhysicalWallCandidateAuthority:
    results = {}
    for page_id, records in (
        (
            SRC_PAGE,
            (
                _wall_record(
                    SRC_WALL,
                    viewport_id="source-plan-vp",
                    pts=((100.0, 10.0), (100.0, 120.0)),
                ),
            ),
        ),
        (
            TGT_PAGE,
            (
                _wall_record(
                    TGT_WALL,
                    viewport_id="target-elevation-vp",
                    pts=((30.0, 60.0), (180.0, 60.0)),
                ),
            ),
        ),
    ):
        key = _ScopeKey(
            document_id=DOC,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        results[key] = PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            scope_complete=True,
            records=records,
            source_observation_ids=(),
            document_id=DOC,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
            reason_codes=(),
        )
    return PhysicalWallCandidateAuthority(results, _seal=WALL_AUTHORITY_SEAL)


def _room_record(
    published,
    *,
    face_id: str,
    polygon,
    walls,
) -> SourceRoomFaceRecord:
    return SourceRoomFaceRecord(
        record_id=f"record-{face_id}",
        face_id=face_id,
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=SRC_PAGE,
        decision_scope_id=f"wall-source:page-{SRC_PAGE}",
        polygon_pdf_pts=tuple(polygon),
        bounding_wall_ids=tuple(walls),
        area_page_pts2=10000.0,
    )


def _room_authority(
    published,
    *,
    complete: bool = True,
    overlap: bool = False,
    selected_wall_present: bool = True,
    include_right: bool = True,
) -> SourceRoomFaceAuthority:
    left_walls = (SRC_WALL, "left-a", "left-b", "left-c") if selected_wall_present else (
        "left-a",
        "left-b",
        "left-c",
        "left-d",
    )
    left = _room_record(
        published,
        face_id="room-left",
        polygon=((10.0, 10.0), (100.0, 10.0), (100.0, 120.0), (10.0, 120.0)),
        walls=left_walls,
    )
    right_polygon = (
        ((20.0, 20.0), (90.0, 20.0), (90.0, 110.0), (20.0, 110.0))
        if overlap
        else ((100.0, 10.0), (210.0, 10.0), (210.0, 120.0), (100.0, 120.0))
    )
    right = _room_record(
        published,
        face_id="room-right",
        polygon=right_polygon,
        walls=(SRC_WALL, "right-a", "right-b", "right-c"),
    )
    selector = SourceRoomFaceSelector(
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=SRC_PAGE,
        decision_scope_id=f"wall-source:page-{SRC_PAGE}",
    )
    result = SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=complete,
        records=((left, right) if include_right else (left,)),
        reason_codes=(),
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=SRC_PAGE,
        decision_scope_id=f"wall-source:page-{SRC_PAGE}",
    )
    return SourceRoomFaceAuthority({selector.key: result}, _seal=ROOM_AUTHORITY_SEAL)


def _cross_authority(published) -> CrossSheetRegistrationAuthority:
    selector = CrossSheetRegistrationSelector(
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_element_id=SRC_WALL,
    )
    record = CrossSheetRegistrationRecord(
        record_id="cross-record",
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_element_id=SRC_WALL,
        target_physical_element_id=TGT_WALL,
        source_view_type="floor_plan",
        target_view_type="elevation",
        callout_mark="1",
        referenced_sheet_code="A20",
    )
    return CrossSheetRegistrationAuthority(
        {
            selector.key: CrossSheetRegistrationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("cross_sheet_registration_resolved",),
                record=record,
            )
        },
        _seal=CROSS_AUTHORITY_SEAL,
    )


def _selector(published) -> mapping.InternalElevationWallFaceSelector:
    return mapping.InternalElevationWallFaceSelector(
        document_id=DOC,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_wall_id=SRC_WALL,
    )


def _patch_target_viewport(
    monkeypatch,
    *,
    view_type="elevation",
    view_id="authenticated-elevation-vp",
) -> None:
    viewport = SegmentedViewport(
        view_id=view_id,
        page_number=2,
        view_type=view_type,
        label="ELEVATION 1",
        title_bbox=(80.0, 110.0, 150.0, 128.0),
        bounding_box=(10.0, 10.0, 210.0, 130.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source=ViewportBoundarySource.VECTOR_FRAME.value,
        confidence=1.0,
    )
    stamped = tuple(_stamp_segment_page_viewports_product([viewport]))
    monkeypatch.setattr(mapping, "segment_page_viewports", lambda *_args, **_kwargs: stamped)


def _producer(
    source,
    published,
    monkeypatch,
    *,
    complete=True,
    overlap=False,
    selected_wall_present=True,
    include_right=True,
    view_type="elevation",
    view_id="authenticated-elevation-vp",
):
    _patch_target_viewport(monkeypatch, view_type=view_type, view_id=view_id)
    return mapping.InternalElevationWallFaceProducer.from_authorities(
        cross_sheet_authority=_cross_authority(published),
        physical_wall_authority=_wall_authority(published),
        room_face_authority=_room_authority(
            published,
            complete=complete,
            overlap=overlap,
            selected_wall_present=selected_wall_present,
            include_right=include_right,
        ),
        source_visibility_producer=source,
    )


def test_source_callout_maps_unique_room_facing_wall_to_elevation(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(source, published, monkeypatch)
    result = producer.publish(_selector(published))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.source_room_face_id == "room-left"
    assert result.record.physical_wall_id == SRC_WALL
    assert result.record.physical_face_id
    assert result.record.physical_wall_decision_scope_id == "wall-source:page-1"
    assert result.record.target_physical_wall_id == TGT_WALL
    assert result.record.target_view_type == "elevation"
    assert result.record.physical_face_role == "room_facing_interior_face"
    assert mapping.INTERNAL_ELEVATION_WALL_FACE_RESOLVED in result.reason_codes


def test_incomplete_room_face_universe_abstains(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(source, published, monkeypatch, complete=False)
    result = producer.publish(_selector(published))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert (
        mapping.INTERNAL_ELEVATION_ROOM_FACE_UNIVERSE_INCOMPLETE
        in result.reason_codes
    )


def test_callout_cannot_choose_room_not_bounded_by_selected_wall(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(
        source,
        published,
        monkeypatch,
        selected_wall_present=False,
    )
    result = producer.publish(_selector(published))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert mapping.INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED in result.reason_codes


def test_overlapping_room_faces_are_conflict_not_ranked(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(source, published, monkeypatch, overlap=True)
    result = producer.publish(_selector(published))

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert mapping.INTERNAL_ELEVATION_ROOM_FACE_AMBIGUOUS in result.reason_codes


def test_opposite_room_sides_of_same_internal_wall_have_distinct_face_ids(monkeypatch) -> None:
    source, published = _ingest(_pdf(callout_pos=(45.0, 50.0)))
    left = _producer(
        source,
        published,
        monkeypatch,
    ).publish(_selector(published))
    assert left.status is EvidenceResolutionStatus.CORROBORATED
    assert left.record is not None
    assert left.record.source_room_face_id == "room-left"

    # Keep the exact same immutable source lineage and cross-sheet registration;
    # change only which authenticated room-side the source callout occupies.
    monkeypatch.setattr(
        mapping,
        "find_callout_references",
        lambda _page, *, page_num: [
            CalloutReferenceEvidence(
                mark="1",
                referenced_sheet_code="A20",
                callout_bbox=(145.0, 40.0, 175.0, 55.0),
                source_page=page_num,
            )
        ],
    )
    right = _producer(
        source,
        published,
        monkeypatch,
    ).publish(_selector(published))
    assert right.status is EvidenceResolutionStatus.CORROBORATED
    assert right.record is not None
    assert right.record.source_room_face_id == "room-right"

    assert left.record.document_id == right.record.document_id
    assert left.record.revision_id == right.record.revision_id
    assert left.record.source_sha256 == right.record.source_sha256
    assert left.record.snapshot_id == right.record.snapshot_id
    assert left.record.physical_wall_id == right.record.physical_wall_id
    assert left.record.physical_face_role == right.record.physical_face_role
    assert left.record.physical_face_id != right.record.physical_face_id


def test_room_side_identity_ignores_polygon_vertex_start_and_direction() -> None:
    base = mapping._canonical_polygon_identity(
        ((10.0, 10.0), (100.0, 10.0), (100.0, 120.0), (10.0, 120.0))
    )
    shifted = mapping._canonical_polygon_identity(
        ((100.0, 120.0), (10.0, 120.0), (10.0, 10.0), (100.0, 10.0))
    )
    reversed_order = mapping._canonical_polygon_identity(
        ((10.0, 10.0), (10.0, 120.0), (100.0, 120.0), (100.0, 10.0))
    )
    assert base == shifted == reversed_order


def test_one_room_boundary_preserves_legacy_semantic_face_identity(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    result = _producer(
        source,
        published,
        monkeypatch,
        include_right=False,
    ).publish(_selector(published))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None

    expected = stable_contract_id(
        "physical_wall_semantic_face",
        {
            "document_id": DOC,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_id": SRC_PAGE,
            "physical_wall_decision_scope_id": f"wall-source:page-{SRC_PAGE}",
            "physical_wall_id": SRC_WALL,
            "physical_face_role": "room_facing_interior_face",
        },
        digest_chars=32,
    )
    assert result.record.physical_face_id == expected


def test_physical_face_identity_does_not_depend_on_target_viewport_id(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    first = _producer(
        source,
        published,
        monkeypatch,
        view_id="elevation-segmentation-v1",
    ).publish(_selector(published))
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.record is not None

    second = _producer(
        source,
        published,
        monkeypatch,
        view_id="elevation-segmentation-v2",
    ).publish(_selector(published))
    assert second.status is EvidenceResolutionStatus.CORROBORATED
    assert second.record is not None

    assert first.record.target_viewport_id != second.record.target_viewport_id
    assert first.record.physical_face_id == second.record.physical_face_id


def test_target_must_be_authenticated_elevation_view(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(
        source,
        published,
        monkeypatch,
        view_type="section",
    )
    result = producer.publish(_selector(published))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert mapping.INTERNAL_ELEVATION_TARGET_NOT_ELEVATION in result.reason_codes


def test_room_boundary_callout_does_not_choose_a_side() -> None:
    polygon = ((10.0, 10.0), (100.0, 10.0), (100.0, 120.0), (10.0, 120.0))
    assert mapping._strict_point_in_polygon((50.0, 50.0), polygon)
    assert not mapping._strict_point_in_polygon((100.0, 50.0), polygon)


def test_authority_missing_selector_abstains(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    producer = _producer(source, published, monkeypatch)
    result = producer.authority().resolve(_selector(published))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert mapping.INTERNAL_ELEVATION_WALL_FACE_UNAVAILABLE in result.reason_codes


def test_constructor_is_sealed(monkeypatch) -> None:
    source, published = _ingest(_pdf())
    with pytest.raises(TypeError, match="from_authorities"):
        mapping.InternalElevationWallFaceProducer(
            cross_sheet_authority=_cross_authority(published),
            physical_wall_authority=_wall_authority(published),
            room_face_authority=_room_authority(published),
            source_visibility_producer=source,
        )
