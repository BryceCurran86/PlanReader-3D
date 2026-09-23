"""Source-authenticated room-face authority tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _write_plan(path: Path, *, with_partition: bool) -> None:
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


def _scope(path: Path):
    source = SourceVisibilityProducer(
        producer_method="source-room-face-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    )
    wall_authority = wall_producer.authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    wall_scope = wall_authority.resolve_scope(wall_selector)
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    room_authority = build_source_room_face_authority(wall_authority)
    room_selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    return room_authority.resolve_scope(room_selector)


def test_two_room_source_plan_publishes_exact_room_faces(tmp_path: Path) -> None:
    path = tmp_path / "two-room.pdf"
    _write_plan(path, with_partition=True)

    result = _scope(path)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_RESOLVED,)
    assert len(result.records) == 2
    assert all(record.area_page_pts2 > 0.0 for record in result.records)
    assert all(len(record.polygon_pdf_pts) >= 4 for record in result.records)
    assert all(record.bounding_wall_ids for record in result.records)
    assert len({record.face_id for record in result.records}) == 2


def test_single_box_cannot_mint_room_face_authority(tmp_path: Path) -> None:
    path = tmp_path / "single-box.pdf"
    _write_plan(path, with_partition=False)

    result = _scope(path)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.scope_complete is False
    assert result.records == ()
    assert SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS in result.reason_codes


def test_selector_lookup_is_exact_lineage(tmp_path: Path) -> None:
    path = tmp_path / "lineage.pdf"
    _write_plan(path, with_partition=True)

    source = SourceVisibilityProducer(
        producer_method="source-room-face-lineage-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="lineage-doc",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    authority = build_source_room_face_authority(walls)

    missing = authority.resolve_scope(
        SourceRoomFaceSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256="0" * 64,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    assert missing.status is EvidenceResolutionStatus.ABSTAINED
    assert missing.records == ()
