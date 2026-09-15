"""Live-extractor accuracy audit regressions (Cursor lane).

These tests encode fail-closed expectations from AGENTS.md:
conflicting observations must not become one apparently-valid prediction;
absence of CONFLICT/BLOCKED/AMBIGUOUS when conflicts exist is a defect.

Baseline: origin/main @ b76f084 (cursor/live-extractor-accuracy-audit-v1).
Does not modify production code or benchmark gold.
"""
from __future__ import annotations

from pb_drawing_ocr_evidence_layer import (
    DrawingEvidenceRecord,
    EvidenceMethod,
    EvidenceReconciler,
    EvidenceStatus,
)
from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    merge_extracted_prediction,
    publishable_prediction_quantity,
)
from pb_raster_schedule_extractor import GenericScheduleTableExtractor, ScheduleRow
import pytest


def _native(tag: str, qty: float, *, page: int, dims=None, conf: float = 0.9) -> DrawingEvidenceRecord:
    return DrawingEvidenceRecord(
        tag=tag,
        trade_type="doors",
        description=f"{tag} native",
        quantity=qty,
        unit="NO",
        dimensions=dims,
        source_page=page,
        confidence=conf,
        extraction_method=EvidenceMethod.NATIVE_TEXT.value,
        status=EvidenceStatus.CONFIRMED.value,
        extracted_text=f"{tag} {qty} No.",
        extracted_value=qty,
        raw_evidence_ref=f"native-p{page}",
    )


def test_reconciler_duplicate_native_same_tag_different_qty_must_conflict_or_retain_both() -> None:
    """AUDIT 1+2: {r.tag: r for r in native} last-write-wins before reconcile.

    Level-1 D1=2 and Level-2/page-2 D1=5 are independent observations that share
    a tag key. Fail-closed expectation: CONFLICT (or both retained scoped).
    Current production keeps only the last native record and can CONFIRM it.
    """
    natives = [
        _native("D1", 2.0, page=1, dims=[900.0, 2100.0], conf=0.80),
        _native("D1", 5.0, page=2, dims=[900.0, 2100.0], conf=0.95),
    ]
    # OCR agrees with the survivor of the dict collapse — hides the lost native.
    ocr = [
        DrawingEvidenceRecord(
            tag="D1",
            trade_type="doors",
            description="D1 ocr",
            quantity=5.0,
            unit="NO",
            dimensions=[900.0, 2100.0],
            source_page=2,
            confidence=0.90,
            extraction_method=EvidenceMethod.RASTER_OCR.value,
            status=EvidenceStatus.CONFIRMED.value,
            extracted_text="D1 5 No.",
            extracted_value=5.0,
            raw_evidence_ref="ocr-p2",
        )
    ]

    reconciled = EvidenceReconciler.reconcile(natives, ocr)
    d1 = [r for r in reconciled if r.tag == "D1"]
    assert d1, "D1 disappeared entirely"

    assert len(d1) == 2
    assert all(r.status == EvidenceStatus.CONFLICT_MANUAL_REVIEW.value for r in d1)
    assert {r.source_page for r in d1} == {1, 2}
    assert not any(r.status == EvidenceStatus.CONFIRMED.value for r in d1)


def test_schedule_conflicting_dimensions_must_not_look_like_absence() -> None:
    """AUDIT 5+7: conflicting schedule dims drop the tag entirely.

    Downstream cannot distinguish 'no schedule row' from 'schedule conflict'.
    Fail-closed expectation: an explicit conflict/provisional marker remains.
    """
    extractor = GenericScheduleTableExtractor()
    rows = extractor.deduplicate_schedule_rows(
        [
            ScheduleRow(
                tag="W1",
                trade_type="windows",
                description="Level 1 schedule",
                quantity=4.0,
                unit="NO",
                dimensions=[1200.0, 900.0],
                source_page=10,
                sheet_number="A101",
                confidence=0.92,
                evidence_text="W1 1200x900 4 No.",
            ),
            ScheduleRow(
                tag="W1",
                trade_type="windows",
                description="Level 2 schedule",
                quantity=4.0,
                unit="NO",
                dimensions=[1500.0, 1200.0],
                source_page=40,
                sheet_number="A201",
                confidence=0.95,
                evidence_text="W1 1500x1200 4 No.",
            ),
        ]
    )

    w1_rows = [r for r in rows if r.tag == "W1"]
    assert w1_rows, (
        "Conflict erased to empty: W1 absent after dedupe — looks like 'no windows' "
        "rather than CONFLICT/AMBIGUOUS"
    )
    assert any(
        getattr(r, "is_provisional", False)
        or "conflict" in (r.evidence_text or "").lower()
        or "conflict" in (r.description or "").lower()
        for r in w1_rows
    ), "Surviving W1 row(s) carry no conflict marker"


def test_pred_dict_confidence_overwrite_erases_conflicting_schedule_dims() -> None:
    """AUDIT 1+6: live merge uses tag + confidence only (no dimension conflict check).

    Mirrors pb_planreader_pdf_extractor schedule merge:
    ``if s_row.tag not in pred_dict or s_row.confidence >= pred_dict[s_row.tag].confidence``.
    """
    pred_dict: dict[str, ExtractedPrediction] = {
        "W1": ExtractedPrediction(
            tag="W1",
            trade_type="windows",
            description="From plan callout",
            quantity=4.0,
            unit="NO",
            confidence=0.80,
            source_page=1,
            dimensions=[1200.0, 900.0],
            metadata={"derivation": "plan_callout"},
        )
    }
    challenger = ScheduleRow(
        tag="W1",
        trade_type="windows",
        description="From schedule (different size)",
        quantity=4.0,
        unit="NO",
        dimensions=[1800.0, 1200.0],
        source_page=12,
        confidence=0.95,
        evidence_text="W1 1800x1200",
    )

    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag=challenger.tag,
            trade_type=challenger.trade_type,
            description=challenger.description,
            quantity=challenger.quantity,
            unit=challenger.unit,
            confidence=challenger.confidence,
            source_page=challenger.source_page,
            dimensions=challenger.dimensions,
        ),
        merge_source="schedule_row",
    )

    winner = pred_dict["W1"]
    assert winner.quantity is None
    assert extracted_prediction_publication_blocked(winner)
    assert publishable_prediction_quantity(winner) is None
    assert winner.metadata.get("reconciliation_status") == "conflict_manual_review"
    scoped = winner.metadata.get("scoped_claims") or []
    assert len(scoped) == 2
