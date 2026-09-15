"""P0 adversarial regressions: reconciler + pred_dict conflict gate."""
from __future__ import annotations

import random

from pb_drawing_ocr_evidence_layer import (
    DrawingEvidenceRecord,
    EvidenceMethod,
    EvidenceReconciler,
    EvidenceStatus,
)
from pb_planreader_pdf_extractor import ExtractedPrediction, merge_extracted_prediction


def _native(
    tag: str,
    qty: float,
    *,
    page: int,
    dims: list[float] | None = None,
    conf: float = 0.9,
) -> DrawingEvidenceRecord:
    return DrawingEvidenceRecord(
        tag=tag,
        trade_type="doors",
        description=f"{tag} native p{page}",
        quantity=qty,
        unit="NO",
        dimensions=dims,
        source_page=page,
        confidence=conf,
        extraction_method=EvidenceMethod.NATIVE_TEXT.value,
        status=EvidenceStatus.CONFIRMED.value,
        extracted_text=f"{tag} {qty} No.",
        extracted_value=qty,
        raw_evidence_ref=f"native-p{page}-{tag}",
    )


def _statuses(records: list[DrawingEvidenceRecord], tag: str) -> list[str]:
    return [r.status for r in records if r.tag == tag]


def _confirmed(records: list[DrawingEvidenceRecord], tag: str) -> list[DrawingEvidenceRecord]:
    return [
        r
        for r in records
        if r.tag == tag and r.status == EvidenceStatus.CONFIRMED.value
    ]


def test_a1_same_tag_conflicting_dimensions_retains_claims_and_blocks_confirm() -> None:
    natives = [
        _native("D01", 1.0, page=1, dims=[820.0, 2040.0]),
        _native("D01", 1.0, page=1, dims=[920.0, 2040.0]),
    ]
    out = EvidenceReconciler.reconcile(natives, [])
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 2
    assert all(r.status == EvidenceStatus.CONFLICT_MANUAL_REVIEW.value for r in d01)
    assert {tuple(r.dimensions or []) for r in d01} == {(820.0, 2040.0), (920.0, 2040.0)}
    assert _confirmed(out, "D01") == []


def test_a2_same_tag_same_dimensions_same_page_dedupes_without_conflict() -> None:
    natives = [
        _native("D01", 2.0, page=3, dims=[900.0, 2100.0], conf=0.70),
        _native("D01", 2.0, page=3, dims=[900.0, 2100.0], conf=0.95),
    ]
    out = EvidenceReconciler.reconcile(natives, [])
    assert len([r for r in out if r.tag == "D01"]) == 1
    assert out[0].status == EvidenceStatus.CONFIRMED.value
    assert out[0].quantity == 2.0


def test_a3_same_tag_across_pages_not_collapsed() -> None:
    natives = [
        _native("D01", 1.0, page=1, dims=[900.0, 2100.0]),
        _native("D01", 1.0, page=2, dims=[900.0, 2100.0]),
    ]
    out = EvidenceReconciler.reconcile(natives, [])
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 2
    assert {r.source_page for r in d01} == {1, 2}
    assert all(r.status == EvidenceStatus.CONFLICT_MANUAL_REVIEW.value for r in d01)
    assert _confirmed(out, "D01") == []


def test_a4_input_order_permutation_is_invariant() -> None:
    natives = [
        _native("D01", 2.0, page=1, dims=[900.0, 2100.0]),
        _native("D01", 5.0, page=2, dims=[900.0, 2100.0]),
    ]
    forward = EvidenceReconciler.reconcile(natives, [])
    backward = EvidenceReconciler.reconcile(list(reversed(natives)), [])
    shuffled = list(natives)
    random.Random(0).shuffle(shuffled)
    permuted = EvidenceReconciler.reconcile(shuffled, [])

    def _signature(rows: list[DrawingEvidenceRecord]) -> tuple:
        d01 = sorted(
            [
                (
                    r.source_page,
                    r.quantity,
                    tuple(r.dimensions or ()),
                    r.status,
                )
                for r in rows
                if r.tag == "D01"
            ]
        )
        return tuple(d01)

    assert _signature(forward) == _signature(backward) == _signature(permuted)


def test_a5_adding_conflicting_record_never_strengthens_authority() -> None:
    clean = [_native("D01", 1.0, page=1, dims=[900.0, 2100.0], conf=0.90)]
    before = EvidenceReconciler.reconcile(clean, [])
    assert _confirmed(before, "D01")

    after = EvidenceReconciler.reconcile(
        clean
        + [_native("D01", 3.0, page=2, dims=[900.0, 2100.0], conf=0.99)],
        [],
    )
    assert _confirmed(after, "D01") == []
    assert EvidenceStatus.CONFLICT_MANUAL_REVIEW.value in _statuses(after, "D01")


def test_pred_dict_merge_blocks_conflicting_dimensions() -> None:
    pred_dict: dict[str, ExtractedPrediction] = {
        "W1": ExtractedPrediction(
            tag="W1",
            trade_type="windows",
            description="plan callout",
            quantity=4.0,
            unit="NO",
            confidence=0.80,
            source_page=1,
            dimensions=[1200.0, 900.0],
            metadata={"derivation": "plan_callout"},
        )
    }
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="W1",
            trade_type="windows",
            description="schedule row",
            quantity=4.0,
            unit="NO",
            confidence=0.95,
            source_page=12,
            dimensions=[1800.0, 1200.0],
        ),
        merge_source="schedule_row",
    )
    winner = pred_dict["W1"]
    assert winner.dimensions == [1200.0, 900.0]
    assert winner.metadata.get("reconciliation_status") == "conflict_manual_review"
    assert winner.confidence == 0.0
