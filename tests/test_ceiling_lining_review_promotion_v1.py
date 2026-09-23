"""Ceiling-lining estimator-review promotion tests."""
from __future__ import annotations

import fitz
import pytest

from pb_ceiling_lining_review_promotion import (
    CEILING_REVIEW_PROMOTION_RESOLVED,
    CEILING_REVIEW_PROMOTION_UNAVAILABLE,
    build_ceiling_lining_review_promotions,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    MissingCommercialAuthorityError,
    existing_commercial_gate_results,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_takeoff_authority_v164 import prepare_ai_takeoff_editor_save


def _source_pdf(*, include_scale_bar: bool = True) -> bytes:
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
            color=(0, 0, 0),
        )
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
        producer_method="ceiling-review-promotion-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="ceiling-review-promotion-doc",
        source_bytes=_source_pdf(include_scale_bar=include_scale_bar),
        source_locator="memory://ceiling-review-promotion.pdf",
    )
    context = ProviderContext(
        run_id="run-ceiling-review-promotion",
        workspace_id="workspace-ceiling-review-promotion",
        project_id="project-ceiling-review-promotion",
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
    return source, context, viewport


def test_generic_adapter_rejects_explicit_shadow_quantity() -> None:
    quantity = QuantityEvidence(
        quantity_id="qty-shadow-ceiling",
        family="ceiling_lining",
        semantic_key="ceiling_lining:room-a",
        value=10.0,
        unit="m2",
        input_entity_ids=("room-a",),
        evidence_ids=("ev-finish",),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        status=AuthorityStatus.PROVISIONAL.value,
        confidence=1.0,
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "rev-1",
            "shadow_only": True,
            "commercial_projection_allowed": False,
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id="project-a",
        document_id="doc-a",
        source_sha256="a" * 64,
        source_page="1",
        viewport_id="vp-a",
        revision_id="rev-1",
        current_revision_id="rev-1",
        evidence_ids=("ev-finish",),
        canonical_entity_ids=("room-a",),
    )
    authority = CommercialMeasurementAuthority(
        method="scaled_geometry",
        resolved_scale_id="scale-a",
        scale_status="resolved",
    )

    with pytest.raises(MissingCommercialAuthorityError, match="shadow-only"):
        quantity_evidence_to_takeoff_output_row(
            quantity,
            trace=trace,
            authority=authority,
        )


def test_source_owned_ceiling_becomes_review_required_ai_draft_only() -> None:
    source, context, viewport = _setup(include_scale_bar=True)

    result = build_ceiling_lining_review_promotions(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (CEILING_REVIEW_PROMOTION_RESOLVED,)
    assert len(result.candidates) == 1

    candidate = result.candidates[0]
    promoted = candidate.promoted_quantity
    assert promoted.status == AuthorityStatus.REVIEW_REQUIRED.value
    assert promoted.authority == MeasurementAuthorityType.PDF_SCALED.value
    assert promoted.metadata["shadow_only"] is False
    assert promoted.metadata["commercial_projection_allowed"] is True
    assert promoted.metadata["commercial_review_required"] is True
    assert promoted.metadata["promotion_parent_quantity_id"] == candidate.shadow_quantity_id

    row = dict(candidate.review_row)
    assert row["origin"] == "AI"
    assert row["quantity_status"] == "To review"
    assert row["measurement_method"] == "scaled_geometry"
    assert row["resolved_scale_id"]
    gates = existing_commercial_gate_results(row)
    assert gates["publishability"][0] is False
    assert gates["pricing"][0] is False
    assert gates["jobhub"][0] is False
    assert "explicitly reviewed" in gates["publishability"][1]


def test_existing_estimator_review_transition_unlocks_existing_gates() -> None:
    source, context, viewport = _setup(include_scale_bar=True)
    result = build_ceiling_lining_review_promotions(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )
    row = dict(result.candidates[0].review_row)

    reviewed = prepare_ai_takeoff_editor_save(
        row,
        {
            "quantity_status": "Measured",
            "confidence": "Verified",
        },
    )
    assert reviewed["origin"] == "AI_REVIEWED"

    gates = existing_commercial_gate_results(reviewed)
    assert gates["publishability"] == (True, "PUBLISHABLE")
    assert gates["pricing"] == (True, "PRICING_AUTHORISED")
    assert gates["jobhub"] == (True, "ELIGIBLE")


def test_ratio_text_without_graphic_bar_never_becomes_review_candidate() -> None:
    source, context, viewport = _setup(include_scale_bar=False)

    result = build_ceiling_lining_review_promotions(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (CEILING_REVIEW_PROMOTION_UNAVAILABLE,)
    assert result.candidates == ()
