"""Source-closed ceiling review export tests."""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

from pb_ceiling_lining_review_promotion import (
    CeilingLiningReviewCandidate,
    build_ceiling_lining_review_promotions,
)
from pb_live_ceiling_source_closed_export import seal_live_ceiling_review_run
from pb_migration_contracts import (
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_source_closed_run_export import SourceClosedRunConflictError
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_takeoff_authority_v164 import prepare_ai_takeoff_editor_save


def _source_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=280.0)
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
        page.insert_text(
            fitz.Point(60.0, 100.0),
            "CEILING FINISH: BOARD",
            fontsize=7.0,
        )
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


def _promotion():
    source = SourceVisibilityProducer(
        producer_method="ceiling-source-closed-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="ceiling-source-closed-doc",
        source_bytes=_source_pdf(),
        source_locator="memory://ceiling-source-closed.pdf",
    )
    context = ProviderContext(
        run_id="run-ceiling-source-closed",
        workspace_id="workspace-ceiling-source-closed",
        project_id="project-ceiling-source-closed",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-full-page",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        workspace_record_id=17,
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
    result = build_ceiling_lining_review_promotions(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )
    assert len(result.candidates) == 1
    return result


def test_promoted_ceiling_review_quantity_seals_deterministically() -> None:
    promotion = _promotion()

    first = seal_live_ceiling_review_run(
        promotion.candidates,
        project_id="project-ceiling-source-closed",
    )
    second = seal_live_ceiling_review_run(
        promotion.candidates,
        project_id="project-ceiling-source-closed",
    )

    assert len(first.quantities) == 1
    row = first.quantities[0]
    candidate = promotion.candidates[0]
    assert row.quantity_id == candidate.promoted_quantity.quantity_id
    assert row.family == "ceiling_lining"
    assert row.object_identity_refs == candidate.promoted_quantity.input_entity_ids
    assert row.lineage_ok is True
    assert first.run_id == second.run_id
    assert first.fingerprint == second.fingerprint


def test_raw_shadow_ceiling_cannot_be_substituted_for_promoted_quantity() -> None:
    promotion = _promotion()
    candidate = promotion.candidates[0]
    shadow = next(
        quantity
        for quantity in promotion.source_result.ceiling_quantities
        if quantity.quantity_id == candidate.shadow_quantity_id
    )
    damaged = replace(candidate, promoted_quantity=shadow)

    with pytest.raises(
        SourceClosedRunConflictError,
        match="did not pass review-promotion boundary",
    ):
        seal_live_ceiling_review_run(
            (damaged,),
            project_id="project-ceiling-source-closed",
        )


def test_reviewed_customer_row_is_not_used_as_source_closed_production_handoff() -> None:
    promotion = _promotion()
    candidate = promotion.candidates[0]
    reviewed = prepare_ai_takeoff_editor_save(
        dict(candidate.review_row),
        {
            "quantity_status": "Measured",
            "confidence": "Verified",
        },
    )
    damaged = CeilingLiningReviewCandidate(
        shadow_quantity_id=candidate.shadow_quantity_id,
        promoted_quantity=candidate.promoted_quantity,
        source_trace=candidate.source_trace,
        measurement_authority=candidate.measurement_authority,
        review_row=reviewed,
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="bypassed estimator review state",
    ):
        seal_live_ceiling_review_run(
            (damaged,),
            project_id="project-ceiling-source-closed",
        )
