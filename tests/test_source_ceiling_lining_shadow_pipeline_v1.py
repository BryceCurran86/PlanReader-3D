"""End-to-end source-authenticated ceiling-lining shadow pipeline tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_ceiling_lining_finish_evidence import collect_unscoped_ceiling_finish_candidates
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
from pb_source_ceiling_lining_shadow_pipeline import run_source_ceiling_lining_shadow
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


NOTE = "CEILING FINISH: 12mm gypsum plasterboard"


def _plan_bytes() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300, height=200)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _setup(tmp_path: Path):
    payload = _plan_bytes()
    source = SourceVisibilityProducer(
        producer_method="source-ceiling-shadow-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-ceiling-shadow-doc",
        source_bytes=payload,
        source_locator=str(tmp_path / "source-ceiling-shadow.pdf"),
    )
    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    room_authority = build_source_room_face_authority(wall_authority)
    selector = SourceRoomFaceSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    resolved = room_authority.resolve_scope(selector)
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert len(resolved.records) == 2

    first = resolved.records[0]
    xs = [point[0] for point in first.polygon_pdf_pts]
    ys = [point[1] for point in first.polygon_pdf_pts]
    bbox = (
        min(xs) + 10.0,
        min(ys) + 10.0,
        min(xs) + 40.0,
        min(ys) + 24.0,
    )
    candidates = collect_unscoped_ceiling_finish_candidates(
        page_text=NOTE,
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        page_id="1",
        page_no=1,
        viewport_id="vp-source-ceiling",
        text_geometry=({"raw_text": NOTE, "bbox": bbox},),
        method="native_pdf_text",
    )
    assert len(candidates) == 1

    document = DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=1,
        page_ids=("1",),
        evidence_ids=(candidates[0].evidence_id,),
        producer="source-ceiling-shadow-test",
        producer_version="1.0",
    )
    viewport = ViewportEvidence(
        viewport_id="vp-source-ceiling",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 300.0, 200.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(candidates[0].evidence_id,),
        confidence=1.0,
    )
    context = ProviderContext(
        run_id="run-source-ceiling",
        workspace_id="workspace-source-ceiling",
        project_id="project-source-ceiling",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=(viewport.viewport_id,),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=((viewport.viewport_id, 1),),
    )
    return published, room_authority, selector, document, viewport, context, candidates


def _scale(published, source_type: ScaleSourceType):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="synthetic-floor-plan",
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


def test_one_room_finish_does_not_leak_to_sibling_room(tmp_path: Path) -> None:
    (
        published,
        room_authority,
        selector,
        document,
        viewport,
        context,
        candidates,
    ) = _setup(tmp_path)

    result = run_source_ceiling_lining_shadow(
        room_face_authority=room_authority,
        selector=selector,
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        unscoped_finish_candidates=candidates,
        scale_calibration=_scale(published, ScaleSourceType.SCALE_BAR),
    )

    assert len(result.room_area_quantities) == 2
    assert all(
        quantity.status == AuthorityStatus.FIRM.value
        and not quantity.abstained
        for quantity in result.room_area_quantities
    )

    assert len(result.ceiling_quantities) == 2
    resolved = [
        quantity for quantity in result.ceiling_quantities if not quantity.abstained
    ]
    blocked = [
        quantity for quantity in result.ceiling_quantities if quantity.abstained
    ]
    assert len(resolved) == 1
    assert len(blocked) == 1
    assert resolved[0].status == AuthorityStatus.PROVISIONAL.value
    assert resolved[0].metadata["shadow_only"] is True
    assert resolved[0].metadata["commercial_projection_allowed"] is False
    assert "missing_explicit_ceiling_finish" in blocked[0].blocking_reasons


def test_title_block_scale_cannot_be_promoted_by_pipeline(tmp_path: Path) -> None:
    (
        published,
        room_authority,
        selector,
        document,
        viewport,
        context,
        candidates,
    ) = _setup(tmp_path)

    result = run_source_ceiling_lining_shadow(
        room_face_authority=room_authority,
        selector=selector,
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        unscoped_finish_candidates=candidates,
        scale_calibration=_scale(published, ScaleSourceType.TITLE_BLOCK),
    )

    assert len(result.room_area_quantities) == 2
    assert all(quantity.abstained for quantity in result.room_area_quantities)
    assert all(
        "scale_not_firm" in quantity.blocking_reasons
        for quantity in result.room_area_quantities
    )
    assert len(result.ceiling_quantities) == 2
    assert all(quantity.abstained for quantity in result.ceiling_quantities)
    assert all(
        "upstream_area_not_authoritative" in quantity.blocking_reasons
        for quantity in result.ceiling_quantities
    )
