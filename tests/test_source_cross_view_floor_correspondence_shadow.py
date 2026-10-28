"""Synthetic tests for pb_source_cross_view_floor_correspondence_shadow.

Verifies exact rigid geometric registration, dual-sheet wall-boundedness proof,
mark containment and typed negative/ambiguity rejection. Pure synthetic geometry:
zero PDF or benchmark gold consumed.
"""
from __future__ import annotations

import copy
import math
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
    OVERLAPPING_MEASURED_BOXES,
    REGISTRATION_NOT_UNIQUE,
    STANDING_AUTHORITY_BLOCKERS,
    build_lines,
    rank_registrations,
    box_correspondence,
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
