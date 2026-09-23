"""End-to-end fully source-owned ceiling-lining shadow tests."""
from __future__ import annotations

import fitz
import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_physical_scale_calibration_bridge import (
    PHYSICAL_SCALE_CALIBRATION_RESOLVED,
    PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE,
)
from pb_source_owned_ceiling_lining_pipeline import (
    SOURCE_OWNED_CEILING_SHADOW_COMPOSED,
    SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH,
    run_source_owned_ceiling_lining_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _source_pdf(*, include_scale_bar: bool = True) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=280.0)

        # Two bounded rooms sharing one wall. The room-face authority needs
        # exact multi-room topology and a two-sided shared physical wall.
        for first, second in (
            ((40.0, 40.0), (320.0, 40.0)),
            ((320.0, 40.0), (320.0, 160.0)),
            ((320.0, 160.0), (40.0, 160.0)),
            ((40.0, 160.0), (40.0, 40.0)),
            ((180.0, 40.0), (180.0, 160.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1,
            )

        # Short explicit finish note fully inside the left room.
        page.insert_text(
            fitz.Point(60.0, 100.0),
            "CEILING FINISH: BOARD",
            fontsize=7.0,
            color=(0, 0, 0),
        )

        # Ratio text alone is deliberately non-authoritative. A real graphic
        # scale bar must exist for the positive case.
        page.insert_text(
            fitz.Point(255.0, 245.0),
            "SCALE 1:100",
            fontsize=8.0,
            color=(0, 0, 0),
        )

        if include_scale_bar:
            span = POINTS_PER_METRE_AT_1_1 / 100.0
            x0, x1, y = 60.0, 60.0 + span, 220.0
            shape = page.new_shape()
            shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
            shape.draw_line(fitz.Point(x0, y - 8.0), fitz.Point(x0, y + 8.0))
            shape.draw_line(fitz.Point(x1, y - 8.0), fitz.Point(x1, y + 8.0))
            shape.finish(width=1.0)
            shape.commit()
            page.insert_text(fitz.Point(x0 - 2.0, y + 24.0), "0", fontsize=8.0)
            page.insert_text(fitz.Point(x1 - 4.0, y + 24.0), "1m", fontsize=8.0)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _setup(*, include_scale_bar: bool = True):
    source = SourceVisibilityProducer(
        producer_method="source-owned-ceiling-shadow-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-owned-ceiling-shadow-doc",
        source_bytes=_source_pdf(include_scale_bar=include_scale_bar),
        source_locator="memory://source-owned-ceiling-shadow.pdf",
    )
    context = ProviderContext(
        run_id="run-source-owned-ceiling-shadow",
        workspace_id="workspace-source-owned-ceiling-shadow",
        project_id="project-source-owned-ceiling-shadow",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-full-page",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-full-page", 1),),
    )
    viewport = ViewportEvidence(
        viewport_id="vp-full-page",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 420.0, 280.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )
    return source, published, context, viewport


def test_complete_source_owned_chain_resolves_one_room_finish_only() -> None:
    source, _published, context, viewport = _setup(include_scale_bar=True)

    result = run_source_owned_ceiling_lining_shadow(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (SOURCE_OWNED_CEILING_SHADOW_COMPOSED,)
    assert len(result.finish_candidates) == 1
    assert result.scale_bridge.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scale_bridge.reason_codes == (PHYSICAL_SCALE_CALIBRATION_RESOLVED,)
    assert result.scale_calibration is not None

    assert len(result.room_area_quantities) == 2
    assert all(
        not quantity.abstained and quantity.status == AuthorityStatus.FIRM.value
        for quantity in result.room_area_quantities
    )

    assert len(result.ceiling_quantities) == 2
    resolved = [quantity for quantity in result.ceiling_quantities if not quantity.abstained]
    blocked = [quantity for quantity in result.ceiling_quantities if quantity.abstained]
    assert len(resolved) == 1
    assert len(blocked) == 1
    assert resolved[0].status == AuthorityStatus.PROVISIONAL.value
    assert resolved[0].metadata["shadow_only"] is True
    assert resolved[0].metadata["commercial_projection_allowed"] is False
    assert "missing_explicit_ceiling_finish" in blocked[0].blocking_reasons


def test_ratio_text_without_graphic_bar_keeps_metric_chain_blocked() -> None:
    source, _published, context, viewport = _setup(include_scale_bar=False)

    result = run_source_owned_ceiling_lining_shadow(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.finish_candidates) == 1
    assert result.scale_bridge.status is EvidenceResolutionStatus.ABSTAINED
    assert result.scale_bridge.reason_codes == (PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE,)
    assert result.scale_calibration is None
    assert len(result.room_area_quantities) == 2
    assert all(quantity.abstained for quantity in result.room_area_quantities)
    assert all(
        "no_authoritative_area_input" in quantity.blocking_reasons
        for quantity in result.room_area_quantities
    )
    assert len(result.ceiling_quantities) == 2
    assert all(quantity.abstained for quantity in result.ceiling_quantities)
    assert all(
        "upstream_area_not_authoritative" in quantity.blocking_reasons
        for quantity in result.ceiling_quantities
    )


def test_stale_entry_snapshot_is_rejected_before_composition() -> None:
    source, _published, context, viewport = _setup(include_scale_bar=True)
    stale = ProviderContext(
        run_id=context.run_id,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        document_id=context.document_id,
        source_sha256=context.source_sha256,
        revision_id=context.revision_id,
        current_revision_id=context.current_revision_id,
        selected_pages=context.selected_pages,
        owned_viewport_ids=context.owned_viewport_ids,
        evidence_snapshot_id="stale-snapshot",
        canonical_graph_snapshot_id=context.canonical_graph_snapshot_id,
        measurement_authority_snapshot_id=context.measurement_authority_snapshot_id,
        source_pdf=context.source_pdf,
        workspace_record_id=context.workspace_record_id,
        owned_page_numbers=context.owned_page_numbers,
        viewport_page_ownership=context.viewport_page_ownership,
    )

    with pytest.raises(ValueError, match=SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH):
        run_source_owned_ceiling_lining_shadow(
            source_visibility_producer=source,
            context=stale,
            viewport=viewport,
            page_no=1,
        )
