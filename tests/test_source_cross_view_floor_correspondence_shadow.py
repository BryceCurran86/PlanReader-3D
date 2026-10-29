"""Synthetic tests for pb_source_cross_view_floor_correspondence_shadow.

Verifies exact rigid geometric registration, dual-sheet wall-boundedness proof,
mark containment and typed negative/ambiguity rejection. Pure synthetic geometry:
zero PDF or benchmark gold consumed.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import math
import random
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_cross_view_floor_correspondence_shadow import (
    SourceCrossViewFloorCorrespondenceProducer,
    SourceCrossViewFloorCorrespondenceSelector,
    BOX_NOT_WALL_BOUNDED,
    WALL_EVIDENCE_DIFFERS,
    COMPETING_FINISH_CODES_IN_BOX,
    MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX,
    NO_FINISH_MARK_IN_BOX,
    BOX_OWNED_BY_OTHER_FINISH_CODE,
    MARK_TOO_CLOSE_TO_BOX_SIDE,
    MARK_IN_UNREGISTERED_REGION,
    SOURCE_FINISH_MARK_IDENTITY_INVALID,
    SOURCE_MEASURED_FLOOR_BOX_INVALID,
    SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID,
    OVERLAPPING_MEASURED_BOXES,
    _overlapping_measured_box_flags,
    DUPLICATE_PHYSICAL_FLOOR_IDENTITY,
    MISSING_PHYSICAL_FLOOR_IDENTITY,
    REGISTRATION_NOT_UNIQUE,
    REGISTRATION_TRANSLATION_ALIAS,
    STANDING_AUTHORITY_BLOCKERS,
    build_lines,
    rank_registrations,
    box_correspondence,
    side_evidence,
    classify_floor,
    merge_intervals,
)


def seg(x1: float, y1: float, x2: float, y2: float) -> dict[str, float]:
    return {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}


def room(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    t: float = 5.28,
    gaps: tuple = (),
) -> list[dict[str, float]]:
    sides = {
        "x0": [(x0, y0, x0, y1), (x0 - t, y0 - t, x0 - t, y1 + t)],
        "x1": [(x1, y0, x1, y1), (x1 + t, y0 - t, x1 + t, y1 + t)],
        "y0": [(x0, y0, x1, y0), (x0 - t, y0 - t, x1 + t, y0 - t)],
        "y1": [(x0, y1, x1, y1), (x0 - t, y1 + t, x1 + t, y1 + t)],
    }
    out = []
    for name, pairs in sides.items():
        for a, b, c, e in pairs:
            segs = [(a, b, c, e)]
            for gname, lo, hi in gaps:
                if gname != name:
                    continue
                nxt = []
                for sa, sb, sc, se in segs:
                    if sa == sc:
                        pieces = [(sb, min(se, lo)), (max(sb, hi), se)]
                        nxt += [(sa, p, sc, q) for p, q in pieces if q > p]
                    else:
                        pieces = [(sa, min(sc, lo)), (max(sa, hi), sc)]
                        nxt += [(p, sb, q, se) for p, q in pieces if q > p]
                segs = nxt
            out += [seg(*s) for s in segs]
    return out


def moved(segs: list[dict[str, float]], dx: float, dy: float) -> list[dict[str, float]]:
    return [
        seg(s["x1"] + dx, s["y1"] + dy, s["x2"] + dx, s["y2"] + dy)
        for s in segs
    ]


PLAN = (
    room(173.04, 1382.72, 316.80, 1585.04, gaps=(("y0", 230.0, 280.0),))
    + room(340.5, 1390.0, 560.2, 1600.0)
    + room(600.0, 1100.0, 733.0, 1301.0)
    + room(210.0, 700.0, 330.0, 951.0)
)
TARGET_SHEET = PLAN + [seg(60, 60, 60, 400), seg(95, 60, 95, 400)]
TRUE_T = (-78.0, 0.0)


def support_sheet() -> list[dict[str, float]]:
    extras = [
        seg(1300, 100, 1300, 900),
        seg(1340, 100, 1340, 900),
        seg(1300, 100, 1340, 100),
    ]
    return moved(PLAN, 78.0, 0.0) + extras


def sample_selector() -> SourceCrossViewFloorCorrespondenceSelector:
    return SourceCrossViewFloorCorrespondenceSelector(
        document_id="doc-test-1",
        revision_id="rev-test-1",
        source_sha256="a" * 64,
        snapshot_id="snap-test-1",
        support_page_id="11",
        target_page_id="7",
        material_code="FT3",
    )


# ==============================================================================
# Positive Tests
# ==============================================================================

def test_producer_initialization():
    prod = SourceCrossViewFloorCorrespondenceProducer()
    assert prod._source is None

    with pytest.raises(TypeError, match="SourceVisibilityProducer"):
        SourceCrossViewFloorCorrespondenceProducer(object())  # type: ignore


def test_positive_rigid_registration_and_candidate_floor():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
            "other_labelled_boxes_overlapping": 0,
        }
    ]
    marks = [
        {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert result.winning_registration is not None
    assert result.winning_registration["orientation"] == "identity"
    assert result.winning_registration["scale"] == 1.0
    assert result.winning_registration["dx"] == TRUE_T[0]
    assert result.winning_registration["dy"] == TRUE_T[1]

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CANDIDATE
    assert rec.canonical_floor_id == "canonical-floor-office"
    assert rec.physical_room_id == "physical-room-office"
    assert rec.wall_bounded_on_both_sheets is True
    assert rec.wall_evidence_identical_on_both_sheets is True
    assert rec.side_kinds["y0"] == "with_openings"
    assert rec.side_kinds["x0"] == "full"
    assert rec.side_kinds["x1"] == "full"
    assert rec.side_kinds["y1"] == "full"
    assert rec.finish_codes_in_box == {"FT3": 1}
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False
    assert rec.authority_blockers == STANDING_AUTHORITY_BLOCKERS


# ==============================================================================
# Negative & Ambiguity Tests
# ==============================================================================

def test_negative_open_plan_box_abstains():
    # Box without surrounding walls (grid only)
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    open_plan_segs = [
        seg(0, 0, 400, 0),
        seg(0, 100, 400, 100),
        seg(0, 0, 0, 400),
        seg(100, 0, 100, 400),
    ]

    measured_boxes = [
        {
            "dimension_box_pdf_pts": (100.0, 100.0, 300.0, 300.0),
            "canonical_floor_id": "canonical-floor-open",
            "physical_room_id": "physical-room-open",
            "source_room_face_record_id": "face-open",
        }
    ]
    marks = [
        {"x": 150.0, "y": 150.0, "code": "FT3", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=open_plan_segs,
        target_segments=open_plan_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert BOX_NOT_WALL_BOUNDED in rec.reason_codes
    assert rec.wall_bounded_on_both_sheets is False


def test_negative_competing_finish_codes_conflict():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }
    ]
    # Two competing finish marks inside the same box
    marks = [
        {"x": 300.0, "y": 1420.0, "code": "FT3", "registered_region": True},
        {"x": 350.0, "y": 1420.0, "code": "FT2", "registered_region": True},
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FINISH_CODES_IN_BOX in rec.reason_codes
    assert rec.finish_codes_in_box == {"FT3": 1, "FT2": 1}


def test_negative_box_owned_by_other_finish_code_abstains():
    selector = sample_selector()  # queried code is FT3
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-coldroom",
            "physical_room_id": "physical-room-coldroom",
            "source_room_face_record_id": "face-coldroom",
        }
    ]
    # Mark is EPX, not FT3
    marks = [
        {"x": 300.0, "y": 1420.0, "code": "EPX", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert BOX_OWNED_BY_OTHER_FINISH_CODE in rec.reason_codes


def test_negative_no_mark_in_box_abstains():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }
    ]
    # No marks in box
    marks = [
        {"x": 100.0, "y": 100.0, "code": "FT3", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert NO_FINISH_MARK_IN_BOX in rec.reason_codes


def test_negative_mark_too_close_to_edge_abstains():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }
    ]
    # Mark at margin 1.0 pt from box side (threshold is 5.0 pt)
    marks = [
        {"x": 252.04, "y": 1450.0, "code": "FT3", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert MARK_TOO_CLOSE_TO_BOX_SIDE in rec.reason_codes


def test_negative_overlapping_measured_boxes_abstains():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()

    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    box_support = (251.04, 1382.72, 394.80, 1585.04)
    measured_boxes = [
        {
            "dimension_box_pdf_pts": box_support,
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
            "other_labelled_boxes_overlapping": 1,
        }
    ]
    marks = [
        {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        support_segments=sup_segs,
        target_segments=tgt_segs,
        measured_boxes=measured_boxes,
        marks=marks,
    )

    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert OVERLAPPING_MEASURED_BOXES in rec.reason_codes


# ==============================================================================
# Metamorphic & Invariance Tests
# ==============================================================================

@pytest.mark.parametrize("shift_x, shift_y", [(0.0, 0.0), (45.0, -120.0), (-300.0, 500.0)])
def test_translation_metamorphic_invariance(shift_x: float, shift_y: float):
    src_segs = moved(support_sheet(), shift_x, shift_y)
    tgt_segs = TARGET_SHEET

    lines_src = build_lines(src_segs)
    lines_tgt = build_lines(tgt_segs)

    ranked = rank_registrations(lines_src, lines_tgt)
    assert ranked
    top = ranked[0]
    assert top["orientation"] == "identity"
    assert top["scale"] == 1.0
    assert top["dx"] == pytest.approx(TRUE_T[0] - shift_x, abs=0.1)
    assert top["dy"] == pytest.approx(TRUE_T[1] - shift_y, abs=0.1)


def test_input_segment_order_invariance():
    sup_segs = support_sheet()
    tgt_segs = TARGET_SHEET

    lines1 = build_lines(sup_segs)
    shuffled = list(sup_segs)
    shuffled.reverse()
    lines2 = build_lines(shuffled)

    assert lines1 == lines2


def test_selector_validation():
    with pytest.raises(ValueError, match="material_code"):
        SourceCrossViewFloorCorrespondenceSelector(
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            support_page_id="11",
            target_page_id="7",
            material_code="",
        )


# GPT2: the finish-code text is not a physical source-mark identity.
# A valid same-code mark must be unique, explicitly registered, and inside
# the original measured box with a finite source margin before CANDIDATE.
def _fully_supported_correspondence():
    return {
        "wall_bounded_on_both_sheets": True,
        "wall_evidence_identical_on_both_sheets": True,
    }


def _classify_source_marks(marks):
    return classify_floor(
        _fully_supported_correspondence(),
        registration_unique=True,
        marks_inside=marks,
        other_labelled_boxes_overlapping=0,
        material_code="FT3",
    )


@pytest.mark.parametrize("registration", [1, "true", "false", None, 0, []])
def test_nonboolean_unique_registration_receipt_never_mints_candidate(registration):
    result = classify_floor(
        _fully_supported_correspondence(),
        registration_unique=registration,
        marks_inside=[{"code": "FT3", "margin_pt": 15.0,
                       "registered_region": True}],
        other_labelled_boxes_overlapping=0,
        material_code="FT3",
    )
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_NOT_UNIQUE in result["reason_codes"]
    assert result["authority_blockers"] == ()


@pytest.mark.parametrize("field, value, reason", [
    ("wall_bounded_on_both_sheets", 1, BOX_NOT_WALL_BOUNDED),
    ("wall_bounded_on_both_sheets", "true", BOX_NOT_WALL_BOUNDED),
    ("wall_bounded_on_both_sheets", "false", BOX_NOT_WALL_BOUNDED),
    ("wall_bounded_on_both_sheets", None, BOX_NOT_WALL_BOUNDED),
    ("wall_evidence_identical_on_both_sheets", 1, WALL_EVIDENCE_DIFFERS),
    ("wall_evidence_identical_on_both_sheets", "true", WALL_EVIDENCE_DIFFERS),
    ("wall_evidence_identical_on_both_sheets", "false", WALL_EVIDENCE_DIFFERS),
    ("wall_evidence_identical_on_both_sheets", None, WALL_EVIDENCE_DIFFERS),
])
def test_nonboolean_wall_evidence_receipt_never_mints_candidate(field, value, reason):
    correspondence = _fully_supported_correspondence()
    correspondence[field] = value
    result = classify_floor(
        correspondence,
        registration_unique=True,
        marks_inside=[{"code": "FT3", "margin_pt": 15.0,
                       "registered_region": True}],
        other_labelled_boxes_overlapping=0,
        material_code="FT3",
    )
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert reason in result["reason_codes"]
    assert result["authority_blockers"] == ()


def test_one_registered_ft3_mark_remains_a_shadow_candidate():
    result = _classify_source_marks([
        {"code": "FT3", "margin_pt": 15.0, "registered_region": True}
    ])
    assert result["status"] is EvidenceResolutionStatus.CANDIDATE
    assert result["authority_blockers"] == STANDING_AUTHORITY_BLOCKERS
    assert result["authenticated_physical_wall_face_equivalence"] is False


@pytest.mark.parametrize("reverse", [False, True])
def test_two_distinct_same_code_ft3_marks_never_choose_one_owner(reverse):
    marks = [
        {"code": "FT3", "margin_pt": 15.0, "registered_region": True},
        {"code": "FT3", "margin_pt": 24.0, "registered_region": True},
    ]
    if reverse:
        marks.reverse()
    result = _classify_source_marks(marks)
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX in result["reason_codes"]
    assert result["finish_codes_in_box"] == {"FT3": 2}
    assert result["authority_blockers"] == ()


def test_distinct_competing_ft2_ft3_marks_still_conflict():
    result = _classify_source_marks([
        {"code": "FT3", "margin_pt": 15.0, "registered_region": True},
        {"code": "FT2", "margin_pt": 20.0, "registered_region": True},
    ])
    assert result["status"] is EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FINISH_CODES_IN_BOX in result["reason_codes"]


@pytest.mark.parametrize("registration", [None, False, "true", 1, 0])
def test_untrusted_registration_is_not_a_source_positive(registration):
    result = _classify_source_marks([
        {"code": "FT3", "margin_pt": 15.0, "registered_region": registration}
    ])
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MARK_IN_UNREGISTERED_REGION in result["reason_codes"]


def test_missing_registration_does_not_default_to_true():
    result = _classify_source_marks([{"code": "FT3", "margin_pt": 15.0}])
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MARK_IN_UNREGISTERED_REGION in result["reason_codes"]


@pytest.mark.parametrize("margin", [None, float("nan"), float("inf"),
                                    -float("inf"), "15.0", True, -1.0,
                                    10 ** 1000])
def test_untrusted_or_nonfinite_mark_margin_abstains(margin):
    result = _classify_source_marks([
        {"code": "FT3", "margin_pt": margin, "registered_region": True}
    ])
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MARK_TOO_CLOSE_TO_BOX_SIDE in result["reason_codes"]


def test_missing_mark_margin_is_not_a_positive_containment_receipt():
    result = _classify_source_marks([
        {"code": "FT3", "registered_region": True}
    ])
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MARK_TOO_CLOSE_TO_BOX_SIDE in result["reason_codes"]


def test_end_to_end_duplicate_ft3_marks_abstain_without_commercial_grant():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[
            {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True},
            {"x": 335.8, "y": 1447.5, "code": "FT3", "registered_region": True},
        ],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX in result.reason_codes
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX in result.records[0].reason_codes
    assert result.records[0].commercial_projection_allowed is False
    assert result.records[0].takeoff_eligible is False


def test_end_to_end_missing_registration_abstains_without_commercial_grant():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3"}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert MARK_IN_UNREGISTERED_REGION in result.reason_codes
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert MARK_IN_UNREGISTERED_REGION in result.records[0].reason_codes
    assert result.records[0].commercial_projection_allowed is False
    assert result.records[0].takeoff_eligible is False


@pytest.mark.parametrize("minimum", [float("nan"), float("inf"),
                                     -1.0, "5.0", True, 10 ** 1000])
def test_invalid_minimum_mark_margin_abstains(minimum):
    result = classify_floor(
        _fully_supported_correspondence(),
        registration_unique=True,
        marks_inside=[{
            "code": "FT3", "margin_pt": 15.0, "registered_region": True
        }],
        other_labelled_boxes_overlapping=0,
        material_code="FT3",
        min_margin_pt=minimum,
    )
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert MARK_TOO_CLOSE_TO_BOX_SIDE in result["reason_codes"]


def test_no_measured_boxes_does_not_advertise_aggregate_floor_candidate():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[],
        marks=[{"x": 327.8, "y": 1437.5,
                "code": "FT3", "registered_region": True}],
    )
    assert result.records == ()
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes
    assert result.winning_registration is not None


def test_competing_codes_propagate_conflict_to_aggregate():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[
            {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True},
            {"x": 335.8, "y": 1447.5, "code": "FT2", "registered_region": True},
        ],
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FINISH_CODES_IN_BOX in result.reason_codes
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.CONFLICT
    assert not result.records[0].commercial_projection_allowed


@pytest.mark.parametrize("reverse", [False, True])
def test_overlapping_measured_floor_boxes_auto_veto_both_finish_owners(reverse):
    # Two aliases for one physical floor must not both claim a single FT3 mark.
    box = (251.04, 1382.72, 394.80, 1585.04)
    measured = [
        {"dimension_box_pdf_pts": box, "canonical_floor_id": "office-a",
         "physical_room_id": "room-a", "source_room_face_record_id": "face-a"},
        {"dimension_box_pdf_pts": box, "canonical_floor_id": "office-b",
         "physical_room_id": "room-b", "source_room_face_record_id": "face-b"},
    ]
    if reverse:
        measured.reverse()
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=measured,
        marks=[{"x": 327.8, "y": 1437.5,
                "code": "FT3", "registered_region": True}],
    )
    assert len(result.records) == 2
    assert len({r.record_id for r in result.records}) == 2
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    for record in result.records:
        assert record.status is EvidenceResolutionStatus.ABSTAINED
        assert OVERLAPPING_MEASURED_BOXES in record.reason_codes
        assert record.finish_codes_in_box == {"FT3": 1}
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False


def test_edge_touching_measured_boxes_do_not_create_false_overlap_veto():
    first = (251.04, 1382.72, 394.80, 1585.04)
    second = (394.80, 1382.72, 538.56, 1585.04)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[
            {"dimension_box_pdf_pts": first, "canonical_floor_id": "office-a",
             "physical_room_id": "room-a", "source_room_face_record_id": "face-a"},
            {"dimension_box_pdf_pts": second, "canonical_floor_id": "office-b",
             "physical_room_id": "room-b", "source_room_face_record_id": "face-b"},
        ],
        marks=[{"x": 327.8, "y": 1437.5,
                "code": "FT3", "registered_region": True}],
    )
    assert len(result.records) == 2
    assert OVERLAPPING_MEASURED_BOXES not in result.records[0].reason_codes
    assert all(not record.takeoff_eligible for record in result.records)


@pytest.mark.parametrize("scale", [0.5, 0.75, 1.25, 2.0])
def test_nonunit_registration_cannot_claim_untransformed_floor_box(monkeypatch, scale):
    # The registration search can return a strong nonunit-scale winner.
    # The existing box_correspondence applies only orientation+translation.
    # Preserve the ranked diagnostic, but never grant floor correspondence.
    import pb_source_cross_view_floor_correspondence_shadow as floor_shadow

    real_rank = floor_shadow.rank_registrations

    def nonunit_winner(*args, **kwargs):
        ranked = real_rank(*args, **kwargs)
        assert ranked and ranked[0]["scale"] == 1.0
        return [{**ranked[0], "scale": scale}]

    monkeypatch.setattr(floor_shadow, "rank_registrations", nonunit_winner)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "office",
            "physical_room_id": "office-room",
            "source_room_face_record_id": "office-face",
        }],
        marks=[{
            "x": 327.8, "y": 1437.5, "code": "FT3",
            "registered_region": True,
        }],
    )
    assert result.winning_registration is not None
    assert result.winning_registration["scale"] == scale
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert floor_shadow.REGISTRATION_SCALE_NOT_APPLIED in result.reason_codes
    assert len(result.records) == 1
    record = result.records[0]
    assert record.registration_scale == scale
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert floor_shadow.REGISTRATION_SCALE_NOT_APPLIED in record.reason_codes
    assert record.takeoff_eligible is False
    assert record.commercial_projection_allowed is False
    assert record.authority_blockers == ()

@pytest.mark.parametrize("alias_kind", ["equal", "near", "nan", "inf", "string", "overflow"])
def test_distinct_translation_alias_cannot_claim_floor_correspondence(
    monkeypatch, alias_kind
):
    # A rival translation under the SAME orientation/scale is not ranked[1].
    import pb_source_cross_view_floor_correspondence_shadow as floor_shadow
    real_rank = floor_shadow.rank_registrations

    def rival_same_transform(*args, **kwargs):
        ranked = real_rank(*args, **kwargs)
        assert ranked and ranked[0]["scale"] == 1.0
        top = ranked[0]["min_support_pt"]
        aliases = {
            "equal": top,
            "near": top / 1.1,
            "nan": float("nan"),
            "inf": float("inf"),
            "string": str(top),
            "overflow": 10 ** 1000,
        }
        return [{**ranked[0], "next_distinct_min_support_pt": aliases[alias_kind]}] + ranked[1:]

    monkeypatch.setattr(floor_shadow, "rank_registrations", rival_same_transform)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "office",
            "physical_room_id": "office-room",
            "source_room_face_record_id": "office-face",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3",
                "registered_region": True}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_TRANSLATION_ALIAS in result.reason_codes
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_TRANSLATION_ALIAS in result.records[0].reason_codes
    assert result.winning_registration is not None
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False


def test_well_separated_same_transform_translation_retains_shadow_candidate(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as floor_shadow
    real_rank = floor_shadow.rank_registrations

    def separated_same_transform(*args, **kwargs):
        ranked = real_rank(*args, **kwargs)
        assert ranked and ranked[0]["scale"] == 1.0
        return [{
            **ranked[0],
            "next_distinct_min_support_pt": ranked[0]["min_support_pt"] / 2.0,
        }] + ranked[1:]

    monkeypatch.setattr(floor_shadow, "rank_registrations", separated_same_transform)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "office",
            "physical_room_id": "office-room",
            "source_room_face_record_id": "office-face",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3",
                "registered_region": True}],
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False

@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_real_target_wall_layout_has_ambiguous_translation(reverse):
    # Two equally supported physical placements exist within one orientation.
    # The second placement is NOT ranked[1] (which ranks orientations/scales).
    repeated_target = TARGET_SHEET + moved(TARGET_SHEET, 800.0, 0.0)
    if reverse:
        repeated_target.reverse()
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=repeated_target,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "office",
            "physical_room_id": "office-room",
            "source_room_face_record_id": "office-face",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3",
                "registered_region": True}],
    )
    winner = result.winning_registration
    assert winner is not None
    assert winner["orientation"] == "identity"
    assert winner["scale"] == 1.0
    assert winner["next_distinct_min_support_pt"] == winner["min_support_pt"]
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_TRANSLATION_ALIAS in result.reason_codes
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_TRANSLATION_ALIAS in result.records[0].reason_codes
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False


# GPT2: stable shadow IDs must not alias different source snapshots or
# different source-face/target correspondence evidence under one document ID.
def _source_lineage_record(*, selector=None, face_id="face-office", target_shift=(0.0, 0.0)):
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=selector or sample_selector(),
        support_segments=support_sheet(),
        target_segments=moved(TARGET_SHEET, *target_shift),
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": face_id,
        }],
        marks=[{
            "x": 327.8, "y": 1437.5, "code": "FT3",
            "registered_region": True,
        }],
    )
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.takeoff_eligible is False
    assert rec.commercial_projection_allowed is False
    return rec


def test_shadow_record_id_separates_source_sha_snapshot_and_face_identity():
    selector = sample_selector()
    base = _source_lineage_record(selector=selector)
    replay = _source_lineage_record(selector=selector)
    changed_sha = _source_lineage_record(selector=replace(selector, source_sha256="b" * 64))
    changed_snapshot = _source_lineage_record(selector=replace(selector, snapshot_id="snap-test-2"))
    changed_face = _source_lineage_record(selector=selector, face_id="face-office-revision")

    assert base.record_id == replay.record_id
    assert len({base.record_id, changed_sha.record_id,
                changed_snapshot.record_id, changed_face.record_id}) == 4
    assert base.canonical_floor_id == changed_sha.canonical_floor_id
    assert base.support_dimension_box_pdf_pts == changed_snapshot.support_dimension_box_pdf_pts
    assert base.physical_room_id == changed_face.physical_room_id


def test_shadow_record_id_separates_distinct_target_sheet_correspondence():
    base = _source_lineage_record()
    moved_target = _source_lineage_record(target_shift=(100.0, -70.0))
    assert base.support_dimension_box_pdf_pts == moved_target.support_dimension_box_pdf_pts
    assert base.target_box_pdf_pts != moved_target.target_box_pdf_pts
    assert base.record_id != moved_target.record_id
    assert moved_target.takeoff_eligible is False
    assert moved_target.commercial_projection_allowed is False


# A source-face/canonical-floor identity is a single physical claim even when
# the corresponding measured boxes do not geometrically overlap.
def _two_separated_floor_boxes():
    return [
        {
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-first",
            "physical_room_id": "physical-room-first",
            "source_room_face_record_id": "source-face-first",
        },
        {
            "dimension_box_pdf_pts": (418.50, 1390.00, 638.20, 1600.00),
            "canonical_floor_id": "canonical-floor-second",
            "physical_room_id": "physical-room-second",
            "source_room_face_record_id": "source-face-second",
        },
    ]


def _two_separated_floor_marks():
    return [
        {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True},
        {"x": 470.0, "y": 1460.0, "code": "FT3", "registered_region": True},
    ]


def _two_floor_result(boxes):
    return SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=boxes,
        marks=_two_separated_floor_marks(),
    )


def test_two_distinct_disjoint_physical_floors_remain_shadow_candidates():
    result = _two_floor_result(_two_separated_floor_boxes())
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 2
    assert all(r.status is EvidenceResolutionStatus.CANDIDATE for r in result.records)
    assert all(not r.takeoff_eligible and not r.commercial_projection_allowed
               for r in result.records)


@pytest.mark.parametrize("field_name", [
    "canonical_floor_id", "physical_room_id", "source_room_face_record_id",
])
@pytest.mark.parametrize("reverse", [False, True])
def test_disjoint_boxes_reusing_one_physical_identity_abstain_without_order_bias(
    field_name, reverse,
):
    boxes = _two_separated_floor_boxes()
    boxes[1][field_name] = boxes[0][field_name]
    if reverse:
        boxes.reverse()
    result = _two_floor_result(boxes)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 2
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in result.records)
    assert all(DUPLICATE_PHYSICAL_FLOOR_IDENTITY in r.reason_codes
               for r in result.records)
    assert DUPLICATE_PHYSICAL_FLOOR_IDENTITY in result.reason_codes
    assert all(not r.takeoff_eligible and not r.commercial_projection_allowed
               for r in result.records)


@pytest.mark.parametrize("field_name", [
    "canonical_floor_id", "physical_room_id", "source_room_face_record_id",
])
def test_missing_physical_identity_abstains_only_affected_floor(field_name):
    boxes = _two_separated_floor_boxes()
    boxes[0].pop(field_name)
    result = _two_floor_result(boxes)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 2
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert MISSING_PHYSICAL_FLOOR_IDENTITY in result.records[0].reason_codes
    assert result.records[1].status is EvidenceResolutionStatus.CANDIDATE
    assert all(not r.takeoff_eligible and not r.commercial_projection_allowed
               for r in result.records)


@pytest.mark.parametrize(
    "side,axis,old_coord,new_coord",
    [
        ("x0", "x", 94.72, 105.28),
        ("x1", "x", 255.28, 244.72),
        ("y0", "y", 94.72, 105.28),
        ("y1", "y", 255.28, 244.72),
    ],
)
def test_wrong_side_second_wall_face_cannot_authenticate_floor(
    side: str, axis: str, old_coord: float, new_coord: float
):
    """Interior parallel strokes cannot serve as the outward wall face."""
    box = (100.0, 100.0, 250.0, 250.0)
    valid = room(*box)
    invalid = copy.deepcopy(valid)
    changed = 0
    for segment in invalid:
        k1, k2 = ("x1", "x2") if axis == "x" else ("y1", "y2")
        if segment[k1] == segment[k2] == old_coord:
            segment[k1] = segment[k2] = new_coord
            changed += 1
    assert changed == 1
    valid_lines = build_lines(valid)
    invalid_lines = build_lines(invalid)
    assert side_evidence(box, valid_lines)[side]["second_face"]
    assert side_evidence(box, invalid_lines)[side]["second_face"] == []

    valid_corr = box_correspondence(
        box, lines_support=valid_lines, lines_target=valid_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    assert valid_corr["wall_bounded_on_both_sheets"] is True
    assert valid_corr["side_kinds"][side] == "full"
    invalid_corr = box_correspondence(
        box, lines_support=invalid_lines, lines_target=invalid_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    assert invalid_corr["side_kinds"][side] == "not_wall"
    assert invalid_corr["wall_bounded_on_both_sheets"] is False
    mark = [{"code": "FT3", "margin_pt": 40.0, "registered_region": True}]
    positive = classify_floor(
        valid_corr, registration_unique=True, marks_inside=mark,
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    negative = classify_floor(
        invalid_corr, registration_unique=True, marks_inside=mark,
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    assert positive["status"] is EvidenceResolutionStatus.CANDIDATE
    assert negative["status"] is EvidenceResolutionStatus.ABSTAINED
    assert BOX_NOT_WALL_BOUNDED in negative["reason_codes"]


# GPT2: a parallel wall stroke is not physical wall equivalence unless the
# complete outward-face thickness and void geometry match on both sheets.
@pytest.mark.parametrize(
    "side,axis,old_coord,new_coord",
    [
        ("x0", "x", 94.72, 92.72),
        ("x1", "x", 255.28, 257.28),
        ("y0", "y", 94.72, 92.72),
        ("y1", "y", 255.28, 257.28),
    ],
)
@pytest.mark.parametrize("translate", [(0.0, 0.0), (700.0, -320.0)])
def test_cross_sheet_different_outward_wall_thickness_abstains(
    side, axis, old_coord, new_coord, translate,
):
    box = (100.0, 100.0, 250.0, 250.0)
    source = room(*box)
    target = copy.deepcopy(source)
    changed = 0
    k1, k2 = ("x1", "x2") if axis == "x" else ("y1", "y2")
    for segment in target:
        if segment[k1] == segment[k2] == old_coord:
            segment[k1] = segment[k2] = new_coord
            changed += 1
    assert changed == 1
    dx, dy = translate
    shifted_box = tuple(v + (dx if i % 2 == 0 else dy)
                        for i, v in enumerate(box))
    source_lines = build_lines(moved(source, dx, dy))
    target_lines = build_lines(moved(target, dx, dy))
    positive = box_correspondence(
        shifted_box, lines_support=source_lines, lines_target=source_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    mismatch = box_correspondence(
        shifted_box, lines_support=source_lines, lines_target=target_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    assert positive["wall_bounded_on_both_sheets"] is True
    assert positive["wall_evidence_identical_on_both_sheets"] is True
    assert mismatch["wall_bounded_on_both_sheets"] is True
    assert mismatch["side_kinds"][side] == "full"
    assert mismatch["sides"][side]["outward_second_faces_match"] is False
    assert mismatch["wall_evidence_identical_on_both_sheets"] is False
    mark = [{"code": "FT3", "margin_pt": 40.0, "registered_region": True}]
    classified = classify_floor(
        mismatch, registration_unique=True, marks_inside=mark,
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    assert classified["status"] is EvidenceResolutionStatus.ABSTAINED
    assert WALL_EVIDENCE_DIFFERS in classified["reason_codes"]
    assert classified["authenticated_physical_wall_face_equivalence"] is False


def _different_outer_face_gap(lo, hi):
    original = room(100.0, 100.0, 250.0, 250.0)
    result = []
    for segment in original:
        if segment["x1"] == segment["x2"] == 94.72:
            result += [
                seg(94.72, segment["y1"], 94.72, lo),
                seg(94.72, hi, 94.72, segment["y2"]),
            ]
        else:
            result.append(segment)
    return result


@pytest.mark.parametrize("reverse", [False, True])
def test_same_second_face_coverage_with_different_void_position_abstains(reverse):
    box = (100.0, 100.0, 250.0, 250.0)
    source = _different_outer_face_gap(130.0, 160.0)
    target = _different_outer_face_gap(170.0, 200.0)
    if reverse:
        source.reverse()
        target.reverse()
    src_lines, tgt_lines = build_lines(source), build_lines(target)
    positive = box_correspondence(
        box, lines_support=src_lines, lines_target=src_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    negative = box_correspondence(
        box, lines_support=src_lines, lines_target=tgt_lines,
        orientation="identity", translation=(0.0, 0.0),
    )
    assert positive["wall_evidence_identical_on_both_sheets"] is True
    assert negative["wall_bounded_on_both_sheets"] is True
    assert negative["sides"]["x0"]["support_sheet"]["second_face"] == (
        negative["sides"]["x0"]["target_sheet"]["second_face"]
    )
    assert negative["sides"]["x0"]["outward_second_faces_match"] is False
    assert negative["wall_evidence_identical_on_both_sheets"] is False
    classified = classify_floor(
        negative, registration_unique=True,
        marks_inside=[{"code": "FT3", "margin_pt": 40.0, "registered_region": True}],
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    assert classified["status"] is EvidenceResolutionStatus.ABSTAINED
    assert WALL_EVIDENCE_DIFFERS in classified["reason_codes"]


# GPT2 original finish marks are source identities, not arbitrary OCR values.
# A single valid code must not borrow a malformed rival's missing lineage.
@pytest.mark.parametrize("bad_mark", [
    None,
    "FT3",
    17,
    {"margin_pt": 15.0, "registered_region": True},
    {"code": None, "margin_pt": 15.0, "registered_region": True},
    {"code": ["FT3"], "margin_pt": 15.0, "registered_region": True},
    {"code": {"glyph": "FT3"}, "margin_pt": 15.0, "registered_region": True},
    {"code": True, "margin_pt": 15.0, "registered_region": True},
    {"code": 3, "margin_pt": 15.0, "registered_region": True},
    {"code": " FT3 ", "margin_pt": 15.0, "registered_region": True},
    {"code": "", "margin_pt": 15.0, "registered_region": True},
])
def test_malformed_original_finish_mark_identity_abstains(bad_mark):
    result = _classify_source_marks([bad_mark])
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result["reason_codes"]
    assert result["authority_blockers"] == ()
    assert result["authenticated_physical_wall_face_equivalence"] is False


def test_valid_finish_mark_cannot_borrow_untyped_rival_as_unique_owner():
    valid = {"code": "FT3", "margin_pt": 15.0, "registered_region": True}
    malformed = {"code": ["FT2"], "margin_pt": 20.0,
                 "registered_region": True}
    for marks in ([valid, malformed], [malformed, valid]):
        result = _classify_source_marks(marks)
        assert result["status"] is EvidenceResolutionStatus.ABSTAINED
        assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result["reason_codes"]
        assert result["finish_codes_in_box"] == {"FT3": 1}
        assert result["authority_blockers"] == ()


@pytest.mark.parametrize("unbounded_or_untyped", [
    None, "FT3", {"code": "FT3"}, 3,
    [{"code": "FT3", "margin_pt": 15.0,
      "registered_region": True}] * 20001,
])
def test_unbounded_or_untyped_original_finish_mark_universe_abstains(
    unbounded_or_untyped,
):
    result = _classify_source_marks(unbounded_or_untyped)
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert result["reason_codes"] == (SOURCE_FINISH_MARK_IDENTITY_INVALID,)
    assert result["finish_codes_in_box"] == {}
    assert result["authority_blockers"] == ()


def test_valid_original_finish_code_still_remains_source_only_candidate():
    result = _classify_source_marks([
        {"code": "FT3", "margin_pt": 15.0, "registered_region": True}
    ])
    assert result["status"] is EvidenceResolutionStatus.CANDIDATE
    assert result["authority_blockers"] == STANDING_AUTHORITY_BLOCKERS
    assert result["authenticated_physical_wall_face_equivalence"] is False


def test_end_to_end_unhashable_original_finish_mark_never_reaches_candidate():
    # Exercise the actual shadow producer, not only classify_floor directly.
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": ["FT3"],
                "registered_region": True}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.records[0].reason_codes
    assert result.records[0].commercial_projection_allowed is False
    assert result.records[0].takeoff_eligible is False


# GPT2: validate the complete original mark universe at the producer boundary,
# before mark['code'] and coordinate conversion can bypass classify_floor.
def _producer_with_original_marks(marks):
    return SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=marks,
    )


@pytest.mark.parametrize("bad_mark", [
    {"x": 335.8, "y": 1447.5, "registered_region": True},
    {"x": 335.8, "y": 1447.5, "code": None, "registered_region": True},
    {"x": 335.8, "y": 1447.5, "code": ["FT2"], "registered_region": True},
    {"x": 335.8, "y": 1447.5, "code": " FT2 ", "registered_region": True},
    {"x": "335.8", "y": 1447.5, "code": "FT2", "registered_region": True},
    {"x": True, "y": 1447.5, "code": "FT2", "registered_region": True},
    {"x": float("nan"), "y": 1447.5, "code": "FT2", "registered_region": True},
    {"x": float("inf"), "y": 1447.5, "code": "FT2", "registered_region": True},
    {"x": 10 ** 1000, "y": 1447.5, "code": "FT2", "registered_region": True},
    {"x": 335.8, "y": float("-inf"), "code": "FT2", "registered_region": True},
    {"x": 335.8, "code": "FT2", "registered_region": True},
    None,
    "FT2",
])
@pytest.mark.parametrize("reverse", [False, True])
def test_producer_malformed_original_mark_never_lends_unique_ft3_owner(
    bad_mark, reverse,
):
    valid = {"x": 327.8, "y": 1437.5, "code": "FT3",
             "registered_region": True}
    marks = [valid, bad_mark]
    if reverse:
        marks.reverse()
    result = _producer_with_original_marks(marks)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.reason_codes
    assert len(result.records) == 1
    record = result.records[0]
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in record.reason_codes
    assert record.finish_codes_in_box == {"FT3": 1}
    assert record.authority_blockers == ()
    assert record.takeoff_eligible is False
    assert record.commercial_projection_allowed is False


@pytest.mark.parametrize("marks", [
    None,
    {"x": 327.8, "y": 1437.5, "code": "FT3"},
    "FT3",
    [{"x": 327.8, "y": 1437.5, "code": "FT3"}] * 20001,
])
def test_producer_untyped_or_unbounded_original_mark_universe_abstains(marks):
    result = _producer_with_original_marks(marks)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_FINISH_MARK_IDENTITY_INVALID,)
    assert result.records == ()


def test_producer_valid_outside_mark_does_not_veto_valid_inside_ft3():
    result = _producer_with_original_marks([
        {"x": 327.8, "y": 1437.5, "code": "FT3",
         "registered_region": True},
        {"x": 10.0, "y": 10.0, "code": "FT2",
         "registered_region": True},
    ])
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].finish_codes_in_box == {"FT3": 1}
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False


def test_producer_competing_valid_codes_still_conflict_with_invalid_rival():
    result = _producer_with_original_marks([
        {"x": 327.8, "y": 1437.5, "code": "FT3",
         "registered_region": True},
        {"x": 335.8, "y": 1447.5, "code": "FT2",
         "registered_region": True},
        {"x": float("nan"), "y": 1447.5, "code": "FT2",
         "registered_region": True},
    ])
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert COMPETING_FINISH_CODES_IN_BOX in result.reason_codes
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.reason_codes
    assert result.records[0].status is EvidenceResolutionStatus.CONFLICT
    assert result.records[0].finish_codes_in_box == {"FT2": 1, "FT3": 1}
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False

# GPT2: the complete original measured-floor box universe must be safe before
# geometry registration. An invalid rival never disappears to make FT3 unique.
@pytest.mark.parametrize("bad_box", [
    None,
    "floor-not-a-source-box",
    {},
    {"dimension_box_pdf_pts": "251,1382,395,1585"},
    {"dimension_box_pdf_pts": (251.04, 1382.72, 394.80)},
    {"dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04, 7.0)},
    {"dimension_box_pdf_pts": (True, 1382.72, 394.80, 1585.04)},
    {"dimension_box_pdf_pts": ("251.04", 1382.72, 394.80, 1585.04)},
    {"dimension_box_pdf_pts": (float("nan"), 1382.72, 394.80, 1585.04)},
    {"dimension_box_pdf_pts": (251.04, float("inf"), 394.80, 1585.04)},
    {"dimension_box_pdf_pts": (251.04, 1382.72, float("-inf"), 1585.04)},
    {"dimension_box_pdf_pts": (10**1000, 1382.72, 394.80, 1585.04)},
    {"dimension_box_pdf_pts": (251.04, 1382.72, 251.04, 1585.04)},
    {"dimension_box_pdf_pts": (394.80, 1382.72, 251.04, 1585.04)},
    {"dimension_box_pdf_pts": (251.04, 1585.04, 394.80, 1382.72)},
])
@pytest.mark.parametrize("reverse", [False, True])
def test_malformed_measured_box_vetoes_surviving_ft3_owner(bad_box, reverse):
    boxes = _two_separated_floor_boxes()
    if reverse:
        boxes.insert(0, bad_box)
    else:
        boxes.append(bad_box)
    result = _two_floor_result(boxes)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_MEASURED_FLOOR_BOX_INVALID in result.reason_codes
    assert len(result.records) == 2  # Retain both valid diagnostic owners.
    assert all(row.status is EvidenceResolutionStatus.ABSTAINED
               for row in result.records)
    assert all(SOURCE_MEASURED_FLOOR_BOX_INVALID in row.reason_codes
               for row in result.records)
    assert all(row.authority_blockers == () for row in result.records)
    assert all(not row.takeoff_eligible and not row.commercial_projection_allowed
               for row in result.records)


@pytest.mark.parametrize("boxes", [
    None,
    "a floor, not a universe",
    {"dimension_box_pdf_pts": (1, 2, 3, 4)},
    [None],
    [{"dimension_box_pdf_pts": (1, 2, 3)}],
    [_two_separated_floor_boxes()[0]] * 20001,
])
def test_untyped_or_unbounded_measured_box_universe_abstains(boxes):
    result = _two_floor_result(boxes)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_MEASURED_FLOOR_BOX_INVALID,)
    assert result.records == ()


def test_complete_valid_measured_boxes_retain_source_only_candidates():
    result = _two_floor_result(_two_separated_floor_boxes())
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 2
    assert all(row.status is EvidenceResolutionStatus.CANDIDATE
               for row in result.records)
    assert all(not row.takeoff_eligible and not row.commercial_projection_allowed
               for row in result.records)


def test_full_measured_box_overlap_index_matches_exhaustive_random_oracle():
    # A positive-area rectangle intersection is symmetric; no first/nearest
    # source owner is selected, and all competing boxes must be vetoed.
    rng = random.Random(20261029)
    for _ in range(80):
        boxes = []
        for _ in range(32):
            x0, y0 = rng.randrange(-30, 30), rng.randrange(-30, 30)
            boxes.append((
                float(x0), float(y0),
                float(x0 + rng.randrange(1, 18)),
                float(y0 + rng.randrange(1, 18)),
            ))
        expected = [False] * len(boxes)
        for i, a in enumerate(boxes):
            for j in range(i + 1, len(boxes)):
                b = boxes[j]
                if (
                    min(a[2], b[2]) > max(a[0], b[0])
                    and min(a[3], b[3]) > max(a[1], b[1])
                ):
                    expected[i] = expected[j] = True
        original = copy.deepcopy(boxes)
        assert _overlapping_measured_box_flags(boxes) == expected
        order = list(range(len(boxes)))
        rng.shuffle(order)
        assert _overlapping_measured_box_flags([boxes[i] for i in order]) == [
            expected[i] for i in order
        ]
        assert boxes == original


def test_full_measured_box_overlap_index_keeps_touching_edges_unmarked():
    boxes = [
        (0.0, 0.0, 2.0, 2.0),
        (2.0, 0.0, 4.0, 2.0),
        (0.0, 2.0, 2.0, 4.0),
        (2.0, 2.0, 4.0, 4.0),
        (5.0, 5.0, 7.0, 7.0),
    ]
    assert _overlapping_measured_box_flags(boxes) == [False] * len(boxes)
    # Both enclosing and enclosed owners must be vetoed, not just the
    # later source record or the one with the smaller area.
    assert _overlapping_measured_box_flags([
        (0.0, 0.0, 100.0, 100.0),
        (10.0, 10.0, 11.0, 11.0),
        (20.0, 20.0, 21.0, 21.0),
        (101.0, 0.0, 102.0, 1.0),
    ]) == [True, True, True, False]


def test_full_measured_box_overlap_index_handles_20000_disjoint_and_dense():
    # Public, source-neutral upper-bound stress: the former pairwise loop
    # performed 199,990,000 checks for each of these 20k-box universes.
    disjoint = [(float(2*i), 0.0, float(2*i+1), 1.0)
                for i in range(20000)]
    dense = [(0.0, 0.0, 10.0, 10.0)] * 20000
    edge_touching = [(float(i), 0.0, float(i+1), 1.0)
                     for i in range(20000)]
    assert not any(_overlapping_measured_box_flags(disjoint))
    assert all(_overlapping_measured_box_flags(dense))
    assert not any(_overlapping_measured_box_flags(edge_touching))


# GPT2: source-room/canonical identities are original evidence, not display text.
# A padded, type-coerced or unprintable source ID must never acquire an
# apparently valid physical-room identity or silently alias another owner.
@pytest.mark.parametrize("field_name", [
    "canonical_floor_id", "physical_room_id", "source_room_face_record_id",
])
@pytest.mark.parametrize("bad_identity", [
    123, True, ["source-face-first"], {"id": "source-face-first"},
    " source-face-first", "source-face-first ", "\tsource-face-first",
    "source-face-first\n", b"source-face-first", float("nan"),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_malformed_original_floor_identity_vetoes_complete_owner_universe(
    field_name, bad_identity, reverse,
):
    boxes = _two_separated_floor_boxes()
    boxes[0][field_name] = bad_identity
    if reverse:
        boxes.reverse()
    original = copy.deepcopy(boxes)
    result = _two_floor_result(boxes)
    assert boxes == original
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 2
    assert len({row.record_id for row in result.records}) == 2
    for row in result.records:
        assert row.status is EvidenceResolutionStatus.ABSTAINED
        assert SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID in row.reason_codes
        assert row.authority_blockers == ()
        assert not row.takeoff_eligible
        assert not row.commercial_projection_allowed
    bad_row = result.records[1 if reverse else 0]
    assert getattr(bad_row, field_name) == ""
    assert SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID in result.reason_codes


def test_original_native_floor_identity_remains_verbatim_and_shadow_only():
    boxes = _two_separated_floor_boxes()
    boxes[0]["source_room_face_record_id"] = "source:face/first#1"
    before = copy.deepcopy(boxes)
    result = _two_floor_result(boxes)
    assert boxes == before
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 2
    assert result.records[0].source_room_face_record_id == "source:face/first#1"
    assert all(row.status is EvidenceResolutionStatus.CANDIDATE
               for row in result.records)
    assert all(not row.takeoff_eligible and not row.commercial_projection_allowed
               for row in result.records)


def test_malformed_identity_does_not_erase_real_competing_finish_conflict():
    boxes = _two_separated_floor_boxes()[:1]
    boxes[0]["physical_room_id"] = {"untrusted": "room"}
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=boxes,
        marks=[
            {"x": 327.8, "y": 1437.5, "code": "FT3",
             "registered_region": True},
            {"x": 335.8, "y": 1447.5, "code": "FT2",
             "registered_region": True},
        ],
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert len(result.records) == 1
    row = result.records[0]
    assert row.status is EvidenceResolutionStatus.CONFLICT
    assert row.physical_room_id == ""
    assert COMPETING_FINISH_CODES_IN_BOX in row.reason_codes
    assert SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID in row.reason_codes
    assert not row.takeoff_eligible and not row.commercial_projection_allowed
