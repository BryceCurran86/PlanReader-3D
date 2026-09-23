"""Source room-face indexes must be exact-viewport scoped."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_ceiling_lining_scope_binder import build_owned_source_room_face_index
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _write_two_room_plan(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
        ((150.0, 50.0), (150.0, 150.0)),
    ):
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
        producer_method="viewport-room-scope-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="viewport-room-scope-doc",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    faces = build_source_room_face_authority(walls)
    selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    result = faces.resolve_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    return published, faces, selector, result


def _context(published, viewport_id: str) -> ProviderContext:
    return ProviderContext(
        run_id="run-viewport-room-scope",
        workspace_id="workspace-viewport-room-scope",
        project_id="project-viewport-room-scope",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=(viewport_id,),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=((viewport_id, 1),),
    )


def _viewport(published, viewport_id: str, bbox) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id=published.revision.document_id,
        page_id="1",
        bbox=bbox,
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def test_room_index_keeps_only_faces_fully_owned_by_selected_viewport(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-viewport.pdf"
    _write_two_room_plan(path)
    published, faces, selector, result = _authority(path)

    left = min(
        result.records,
        key=lambda record: sum(point[0] for point in record.polygon_pdf_pts)
        / len(record.polygon_pdf_pts),
    )
    xs = [point[0] for point in left.polygon_pdf_pts]
    ys = [point[1] for point in left.polygon_pdf_pts]
    bbox = (
        min(xs) - 1.0,
        min(ys) - 1.0,
        max(xs) + 1.0,
        max(ys) + 1.0,
    )
    viewport_id = "vp-left-room"
    index = build_owned_source_room_face_index(
        room_face_authority=faces,
        selector=selector,
        context=_context(published, viewport_id),
        viewport=_viewport(published, viewport_id, bbox),
    )

    assert index is not None
    assert index.is_producer_owned
    assert [room.room_ref for room in index.rooms()] == [left.face_id]


def test_partial_viewport_cannot_claim_room_face_it_only_intersects(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-partial-viewport.pdf"
    _write_two_room_plan(path)
    published, faces, selector, result = _authority(path)

    left = min(
        result.records,
        key=lambda record: sum(point[0] for point in record.polygon_pdf_pts)
        / len(record.polygon_pdf_pts),
    )
    xs = [point[0] for point in left.polygon_pdf_pts]
    ys = [point[1] for point in left.polygon_pdf_pts]
    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0
    viewport_id = "vp-partial-room"
    index = build_owned_source_room_face_index(
        room_face_authority=faces,
        selector=selector,
        context=_context(published, viewport_id),
        viewport=_viewport(
            published,
            viewport_id,
            (
                center_x - 10.0,
                center_y - 10.0,
                center_x + 10.0,
                center_y + 10.0,
            ),
        ),
    )

    assert index is None
