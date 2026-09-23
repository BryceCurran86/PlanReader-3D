"""Source room-face -> EntityEvidence -> room-area shadow bridge tests."""
from __future__ import annotations

import math
from pathlib import Path

import fitz

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    ScaleSourceReading,
    ScaleSourceType,
    resolve_page_scale_calibration,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_area_bridge import (
    SOURCE_ROOM_AREA_BRIDGE_CONTEXT_MISMATCH,
    SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE,
    SOURCE_ROOM_AREA_BRIDGE_RESOLVED,
    SOURCE_ROOM_AREA_ENTITY_BOUND,
    build_source_room_area_bridge,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _write_plan(path: Path, *, with_partition: bool = True) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    lines = [
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
    ]
    if with_partition:
        lines.append(((150.0, 50.0), (150.0, 150.0)))
    for first, second in lines:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    doc.save(path)
    doc.close()


def _authority(path: Path):
    source = SourceVisibilityProducer(
        producer_method="source-room-area-bridge-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-room-area-doc",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    room_faces = build_source_room_face_authority(walls)
    selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    return published, room_faces, selector


def _context(published) -> ProviderContext:
    return ProviderContext(
        run_id="run-source-room-area",
        workspace_id="workspace-source-room-area",
        project_id="project-source-room-area",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-source-room-area",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-source-room-area", 1),),
    )


def _viewport(published) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp-source-room-area",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 300.0, 200.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def _document(published, *, source_sha256: str | None = None) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=source_sha256 or published.revision.source_sha256,
        page_count=1,
        page_ids=("1",),
        evidence_ids=(),
        producer="source-room-area-bridge-test",
        producer_version="1.0",
    )


def _firm_scale(published, *, source_type: ScaleSourceType = ScaleSourceType.SCALE_BAR):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="synthetic-plan",
        readings=[
            ScaleSourceReading(
                source_type=source_type.value,
                scale_text="1:100",
                ratio=100.0,
                confidence=1.0,
            )
        ],
        revision_id=published.revision.revision_id,
    )


def test_authenticated_room_faces_mint_entities_then_firm_room_area(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-area.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    scale = _firm_scale(published)

    result = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=scale,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (SOURCE_ROOM_AREA_BRIDGE_RESOLVED,)
    assert result.room_index is not None
    assert result.room_index.is_producer_owned
    assert len(result.entities) == 2
    assert len(result.quantities) == 2

    rooms = {room.room_ref: room for room in result.room_index.rooms()}
    for entity in result.entities:
        assert entity.status is EvidenceResolutionStatus.CORROBORATED
        assert entity.reason_codes == (SOURCE_ROOM_AREA_ENTITY_BOUND,)
        assert entity.candidate_entity_id in rooms
        assert set(entity.evidence_ids) == set(rooms[entity.candidate_entity_id].evidence)
        assert set(entity.evidence_ids).issubset(set(result.document.evidence_ids))

    for quantity in result.quantities:
        assert quantity.abstained is False
        assert quantity.status == AuthorityStatus.FIRM.value
        assert quantity.family == "room_area"
        room = rooms[quantity.input_entity_ids[0]]
        expected = round(room.area_page_pts2 / (scale.px_per_m ** 2), 6)
        assert math.isclose(quantity.value or 0.0, expected, abs_tol=1e-6)


def test_title_block_only_scale_is_not_promoted_by_bridge(tmp_path: Path) -> None:
    path = tmp_path / "two-room-title-scale.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)

    result = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(
            published,
            source_type=ScaleSourceType.TITLE_BLOCK,
        ),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.quantities) == 2
    assert all(quantity.abstained for quantity in result.quantities)
    assert all(
        "scale_not_firm" in quantity.blocking_reasons
        for quantity in result.quantities
    )


def test_missing_scale_keeps_room_identity_but_blocks_metric_area(tmp_path: Path) -> None:
    path = tmp_path / "two-room-no-scale.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)

    result = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=None,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.entities) == 2
    assert len(result.quantities) == 2
    assert all(quantity.abstained for quantity in result.quantities)
    assert all(
        "no_authoritative_area_input" in quantity.blocking_reasons
        for quantity in result.quantities
    )


def test_document_identity_mismatch_fails_before_entity_minting(tmp_path: Path) -> None:
    path = tmp_path / "two-room-context-mismatch.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)

    result = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published, source_sha256="0" * 64),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_ROOM_AREA_BRIDGE_CONTEXT_MISMATCH,)
    assert result.entities == ()
    assert result.quantities == ()


def test_unresolved_single_loop_cannot_create_room_entities(tmp_path: Path) -> None:
    path = tmp_path / "single-loop.pdf"
    _write_plan(path, with_partition=False)
    published, room_faces, selector = _authority(path)

    result = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE,)
    assert result.room_index is None
    assert result.entities == ()
    assert result.quantities == ()


def test_bridge_replay_is_deterministic_and_does_not_mutate_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-replay.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    document = _document(published)
    before = document.to_dict()
    kwargs = dict(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=document,
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )

    first = build_source_room_area_bridge(**kwargs)
    second = build_source_room_area_bridge(**kwargs)

    assert document.to_dict() == before
    assert tuple(entity.to_dict() for entity in first.entities) == tuple(
        entity.to_dict() for entity in second.entities
    )
    assert tuple(quantity.to_dict() for quantity in first.quantities) == tuple(
        quantity.to_dict() for quantity in second.quantities
    )
    assert first.room_index is not None
    assert second.room_index is not None
    assert first.room_index.index_id == second.room_index.index_id
