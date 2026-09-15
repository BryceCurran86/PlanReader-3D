"""P0 adversarial regressions: reconciler + pred_dict conflict gate."""
from __future__ import annotations

import random

from pb_drawing_ocr_evidence_layer import (
    DrawingEvidenceRecord,
    EvidenceMethod,
    EvidenceReconciler,
    EvidenceStatus,
)
from pb_opening_deduction_pipeline import GenericOpeningDeductionPipeline, OpeningInstance, WallInstance
from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    merge_extracted_prediction,
    publishable_prediction_quantity,
)


def _native(
    tag: str,
    qty: float,
    *,
    page: int,
    dims: list[float] | None = None,
    conf: float = 0.9,
    raw_evidence_ref: str | None = None,
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
        raw_evidence_ref=raw_evidence_ref or f"native-p{page}-{tag}",
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


def test_a2_same_tag_same_dimensions_same_page_distinct_instances_stay_ambiguous() -> None:
    """Two physically distinct same-page D01 with identical dims must not collapse."""
    natives = [
        _native(
            "D01",
            2.0,
            page=3,
            dims=[900.0, 2100.0],
            conf=0.70,
            raw_evidence_ref="native-p3-D01-instance-a",
        ),
        _native(
            "D01",
            2.0,
            page=3,
            dims=[900.0, 2100.0],
            conf=0.95,
            raw_evidence_ref="native-p3-D01-instance-b",
        ),
    ]
    out = EvidenceReconciler.reconcile(natives, [])
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 2
    assert all(r.status == EvidenceStatus.UNRESOLVED.value for r in d01)
    assert {r.raw_evidence_ref for r in d01} == {
        "native-p3-D01-instance-a",
        "native-p3-D01-instance-b",
    }
    assert _confirmed(out, "D01") == []


def test_a2b_proven_same_exact_duplicate_observation_collapses() -> None:
    """PROVEN_SAME only when dedupe key is identical (incl. raw_evidence_ref)."""
    base = _native("D01", 2.0, page=3, dims=[900.0, 2100.0], conf=0.70)
    duplicate = DrawingEvidenceRecord(
        tag=base.tag,
        trade_type=base.trade_type,
        description=base.description,
        quantity=base.quantity,
        unit=base.unit,
        dimensions=base.dimensions,
        source_page=base.source_page,
        confidence=0.95,
        extraction_method=base.extraction_method,
        status=base.status,
        extracted_text=base.extracted_text,
        extracted_value=base.extracted_value,
        raw_evidence_ref=base.raw_evidence_ref,
    )
    out = EvidenceReconciler.reconcile([base, duplicate], [])
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 1
    assert d01[0].status == EvidenceStatus.CONFIRMED.value
    assert d01[0].quantity == 2.0


def test_a3_same_tag_across_pages_not_collapsed_or_marked_conflict() -> None:
    """Different pages prevent unsafe merge but are not automatic contradiction."""
    natives = [
        _native("D01", 1.0, page=1, dims=[900.0, 2100.0]),
        _native("D01", 1.0, page=2, dims=[900.0, 2100.0]),
    ]
    out = EvidenceReconciler.reconcile(natives, [])
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 2
    assert {r.source_page for r in d01} == {1, 2}
    assert all(r.status == EvidenceStatus.UNRESOLVED.value for r in d01)
    assert EvidenceStatus.CONFLICT_MANUAL_REVIEW.value not in _statuses(out, "D01")
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


def test_a5_adding_conflicting_quantity_never_strengthens_authority() -> None:
    clean = [_native("D01", 1.0, page=1, dims=[900.0, 2100.0], conf=0.90)]
    before = EvidenceReconciler.reconcile(clean, [])
    assert _confirmed(before, "D01")

    after = EvidenceReconciler.reconcile(
        clean
        + [_native("D01", 3.0, page=2, dims=[900.0, 2100.0], conf=0.99)],
        [],
    )
    assert _confirmed(after, "D01") == []
    assert all(
        r.status == EvidenceStatus.CONFLICT_MANUAL_REVIEW.value
        for r in after
        if r.tag == "D01"
    )


def test_a6_cross_page_compatible_claims_stay_ambiguous_not_conflict() -> None:
    """Level 1 D01 and Level 2 D01 with same dims are scope-ambiguous, not contradictory."""
    out = EvidenceReconciler.reconcile(
        [
            _native("D01", 1.0, page=1, dims=[900.0, 2100.0]),
            _native("D01", 1.0, page=2, dims=[900.0, 2100.0]),
        ],
        [],
    )
    d01 = [r for r in out if r.tag == "D01"]
    assert len(d01) == 2
    assert all(r.status == EvidenceStatus.UNRESOLVED.value for r in d01)
    assert _confirmed(out, "D01") == []


def test_a7_ocr_agreeing_with_one_conflicting_native_cannot_launder_conflict() -> None:
    natives = [
        _native("D01", 1.0, page=1, dims=[820.0, 2040.0]),
        _native("D01", 1.0, page=1, dims=[920.0, 2040.0]),
    ]
    ocr = [
        DrawingEvidenceRecord(
            tag="D01",
            trade_type="doors",
            description="D01 ocr agrees with 920",
            quantity=1.0,
            unit="NO",
            dimensions=[920.0, 2040.0],
            source_page=1,
            confidence=0.99,
            extraction_method=EvidenceMethod.RASTER_OCR.value,
            status=EvidenceStatus.CONFIRMED.value,
            extracted_text="D01 920x2040",
            extracted_value=1.0,
            raw_evidence_ref="ocr-p1-d01-920",
        )
    ]
    out = EvidenceReconciler.reconcile(natives, ocr)
    assert _confirmed(out, "D01") == []
    assert all(
        r.status == EvidenceStatus.CONFLICT_MANUAL_REVIEW.value
        for r in out
        if r.tag == "D01"
    )


def test_a8_conflicted_pred_dict_quantity_not_publishable_even_if_diagnostic_retained() -> None:
    pred_dict: dict[str, ExtractedPrediction] = {
        "D01": ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="plan callout",
            quantity=1.0,
            unit="NO",
            confidence=0.80,
            source_page=1,
            dimensions=[820.0, 2040.0],
            metadata={"derivation": "plan_callout"},
        )
    }
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="schedule row",
            quantity=1.0,
            unit="NO",
            confidence=0.95,
            source_page=12,
            dimensions=[920.0, 2040.0],
        ),
        merge_source="schedule_row",
    )
    blocked = pred_dict["D01"]
    assert blocked.quantity is None
    assert extracted_prediction_publication_blocked(blocked)
    assert publishable_prediction_quantity(blocked) is None
    scoped = blocked.metadata.get("scoped_claims") or []
    assert len(scoped) == 2
    assert {tuple(c.get("dimensions") or ()) for c in scoped} == {
        (820.0, 2040.0),
        (920.0, 2040.0),
    }
    # confidence=0.0 alone must not be treated as the publication gate.
    only_conf_zero = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="looks blocked but is not",
        quantity=4.0,
        unit="NO",
        confidence=0.0,
        source_page=1,
        dimensions=[920.0, 2040.0],
    )
    assert not extracted_prediction_publication_blocked(only_conf_zero)
    assert publishable_prediction_quantity(only_conf_zero) == 4.0


def test_a9_conflicted_opening_not_consumed_by_deduction_pipeline() -> None:
    pred = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="blocked conflict",
        quantity=None,
        unit="NO",
        confidence=0.0,
        source_page=1,
        dimensions=[920.0, 2040.0],
        metadata={
            "publication_blocked": True,
            "reconciliation_status": "conflict_manual_review",
            "scoped_claims": [
                {"dimensions": [820.0, 2040.0]},
                {"dimensions": [920.0, 2040.0]},
            ],
        },
    )
    assert extracted_prediction_publication_blocked(pred)
    wall = WallInstance(
        wall_id="perimeter_walling",
        length_m=20.0,
        height_m=2.7,
        gross_area_m2=54.0,
    )
    # Mirror live extractor gate: blocked predictions must not become openings.
    if extracted_prediction_publication_blocked(pred):
        openings: list[OpeningInstance] = []
    else:
        openings = [
            OpeningInstance(
                opening_id="D01",
                trade_type="doors",
                width_m=0.92,
                height_m=2.04,
                quantity=1.0,
                bound_wall_id="perimeter_walling",
            )
        ]
    pipeline = GenericOpeningDeductionPipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], openings)
    assert results["perimeter_walling"].net_area_m2 == wall.gross_area_m2


def test_a10_reverse_input_order_same_conflict_result() -> None:
    plan = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="plan",
        quantity=1.0,
        unit="NO",
        confidence=0.80,
        source_page=1,
        dimensions=[920.0, 2040.0],
    )
    schedule = ExtractedPrediction(
        tag="D01",
        trade_type="doors",
        description="schedule",
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


def test_a11_follow_on_agreeing_claim_does_not_resolve_conflict() -> None:
    pred_dict: dict[str, ExtractedPrediction] = {}
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="schedule 820",
            quantity=1.0,
            unit="NO",
            confidence=0.80,
            source_page=10,
            dimensions=[820.0, 2040.0],
        ),
        merge_source="schedule_row",
    )
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="plan 920",
            quantity=1.0,
            unit="NO",
            confidence=0.95,
            source_page=1,
            dimensions=[920.0, 2040.0],
        ),
        merge_source="plan_callout",
    )
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="another 920 claim",
            quantity=1.0,
            unit="NO",
            confidence=0.99,
            source_page=2,
            dimensions=[920.0, 2040.0],
        ),
        merge_source="plan_callout",
    )
    blocked = pred_dict["D01"]
    assert blocked.metadata.get("reconciliation_status") == "conflict_manual_review"
    assert blocked.quantity is None
    assert len(blocked.metadata.get("scoped_claims") or []) == 3


def test_a12_scope_collision_across_pages_blocks_without_conflict_label() -> None:
    pred_dict: dict[str, ExtractedPrediction] = {}
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="Level 1",
            quantity=1.0,
            unit="NO",
            confidence=0.80,
            source_page=1,
            dimensions=[900.0, 2100.0],
        ),
        merge_source="plan_callout",
    )
    merge_extracted_prediction(
        pred_dict,
        ExtractedPrediction(
            tag="D01",
            trade_type="doors",
            description="Level 2",
            quantity=1.0,
            unit="NO",
            confidence=0.95,
            source_page=2,
            dimensions=[900.0, 2100.0],
        ),
        merge_source="plan_callout",
    )
    blocked = pred_dict["D01"]
    assert blocked.metadata.get("reconciliation_status") == "ambiguous_unresolved"
    assert blocked.quantity is None
    assert len(blocked.metadata.get("scoped_claims") or []) == 2
