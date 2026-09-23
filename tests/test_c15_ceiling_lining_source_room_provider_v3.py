"""C15 end-to-end source-room authority -> room area -> ceiling shadow tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_ceiling_lining_finish_evidence import (
    collect_unscoped_ceiling_finish_candidates,
)
from pb_ceiling_lining_shadow_provider import (
    CeilingLiningShadowInputs,
    CeilingLiningShadowProvider,
)
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
from pb_source_room_area_bridge import build_source_room_area_bridge
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


FINISH_TEXT = "CEILING FINISH: 10mm chip board"


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
    # Small native text fully inside the left room.
    page.insert_text(fitz.Point(62.0, 102.0), FINISH_TEXT, fontsize=5)
    doc.save(path)
    doc.close()


def _source(path: Path):
    source = SourceVisibilityProducer(
        producer_method="c15-source-room-provider-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="c15-source-room-provider-doc",
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
        run_id="run-c15-source-room-provider",
        workspace_id="workspace-c15-source-room-provider",
        project_id="project-c15-source-room-provider",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-c15-source-room",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-c15-source-room", 1),),
    )


def _viewport(published) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp-c15-source-room",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 300.0, 200.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def _document(published, evidence_ids=()) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=1,
        page_ids=("1",),
        evidence_ids=tuple(sorted(set(evidence_ids))),
        producer="c15-source-room-provider-test",
        producer_version="1.0",
    )


def _scale(published):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="synthetic-plan",
        readings=(
            ScaleSourceReading(
                source_type=ScaleSourceType.SCALE_BAR.value,
                scale_text="1:100",
                ratio=100.0,
                confidence=1.0,
            ),
        ),
        revision_id=published.revision.revision_id,
    )


def _finish_candidates(path: Path, published, viewport):
    doc = fitz.open(path)
    try:
        page = doc[0]
        page_text = page.get_text("text")
        blocks = [
            block
            for block in page.get_text("blocks")
            if FINISH_TEXT in str(block[4])
        ]
        assert len(blocks) == 1
        bbox = tuple(float(value) for value in blocks[0][:4])
    finally:
        doc.close()
    return collect_unscoped_ceiling_finish_candidates(
        page_text=page_text,
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        page_id="1",
        page_no=1,
        viewport_id=viewport.viewport_id,
        text_geometry=({"raw_text": FINISH_TEXT, "bbox": bbox},),
        method="native_pdf_text",
    )


def _prepared(path: Path):
    published, room_faces, selector = _source(path)
    context = _context(published)
    viewport = _viewport(published)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=context,
        document=_document(published),
        viewport=viewport,
        page_no=1,
        scale_calibration=_scale(published),
    )
    assert bridge.status is EvidenceResolutionStatus.CORROBORATED
    assert len(bridge.quantities) == 2
    assert all(
        quantity.status == AuthorityStatus.FIRM.value
        and not quantity.abstained
        for quantity in bridge.quantities
    )
    candidates = _finish_candidates(path, published, viewport)
    assert len(candidates) == 1
    document = DocumentEvidence(
        document_id=bridge.document.document_id,
        source_sha256=bridge.document.source_sha256,
        page_count=bridge.document.page_count,
        page_ids=bridge.document.page_ids,
        evidence_ids=tuple(
            sorted(
                {
                    *bridge.document.evidence_ids,
                    *(candidate.evidence_id for candidate in candidates),
                }
            )
        ),
        producer=bridge.document.producer,
        producer_version=bridge.document.producer_version,
        metadata=dict(bridge.document.metadata or {}),
    )
    return (
        published,
        room_faces,
        selector,
        context,
        viewport,
        bridge,
        candidates,
        document,
    )


def test_source_room_authority_drives_one_room_ceiling_shadow_only(
    tmp_path: Path,
) -> None:
    path = tmp_path / "c15-two-room-source.pdf"
    _write_two_room_plan(path)
    (
        _published,
        room_faces,
        selector,
        context,
        viewport,
        bridge,
        candidates,
        document,
    ) = _prepared(path)

    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=document,
            viewport=viewport,
            page_no=1,
            authoritative_area_quantities=bridge.quantities,
            unscoped_finish_candidates=candidates,
            source_room_face_authority=room_faces,
            source_room_face_selector=selector,
        )
    )
    result = provider.extract(context)

    assert len(result.quantities) == 2
    resolved = tuple(quantity for quantity in result.quantities if not quantity.abstained)
    blocked = tuple(quantity for quantity in result.quantities if quantity.abstained)
    assert len(resolved) == 1
    assert len(blocked) == 1

    ceiling = resolved[0]
    assert ceiling.family == "ceiling_lining"
    assert ceiling.status == AuthorityStatus.PROVISIONAL.value
    assert ceiling.metadata["shadow_only"] is True
    assert ceiling.metadata["commercial_projection_allowed"] is False
    assert ceiling.metadata["finish_descriptor"] == "10mm chip board"

    area_by_scope = {
        quantity.input_entity_ids[0]: quantity
        for quantity in bridge.quantities
    }
    ceiling_scope = ceiling.input_entity_ids[0]
    assert ceiling_scope in area_by_scope
    assert ceiling.value == area_by_scope[ceiling_scope].value

    assert "missing_explicit_ceiling_finish" in blocked[0].blocking_reasons
    assert blocked[0].input_entity_ids[0] != ceiling_scope


def test_partial_source_room_authority_pair_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "c15-partial-source-pair.pdf"
    _write_two_room_plan(path)
    (
        _published,
        room_faces,
        _selector,
        context,
        viewport,
        bridge,
        candidates,
        document,
    ) = _prepared(path)

    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=document,
            viewport=viewport,
            page_no=1,
            authoritative_area_quantities=bridge.quantities,
            unscoped_finish_candidates=candidates,
            source_room_face_authority=room_faces,
            source_room_face_selector=None,
        )
    )
    result = provider.extract(context)

    assert len(result.quantities) == 2
    assert all(quantity.abstained for quantity in result.quantities)
    assert all(
        "missing_explicit_ceiling_finish" in quantity.blocking_reasons
        for quantity in result.quantities
    )


def test_wrong_source_room_selector_lineage_cannot_bind_finish(tmp_path: Path) -> None:
    path = tmp_path / "c15-wrong-selector.pdf"
    _write_two_room_plan(path)
    (
        published,
        room_faces,
        selector,
        context,
        viewport,
        bridge,
        candidates,
        document,
    ) = _prepared(path)
    wrong_selector = SourceRoomFaceSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256="0" * 64,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    )

    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=document,
            viewport=viewport,
            page_no=1,
            authoritative_area_quantities=bridge.quantities,
            unscoped_finish_candidates=candidates,
            source_room_face_authority=room_faces,
            source_room_face_selector=wrong_selector,
        )
    )
    result = provider.extract(context)

    assert published.revision.source_sha256 != wrong_selector.source_sha256
    assert len(result.quantities) == 2
    assert all(quantity.abstained for quantity in result.quantities)
    assert all(
        "missing_explicit_ceiling_finish" in quantity.blocking_reasons
        for quantity in result.quantities
    )
