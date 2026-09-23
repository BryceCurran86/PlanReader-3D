"""C15 source-authenticated room-face scope binding tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_ceiling_lining_finish_evidence import (
    collect_unscoped_ceiling_finish_candidates,
)
from pb_ceiling_lining_scope_binder import (
    GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES,
    bind_unscoped_finish_candidates_to_room,
    build_owned_source_room_face_index,
    resolve_ceiling_finish_scope_proofs,
)
from pb_migration_contracts import (
    DocumentEvidence,
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


def _source_room_faces(path: Path):
    source = SourceVisibilityProducer(
        producer_method="c15-source-room-face-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="c15-room-doc",
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


def _context(published) -> ProviderContext:
    return ProviderContext(
        run_id="run-c15-source-room",
        workspace_id="workspace-c15-source-room",
        project_id="project-c15-source-room",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-source-room",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-source-room", 1),),
    )


def _viewport(published) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp-source-room",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 300.0, 200.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def test_explicit_ceiling_finish_binds_to_unique_source_room_face(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-room-ceiling.pdf"
    _write_two_room_plan(path)
    published, face_authority, selector, face_result = _source_room_faces(path)
    context = _context(published)
    viewport = _viewport(published)

    room_index = build_owned_source_room_face_index(
        room_face_authority=face_authority,
        selector=selector,
        context=context,
        viewport=viewport,
    )
    assert room_index is not None
    assert room_index.is_producer_owned
    assert room_index.geometry_source == GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES
    assert len(room_index.rooms()) == 2

    target = face_result.records[0]
    xs = [point[0] for point in target.polygon_pdf_pts]
    ys = [point[1] for point in target.polygon_pdf_pts]
    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0
    bbox = (center_x - 2.0, center_y - 2.0, center_x + 2.0, center_y + 2.0)

    candidates = collect_unscoped_ceiling_finish_candidates(
        page_text="CEILING FINISH: 10mm chip board",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        page_id="1",
        page_no=1,
        viewport_id=viewport.viewport_id,
        text_geometry=(
            {
                "raw_text": "CEILING FINISH: 10mm chip board",
                "bbox": bbox,
            },
        ),
        method="native_pdf_text",
    )
    assert len(candidates) == 1

    document = DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=1,
        page_ids=("1",),
        evidence_ids=(candidates[0].evidence_id,),
        producer="c15-source-room-test",
        producer_version="1",
    )
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        room_index=room_index,
        document=document,
        viewport=viewport,
    )
    assert len(proofs) == 1
    assert proofs[0].room_entity_id == target.face_id
    assert proofs[0].is_resolver_minted

    scoped = bind_unscoped_finish_candidates_to_room(
        candidates=candidates,
        queried_room_ref=target.face_id,
        proofs=proofs,
        room_index=room_index,
        document=document,
        viewport=viewport,
    )
    assert len(scoped) == 1
    assert scoped[0].metadata["scope_entity_id"] == target.face_id
    assert scoped[0].metadata["scope_bound"] is True


def test_ceiling_finish_outside_source_rooms_remains_unbound(tmp_path: Path) -> None:
    path = tmp_path / "two-room-outside-note.pdf"
    _write_two_room_plan(path)
    published, face_authority, selector, _face_result = _source_room_faces(path)
    context = _context(published)
    viewport = _viewport(published)
    room_index = build_owned_source_room_face_index(
        room_face_authority=face_authority,
        selector=selector,
        context=context,
        viewport=viewport,
    )
    assert room_index is not None

    candidates = collect_unscoped_ceiling_finish_candidates(
        page_text="CEILING FINISH: 10mm chip board",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        page_id="1",
        page_no=1,
        viewport_id=viewport.viewport_id,
        text_geometry=(
            {
                "raw_text": "CEILING FINISH: 10mm chip board",
                "bbox": (5.0, 5.0, 15.0, 15.0),
            },
        ),
        method="native_pdf_text",
    )
    document = DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=1,
        page_ids=("1",),
        evidence_ids=tuple(atom.evidence_id for atom in candidates),
        producer="c15-source-room-test",
        producer_version="1",
    )
    proofs = resolve_ceiling_finish_scope_proofs(
        candidates=candidates,
        room_index=room_index,
        document=document,
        viewport=viewport,
    )
    assert proofs == ()
