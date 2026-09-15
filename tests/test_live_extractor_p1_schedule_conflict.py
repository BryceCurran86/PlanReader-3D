"""P1 schedule-conflict preservation regressions."""
from __future__ import annotations

from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    merge_extracted_prediction,
)
from pb_raster_schedule_extractor import GenericScheduleTableExtractor, ScheduleRow


def _schedule_row(
    *,
    tag: str,
    dims: list[float],
    page: int,
    description: str,
    evidence_text: str,
    confidence: float = 0.92,
) -> ScheduleRow:
    return ScheduleRow(
        tag=tag,
        trade_type="doors",
        description=description,
        quantity=1.0,
        unit="NO",
        dimensions=dims,
        source_page=page,
        confidence=confidence,
        evidence_text=evidence_text,
    )


def test_schedule_dimension_conflict_retained_not_erased() -> None:
    extractor = GenericScheduleTableExtractor()
    rows = extractor.deduplicate_schedule_rows(
        [
            _schedule_row(
                tag="D01",
                dims=[820.0, 2040.0],
                page=10,
                description="Schedule A",
                evidence_text="D01 820x2040 schedule A",
            ),
            _schedule_row(
                tag="D01",
                dims=[920.0, 2040.0],
                page=40,
                description="Schedule B",
                evidence_text="D01 920x2040 schedule B",
            ),
        ]
    )
    d1 = [r for r in rows if r.tag == "D1"]
    assert d1, "D1 must remain represented after schedule conflict"
    assert all("schedule conflict" in r.description.lower() for r in d1)
    assert all("schedule_conflict" in r.evidence_text.lower() for r in d1)
    assert {tuple(r.dimensions or ()) for r in d1} == {(820.0, 2040.0), (920.0, 2040.0)}


def test_schedule_conflict_merge_blocks_publication() -> None:
    extractor = GenericScheduleTableExtractor()
    rows = extractor.deduplicate_schedule_rows(
        [
            _schedule_row(
                tag="D01",
                dims=[820.0, 2040.0],
                page=10,
                description="Schedule A",
                evidence_text="D01 820x2040 schedule A",
            ),
            _schedule_row(
                tag="D01",
                dims=[920.0, 2040.0],
                page=40,
                description="Schedule B",
                evidence_text="D01 920x2040 schedule B",
            ),
        ]
    )
    pred_dict: dict[str, ExtractedPrediction] = {}
    for row in rows:
        if row.is_provisional and "schedule_conflict" in (row.evidence_text or "").lower():
            merge_extracted_prediction(
                pred_dict,
                ExtractedPrediction(
                    tag=row.tag,
                    trade_type=row.trade_type,
                    description=row.description,
                    quantity=None,
                    unit=row.unit,
                    confidence=0.0,
                    source_page=row.source_page,
                    dimensions=row.dimensions,
                    metadata={
                        "publication_blocked": True,
                        "reconciliation_status": "conflict_manual_review",
                        "raw_evidence_ref": row.evidence_text,
                    },
                ),
                merge_source="schedule_conflict_row",
            )
    assert "D1" in pred_dict
    assert extracted_prediction_publication_blocked(pred_dict["D1"])


def test_plan_schedule_conflict_retained_reverse_order() -> None:
    plan = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="plan callout",
        quantity=1.0,
        unit="NO",
        confidence=0.80,
        source_page=1,
        dimensions=[920.0, 2040.0],
    )
    schedule = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="schedule row",
        quantity=1.0,
        unit="NO",
        confidence=0.95,
        source_page=12,
        dimensions=[820.0, 2040.0],
    )

    forward: dict[str, ExtractedPrediction] = {}
    merge_extracted_prediction(forward, plan, merge_source="plan_callout")
    merge_extracted_prediction(forward, schedule, merge_source="schedule_row")

    backward: dict[str, ExtractedPrediction] = {}
    merge_extracted_prediction(backward, schedule, merge_source="schedule_row")
    merge_extracted_prediction(backward, plan, merge_source="plan_callout")

    assert forward["D01"].metadata.get("reconciliation_status") == "conflict_manual_review"
    assert backward["D01"].metadata.get("reconciliation_status") == "conflict_manual_review"
    assert forward["D01"].quantity is None
    assert backward["D01"].quantity is None
