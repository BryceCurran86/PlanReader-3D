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
    SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED,
    MAX_SOURCE_FINISH_CODE_BOX_SUMMARY_ENTRIES,
    SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,
    SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED,
    SOURCE_NULL_SUPPORT_TRIALS_INVALID,
    MIN_SOURCE_NULL_SUPPORT_TRIALS,
    MAX_SOURCE_NULL_SUPPORT_TRIALS,
    MAX_SOURCE_REGISTRATION_VOTE_PAIRS,
    SOURCE_MEASURED_FLOOR_BOX_INVALID,
    SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID,
    OVERLAPPING_MEASURED_BOXES,
    _overlapping_measured_box_flags,
    _indexed_marks_in_boxes,
    DUPLICATE_PHYSICAL_FLOOR_IDENTITY,
    MISSING_PHYSICAL_FLOOR_IDENTITY,
    REGISTRATION_NOT_UNIQUE,
    REGISTRATION_TRANSLATION_ALIAS,
    STANDING_AUTHORITY_BLOCKERS,
    build_lines,
    LineIndex,
    _shift_votes,
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


# A page cannot corroborate itself as an independent cross-sheet owner.
# Keep this earliest selector boundary separate from the downstream original
# decoded-page gate: synthetic source-shadow callers must fail closed too.
@pytest.mark.parametrize("page_id", ["7", "11"])
def test_cross_view_selector_rejects_same_original_page(page_id):
    base = sample_selector()
    fields = {
        name: getattr(base, name)
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "support_page_id", "target_page_id", "material_code",
        )
    }
    fields.update(support_page_id=page_id, target_page_id=page_id)
    with pytest.raises(ValueError, match="support and target pages must differ"):
        SourceCrossViewFloorCorrespondenceSelector(**fields)


@pytest.mark.parametrize("field_name", ["support_page_id", "target_page_id"])
@pytest.mark.parametrize("bad_page_id", [" 7","7 ","7\n","\t7","7\u0000"])
def test_cross_view_selector_rejects_noncanonical_page_aliases(field_name, bad_page_id):
    base = sample_selector()
    fields = {
        name: getattr(base, name)
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "support_page_id", "target_page_id", "material_code",
        )
    }
    fields[field_name] = bad_page_id
    with pytest.raises(ValueError, match=field_name):
        SourceCrossViewFloorCorrespondenceSelector(**fields)


# A printable page ID is not necessarily a canonical original PDF page.
# In particular, "07" and "7" may be the SAME page rather than two sources.
@pytest.mark.parametrize("field_name", ["support_page_id", "target_page_id"])
@pytest.mark.parametrize(
    "bad_page_id",
    [
        "00", "01", "07", "007", "011", "000",
        "+7", "-7", "7.0", "7e0", "7/7",
        "A7", "Page 7",
        "７",  # fullwidth decimal seven
        "٧",  # Arabic-Indic decimal seven
        "𝟟",  # mathematical double-struck seven
        "Ⅶ",  # Roman numeral
        "7\u200b",  # zero-width space
    ],
)
def test_cross_view_selector_rejects_noncanonical_numbered_page_id(
    field_name, bad_page_id,
):
    original = sample_selector()
    with pytest.raises(ValueError, match=field_name):
        replace(original, **{field_name: bad_page_id})
    # Fail closed before any synthetic wall registration or mark promotion,
    # and leave the authenticated original page selector untouched.
    assert (original.support_page_id, original.target_page_id) == ("11", "7")


@pytest.mark.parametrize(
    "support_id,target_id",
    [("7", "07"), ("007", "7"), ("7", "٧"), ("７", "7"), ("11", "011")],
)
def test_cross_view_selector_never_treats_page_aliases_as_two_sources(
    support_id, target_id,
):
    with pytest.raises(ValueError, match="source page identity"):
        replace(sample_selector(), support_page_id=support_id, target_page_id=target_id)


def test_cross_view_selector_keeps_zero_index_and_distinct_decimal_pages():
    selector = replace(sample_selector(), support_page_id="0", target_page_id="7")
    assert (selector.support_page_id, selector.target_page_id) == ("0", "7")
    assert selector != sample_selector()
    assert selector.support_page_id != selector.target_page_id


def test_cross_view_selector_keeps_distinct_original_page_ids_verbatim():
    selector = sample_selector()
    assert selector.support_page_id == "11"
    assert selector.target_page_id == "7"
    assert selector.support_page_id != selector.target_page_id


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



def _mark_index_oracle(boxes, marks):
    """Original exhaustive producer loop and public classifier as an oracle."""
    expected = []
    for x0, y0, x1, y1 in boxes:
        inside = []
        for x, y, mark in marks:
            margin = min(x - x0, x1 - x, y - y0, y1 - y)
            if margin >= 0:
                inside.append({
                    "code": mark.get("code"),
                    "margin_pt": margin,
                    "registered_region": mark.get("registered_region"),
                })
        expected.append(classify_floor(
            _fully_supported_correspondence(),
            registration_unique=True,
            marks_inside=inside,
            other_labelled_boxes_overlapping=0,
            material_code="FT3",
        ))
    return expected


def test_full_mark_containment_index_matches_exhaustive_classifier_oracle():
    # Compare *all* classifier predicates, not just candidate counts:
    # malformed code, duplicate same code, competing FT2/FT3, registration,
    # exact five-point margin, inclusive edges and no-mark cases.
    rng = random.Random(20261030)
    for _ in range(85):
        boxes = []
        for _ in range(rng.randrange(1, 28)):
            x0 = rng.randrange(-50, 50) / 2.0
            y0 = rng.randrange(-50, 50) / 2.0
            boxes.append((x0, y0, x0 + rng.randrange(1, 30) / 2.0,
                          y0 + rng.randrange(1, 30) / 2.0))
        marks = []
        for _ in range(rng.randrange(0, 90)):
            x = rng.randrange(-80, 100) / 2.0
            y = rng.randrange(-80, 100) / 2.0
            marks.append((x, y, {
                "code": rng.choice(("FT2", "FT3", None, " FT3")),
                "registered_region": rng.choice((True, False, "true", None)),
            }))
        original = copy.deepcopy((boxes, marks))
        indexed = _indexed_marks_in_boxes(marks, boxes)
        expected = _mark_index_oracle(boxes, marks)
        assert len(indexed) == len(expected)
        for (compressed, counts), oracle in zip(indexed, expected):
            actual = classify_floor(
                _fully_supported_correspondence(),
                registration_unique=True,
                marks_inside=compressed,
                other_labelled_boxes_overlapping=0,
                material_code="FT3",
            )
            actual["finish_codes_in_box"] = counts
            assert actual == oracle
        assert (boxes, marks) == original


def test_full_mark_index_preserves_fractional_margin_and_boundary_predicates():
    edge = math.nextafter(5.0, 0.0)
    outer = (0.0, 0.0, 20.0, 20.0)
    cases = [
        [(5.0, 10.0, {"code": "FT3", "registered_region": True})],
        [(edge, 10.0, {"code": "FT3", "registered_region": True})],
        [(0.0, 10.0, {"code": "FT3", "registered_region": True})],
        [(20.0, 10.0, {"code": "FT3", "registered_region": True})],
        [(20.01, 10.0, {"code": "FT3", "registered_region": True})],
        [(5.0, 10.0, {"code": "FT3", "registered_region": True}),
         (10.0, 10.0, {"code": "FT2", "registered_region": False})],
    ]
    for marks in cases:
        original = copy.deepcopy(marks)
        compressed, counts = _indexed_marks_in_boxes(marks, [outer])[0]
        actual = classify_floor(
            _fully_supported_correspondence(),
            registration_unique=True,
            marks_inside=compressed,
            other_labelled_boxes_overlapping=0,
            material_code="FT3",
        )
        actual["finish_codes_in_box"] = counts
        assert actual == _mark_index_oracle([outer], marks)[0]
        assert marks == original


def test_full_mark_index_handles_20000_disjoint_and_dense_source_universes():
    # The former full producer performed 400,000,000 containment checks.
    # Verify exact code multiplicities and no first/nearest mark selection.
    marks = [
        (float(3 * i + 10), 20.0, {"code": "FT3", "registered_region": True})
        for i in range(20000)
    ]
    disjoint = [
        (float(3 * i), 0.0, float(3 * i + 20), 40.0)
        for i in range(20000)
    ]
    # Overlapping disjoint x ranges are intentional: check exact multiplicity
    # against a small local geometric oracle at several positions.
    out = _indexed_marks_in_boxes(marks, disjoint)
    assert len(out) == 20000
    for i in (0, 1, 200, 19999):
        expected = sum(
            3 * i <= x <= 3 * i + 20 and 0 <= y <= 40
            for x, y, _ in marks
        )
        assert out[i][1] == {"FT3": expected}
        assert len(out[i][0]) == (2 if expected > 1 else 1)
    dense = [(0.0, 0.0, 60020.0, 40.0)] * 20000
    dense_out = _indexed_marks_in_boxes(marks, dense)
    assert len(dense_out) == 20000
    assert all(counts == {"FT3": 20000} and len(comp) == 2
               for comp, counts in dense_out)


def test_full_producer_dense_marks_are_counted_without_commercial_promotion():
    # End-to-end source-neutral producer path, not merely the helper.
    boxes = [
        {
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": f"floor-{i}",
            "physical_room_id": f"room-{i}",
            "source_room_face_record_id": f"face-{i}",
        }
        for i in range(1024)
    ]
    marks = [
        {"x": 300.0 + i * 0.01, "y": 1437.5,
         "code": "FT3", "registered_region": True}
        for i in range(1024)
    ]
    original = copy.deepcopy((boxes, marks))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=boxes,
        marks=marks,
    )
    assert (boxes, marks) == original
    assert len(result.records) == 1024
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert all(row.finish_codes_in_box == {"FT3": 1024}
               and row.status is EvidenceResolutionStatus.ABSTAINED
               and MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX in row.reason_codes
               and OVERLAPPING_MEASURED_BOXES in row.reason_codes
               and not row.takeoff_eligible and not row.commercial_projection_allowed
               for row in result.records)


# High-cardinality source code universes must never allocate a full
# 20,000-box x 20,000-code Counter or iterate all keys per Fenwick prefix.
# These are source-neutral safety tests, not original-plan quantity evidence.
def test_high_cardinality_20000_by_20000_mark_index_abstains_before_allocation():
    marks = [
        (10.0, 10.0, {"code": f"FT-{i:05d}", "registered_region": True})
        for i in range(20000)
    ]
    boxes = [(0.0, 0.0, 20.0, 20.0)] * 20000
    assert len(marks) == len(boxes) == 20000
    assert len({mark["code"] for _, _, mark in marks}) == 20000
    assert len(boxes) * len(marks) > MAX_SOURCE_FINISH_CODE_BOX_SUMMARY_ENTRIES
    with pytest.raises(ValueError, match=SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED):
        _indexed_marks_in_boxes(marks, boxes)
    # Direct helper must not modify its source evidence on refusal.
    assert marks[0][2]["code"] == "FT-00000"
    assert marks[-1][2]["code"] == "FT-19999"
    assert boxes[0] == boxes[-1] == (0.0, 0.0, 20.0, 20.0)


@pytest.mark.parametrize("reverse", [False, True])
def test_high_cardinality_full_producer_typed_abstain_without_registration(reverse):
    boxes = [
        {"dimension_box_pdf_pts": (0.0, 0.0, 20.0, 20.0),
         "canonical_floor_id": f"floor-{i}",
         "physical_room_id": f"room-{i}",
         "source_room_face_record_id": f"face-{i}"}
        for i in range(20000)
    ]
    marks = [
        {"x": 10.0, "y": 10.0, "code": f"FT-{i:05d}",
         "registered_region": True}
        for i in range(20000)
    ]
    if reverse:
        boxes.reverse()
        marks.reverse()
    # No support or target geometry: resource veto must precede registration.
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=[], target_segments=[],
        measured_boxes=boxes, marks=marks,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED,)
    assert result.records == ()
    assert result.winning_registration is None
    assert boxes[0]["dimension_box_pdf_pts"] == (0.0, 0.0, 20.0, 20.0)
    assert marks[0]["registered_region"] is True
    assert marks[0]["code"] == ("FT-19999" if reverse else "FT-00000")


def test_small_multi_code_source_universe_preserves_exact_counts_and_conflict():
    marks = [
        (10.0, 10.0, {"code": "FT3", "registered_region": True}),
        (11.0, 11.0, {"code": "FT2", "registered_region": True}),
    ]
    boxes = [(0.0, 0.0, 20.0, 20.0)] * 2
    assert len(boxes) * 2 <= MAX_SOURCE_FINISH_CODE_BOX_SUMMARY_ENTRIES
    indexed = _indexed_marks_in_boxes(marks, boxes)
    assert len(indexed) == 2
    for compressed, counts in indexed:
        assert counts == {"FT2": 1, "FT3": 1}
        classified = classify_floor(
            _fully_supported_correspondence(),
            registration_unique=True,
            marks_inside=compressed,
            other_labelled_boxes_overlapping=0,
            material_code="FT3",
        )
        assert classified["status"] is EvidenceResolutionStatus.CONFLICT
        assert COMPETING_FINISH_CODES_IN_BOX in classified["reason_codes"]
        assert classified["finish_codes_in_box"] == counts


def test_cardinality_refusal_preserves_malformed_mark_and_box_universe_negatives():
    marks = [
        {"x": 10.0, "y": 10.0, "code": f"FT-{i}",
         "registered_region": True}
        for i in range(1000)
    ]
    marks.append({"x": 10.0, "y": 10.0, "registered_region": True})
    boxes = [
        {"dimension_box_pdf_pts": (0.0, 0.0, 20.0, 20.0),
         "canonical_floor_id": f"floor-{i}",
         "physical_room_id": f"room-{i}",
         "source_room_face_record_id": f"face-{i}"}
        for i in range(300)
    ]
    boxes.append({"dimension_box_pdf_pts": (0.0, 0.0, 0.0, 20.0)})
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=[], target_segments=[],
        measured_boxes=boxes, marks=marks,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED,
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
    )
    assert result.records == ()
    assert marks[-1] == {"x": 10.0, "y": 10.0, "registered_region": True}
    assert boxes[-1]["dimension_box_pdf_pts"] == (0.0, 0.0, 0.0, 20.0)


# GPT2: wall-source completeness must be proved before any geometric
# registration; silently dropping a malformed competing wall is unsafe.
def _wall_universe_shadow_result(support, target):
    return SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support,
        target_segments=target,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "office-floor",
            "physical_room_id": "office-room",
            "source_room_face_record_id": "office-face",
        }],
        marks=[{
            "x": 327.8, "y": 1437.5,
            "code": "FT3", "registered_region": True,
        }],
    )


@pytest.mark.parametrize("sheet", ["support", "target"])
@pytest.mark.parametrize("bad_segment", [
    None,
    "not-a-native-segment",
    {"x1": 0.0, "y1": 0.0, "x2": 1.0},  # missing endpoint
    {"x1": 0.0, "y1": 0.0, "x2": True, "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": "1.0", "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": float("nan"), "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": float("inf"), "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": -float("inf"), "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": 2**53 + 1, "y2": 1.0},
    {"x1": 0.0, "y1": 0.0, "x2": 1e100, "y2": 1.0},
])
@pytest.mark.parametrize("prepend", [False, True])
def test_complete_wall_universe_rejects_malformed_competing_segment(
    sheet, bad_segment, prepend
):
    support = support_sheet()
    target = list(TARGET_SHEET)
    chosen = support if sheet == "support" else target
    if prepend:
        chosen.insert(0, copy.deepcopy(bad_segment))
    else:
        chosen.append(copy.deepcopy(bad_segment))
    before = repr((support, target))
    result = _wall_universe_shadow_result(support, target)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,)
    assert result.records == ()
    assert repr((support, target)) == before


@pytest.mark.parametrize("sheet", ["support", "target"])
def test_complete_wall_universe_rejects_more_than_20000_segments(sheet):
    support = support_sheet()
    target = list(TARGET_SHEET)
    oversized = [seg(0, 0, 100, 0)] * 20_001
    if sheet == "support":
        support = oversized
    else:
        target = oversized
    result = _wall_universe_shadow_result(support, target)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,)
    assert result.records == ()


@pytest.mark.parametrize("sheet", ["support", "target"])
def test_complete_wall_universe_rejects_unbounded_or_untyped_container(sheet):
    support = support_sheet()
    target = list(TARGET_SHEET)
    if sheet == "support":
        support = iter(support)
    else:
        target = "not-a-native-segment-sequence"
    result = _wall_universe_shadow_result(support, target)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,)
    assert result.records == ()


def test_valid_native_wall_universe_preserves_shadow_candidate_only():
    result = _wall_universe_shadow_result(support_sheet(), list(TARGET_SHEET))
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False


def test_wall_veto_preserves_independent_malformed_mark_and_box_evidence():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet() + [{"x1": 1.0, "y1": 2.0}],
        target_segments=list(TARGET_SHEET),
        measured_boxes=[{
            "dimension_box_pdf_pts": (0.0, 0.0, 0.0, 1.0),
            "canonical_floor_id": "malformed-room",
        }],
        marks=[{"x": float("nan"), "y": 100.0, "code": "FT3"}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
    )
    assert result.records == ()


def test_all_invalid_boxes_preserve_independent_mark_negative_with_valid_walls():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=list(TARGET_SHEET),
        measured_boxes=[{"dimension_box_pdf_pts": (0.0, 0.0, 0.0, 1.0)}],
        marks=[{"x": float("nan"), "y": 100.0, "code": "FT3"}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
    )
    assert result.records == ()


def test_registration_shift_window_matches_original_complete_vote_oracle():
    import collections

    rng = random.Random(20261030)
    for _ in range(40):
        source = {
            o: {
                float(i * 1000 + rng.randint(-100, 100)): [
                    (float(i), float(i + rng.randint(3, 50)))
                ]
                for i in range(12)
            }
            for o in "HV"
        }
        target = {
            o: {
                float(i * 1000 + rng.randint(-100, 100)): [
                    (float(i), float(i + rng.randint(3, 50)))
                ]
                for i in range(12)
            }
            for o in "HV"
        }
        index = LineIndex(target)
        before = repr((source, target))
        expected_votes = {"H": collections.Counter(), "V": collections.Counter()}
        for o in "HV":
            for k, intervals in source[o].items():
                source_length = sum(hi - lo for lo, hi in intervals)
                for k2 in index.keys[o]:
                    d = k2 - k
                    if abs(d) > 3000.0:
                        continue
                    target_length = sum(hi - lo for lo, hi in target[o][k2])
                    expected_votes[o][round(d / 0.04) * 0.04] += min(
                        source_length, target_length
                    )
        expected = (
            [d for d, _ in sorted(
                expected_votes["V"].items(), key=lambda kv: (-kv[1], kv[0])
            )[:7]],
            [d for d, _ in sorted(
                expected_votes["H"].items(), key=lambda kv: (-kv[1], kv[0])
            )[:7]],
        )
        assert _shift_votes(source, index, 7) == expected
        assert repr((source, target)) == before


def test_registration_vote_budget_abstains_on_complete_dense_native_universe():
    # Valid 20k native axis keys on each page: the old Cartesian vote scan
    # would attempt 400m comparisons for one orientation. No partial votes.
    segments = [seg(i / 10, 0, i / 10, 100) for i in range(20_000)]
    before = repr(segments)
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        rank_registrations(build_lines(segments), build_lines(segments))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=segments,
        target_segments=segments,
        measured_boxes=[{
            "dimension_box_pdf_pts": (10.0, 10.0, 100.0, 100.0),
            "canonical_floor_id": "source-only-room",
        }],
        marks=[{"x": 50.0, "y": 50.0, "code": "FT3", "registered_region": True}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED,)
    assert result.records == ()
    assert repr(segments) == before
    assert MAX_SOURCE_REGISTRATION_VOTE_PAIRS < 20_000 * 20_000


def test_registration_vote_budget_preserves_independent_invalid_mark_and_box():
    segments = [seg(i / 10, 0, i / 10, 100) for i in range(2_000)]
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=segments,
        target_segments=segments,
        measured_boxes=[
            {"dimension_box_pdf_pts": (10.0, 10.0, 100.0, 100.0)},
            {"dimension_box_pdf_pts": (0.0, 0.0, 0.0, 1.0)},
        ],
        marks=[{"x": float("nan"), "y": 20.0, "code": "FT3"}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED,
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
    )
    assert result.records == ()


@pytest.mark.parametrize(
    "bad_mark",
    [
        {"x": float("nan"), "y": 20.0, "code": "FT3", "registered_region": True},
        {"x": 20.0, "y": 20.0, "code": " FT3", "registered_region": True},
        {"x": 20.0, "y": 20.0, "code": 3, "registered_region": True},
    ],
)
def test_no_registration_retains_independent_invalid_mark_and_box_reasons(bad_mark):
    """No transform cannot erase a malformed FT occurrence or sibling room."""
    good_mark = {"x": 50.0, "y": 50.0, "code": "FT3", "registered_region": True}
    boxes = [
        {"dimension_box_pdf_pts": (0.0, 0.0, 100.0, 100.0)},
        {"dimension_box_pdf_pts": (0.0, 0.0, 0.0, 100.0)},
    ]
    for marks in ([good_mark, bad_mark], [bad_mark, good_mark]):
        before = repr((marks, boxes))
        result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
            selector=sample_selector(),
            support_segments=[],
            target_segments=[],
            measured_boxes=boxes,
            marks=marks,
        )
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (
            REGISTRATION_NOT_UNIQUE,
            SOURCE_FINISH_MARK_IDENTITY_INVALID,
            SOURCE_MEASURED_FLOOR_BOX_INVALID,
        )
        assert result.records == ()
        assert repr((marks, boxes)) == before


@pytest.mark.parametrize(
    "bad_boxes",
    [
        None,
        {"dimension_box_pdf_pts": (0.0, 0.0, 100.0, 100.0)},
        [None] * 20_001,
    ],
)
def test_invalid_box_container_retains_independent_mark_and_wall_negatives(bad_boxes):
    """Container preflight must retain independent source defects, never FIRM."""
    bad_wall = {"x1": "not-native", "y1": 0.0, "x2": 10.0, "y2": 0.0}
    marks = [
        {"x": 50.0, "y": 50.0, "code": "FT3", "registered_region": True},
        {"x": float("nan"), "y": 20.0, "code": "FT3", "registered_region": True},
    ]
    for source, target in (([bad_wall], []), ([], [bad_wall])):
        for order in (marks, list(reversed(marks))):
            before = repr((source, target, bad_boxes, order))
            result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
                selector=sample_selector(),
                support_segments=source,
                target_segments=target,
                measured_boxes=bad_boxes,
                marks=order,
            )
            assert result.status is EvidenceResolutionStatus.ABSTAINED
            assert result.reason_codes == (
                SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,
                SOURCE_FINISH_MARK_IDENTITY_INVALID,
                SOURCE_MEASURED_FLOOR_BOX_INVALID,
            )
            assert result.records == ()
            assert repr((source, target, bad_boxes, order)) == before


def test_no_registration_and_invalid_box_container_clean_negative_controls():
    producer = SourceCrossViewFloorCorrespondenceProducer()
    clean_mark = [{"x": 50.0, "y": 50.0, "code": "FT3", "registered_region": True}]
    base = dict(
        selector=sample_selector(),
        support_segments=[],
        target_segments=[],
        marks=clean_mark,
    )
    no_registration = producer.evaluate_synthetic(
        **base,
        measured_boxes=[{"dimension_box_pdf_pts": (0.0, 0.0, 100.0, 100.0)}],
    )
    assert no_registration.status is EvidenceResolutionStatus.ABSTAINED
    assert no_registration.reason_codes == (REGISTRATION_NOT_UNIQUE,)
    assert no_registration.records == ()
    invalid_container = producer.evaluate_synthetic(**base, measured_boxes=None)
    assert invalid_container.status is EvidenceResolutionStatus.ABSTAINED
    assert invalid_container.reason_codes == (SOURCE_MEASURED_FLOOR_BOX_INVALID,)
    assert invalid_container.records == ()


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("invalid_coordinate", [2**53 + 1, -(2**53 + 1), 1e100, -1e100])
@pytest.mark.parametrize("prepend", [False, True])
def test_non_lossless_original_mark_coordinate_vetoes_complete_owner_universe(
    axis, invalid_coordinate, prepend
):
    """Distinct native positions must not alias on binary64 conversion."""
    good = {
        "x": 327.8, "y": 1437.5,
        "code": "FT3", "registered_region": True,
    }
    bad = dict(good)
    bad[axis] = invalid_coordinate
    marks = [bad, good] if prepend else [good, bad]
    boxes = [{
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "office-floor",
        "physical_room_id": "office-room",
        "source_room_face_record_id": "office-face",
    }]
    support, target = support_sheet(), list(TARGET_SHEET)
    before = repr((support, target, boxes, marks))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support,
        target_segments=target,
        measured_boxes=boxes,
        marks=marks,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 1
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.reason_codes
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.records[0].reason_codes
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert result.records[0].commercial_projection_allowed is False
    assert result.records[0].takeoff_eligible is False
    assert repr((support, target, boxes, marks)) == before


def test_exact_native_mark_coordinate_limit_preserves_existing_clean_candidate():
    """The new source-integrity veto must not remove a normal valid mark."""
    result = _wall_universe_shadow_result(support_sheet(), list(TARGET_SHEET))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].takeoff_eligible is False


@pytest.mark.parametrize("axis", (0, 1, 2, 3))
@pytest.mark.parametrize("reverse_boxes", (False, True))
def test_oversized_native_float_floor_box_coordinates_fail_closed(axis, reverse_boxes):
    """A malformed competing physical box must not confer a unique owner.

    The source mark and wall universes already reject magnitudes above 2**53
    for both numeric types; a float floor-box endpoint must do the same.
    """
    good = {
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-room-office",
        "source_room_face_record_id": "face-office",
    }
    bad = copy.deepcopy(good)
    bad["canonical_floor_id"] = "canonical-floor-competitor"
    bad["physical_room_id"] = "physical-room-competitor"
    bad["source_room_face_record_id"] = "face-competitor"
    coords = list(bad["dimension_box_pdf_pts"])
    # Preserve ordered box geometry so the only source defect is precision.
    coords[axis] = float(-(2**53 + 2) if axis in (0, 1) else 2**53 + 2)
    bad["dimension_box_pdf_pts"] = tuple(coords)
    boxes = [good, bad]
    if reverse_boxes:
        boxes.reverse()
    marks = [{"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True}]
    original_boxes, original_marks = copy.deepcopy(boxes), copy.deepcopy(marks)

    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=boxes,
        marks=marks,
    )
    assert len(result.records) == 1
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    rec = result.records[0]
    assert rec.canonical_floor_id == good["canonical_floor_id"]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_MEASURED_FLOOR_BOX_INVALID in rec.reason_codes
    assert SOURCE_MEASURED_FLOOR_BOX_INVALID in result.reason_codes
    assert rec.finish_codes_in_box == {"FT3": 1}
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False
    assert rec.authority_blockers == ()
    assert boxes == original_boxes
    assert marks == original_marks


def test_only_oversized_native_float_floor_box_abstains_without_record():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, float(2**53 + 2), 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True}],
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_MEASURED_FLOOR_BOX_INVALID,)
    assert result.records == ()


def test_oversized_native_float_floor_box_retains_genuine_ft2_ft3_conflict():
    good = {
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-room-office",
        "source_room_face_record_id": "face-office",
    }
    bad = {
        **good,
        "dimension_box_pdf_pts": (-float(2**53 + 2), 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-competitor",
        "physical_room_id": "physical-room-competitor",
        "source_room_face_record_id": "face-competitor",
    }
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[bad, good],
        marks=[
            {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True},
            {"x": 345.0, "y": 1440.0, "code": "FT2", "registered_region": True},
        ],
    )
    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert rec.finish_codes_in_box == {"FT2": 1, "FT3": 1}
    assert COMPETING_FINISH_CODES_IN_BOX in rec.reason_codes
    assert SOURCE_MEASURED_FLOOR_BOX_INVALID in rec.reason_codes
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False


# GPT2: null-registration support is part of the source identity gate, not a
# caller-tunable shortcut. A zero/one-trial null sample can crash or make a
# weak registration appear unique. Reject it before scoring any source box.
@pytest.mark.parametrize("bad_trials", [
    None, False, True, 0, -1, 1, 59, 60.0, "60",
    1001, 10**100, float("nan"), float("inf"),
])
def test_null_support_trial_budget_abstains_without_source_owner(bad_trials):
    boxes = [{
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-room-office",
        "source_room_face_record_id": "face-office",
    }]
    marks = [{"x": 327.8, "y": 1437.5, "code": "FT3",
              "registered_region": True}]
    original_boxes, original_marks = copy.deepcopy(boxes), copy.deepcopy(marks)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=support_sheet(),
        target_segments=TARGET_SHEET, measured_boxes=boxes,
        marks=marks, trials=bad_trials,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_NULL_SUPPORT_TRIALS_INVALID,)
    assert result.records == ()
    assert result.winning_registration is None
    assert boxes == original_boxes
    assert marks == original_marks


@pytest.mark.parametrize("trials", [
    MIN_SOURCE_NULL_SUPPORT_TRIALS, MAX_SOURCE_NULL_SUPPORT_TRIALS,
])
def test_bounded_complete_null_support_retains_clean_shadow_candidate(trials):
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3",
                "registered_region": True}],
        trials=trials,
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].commercial_projection_allowed is False


def test_invalid_null_trials_retain_independent_source_universe_negatives():
    support = support_sheet() + [
        {"x1": 0.0, "y1": 0.0, "x2": True, "y2": 1.0},
    ]
    boxes = [
        {"dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04)},
        {"dimension_box_pdf_pts": (0.0, 0.0, 0.0, 20.0)},
    ]
    marks = [
        {"x": 327.8, "y": 1437.5, "code": "FT3",
         "registered_region": True},
        {"x": 328.0, "y": 1438.0, "code": None,
         "registered_region": True},
    ]
    before = copy.deepcopy((support, boxes, marks))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=support,
        target_segments=TARGET_SHEET, measured_boxes=boxes,
        marks=marks, trials=0,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_WALL_SEGMENT_UNIVERSE_INVALID,
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
        SOURCE_NULL_SUPPORT_TRIALS_INVALID,
    )
    assert result.records == ()
    assert (support, boxes, marks) == before


@pytest.mark.parametrize("malformed_input,expected_reasons", [
    ("marks", (
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_NULL_SUPPORT_TRIALS_INVALID,
    )),
    ("boxes", (
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
        SOURCE_NULL_SUPPORT_TRIALS_INVALID,
    )),
])
def test_invalid_null_trials_survive_early_malformed_container_abstain(
    malformed_input, expected_reasons,
):
    kwargs = {
        "selector": sample_selector(),
        "support_segments": support_sheet(),
        "target_segments": TARGET_SHEET,
        "measured_boxes": [{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        }],
        "marks": [{"x": 327.8, "y": 1437.5, "code": "FT3",
                   "registered_region": True}],
        "trials": False,
    }
    kwargs["marks" if malformed_input == "marks" else "measured_boxes"] = None
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(**kwargs)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == expected_reasons
    assert result.records == ()


def _exhaustive_outward_second_face_oracle(box, lines, band):
    """Independent original full-key scan, including every outward competitor."""
    x0, y0, x1, y1 = box
    answer = {}
    for name, orient, coord, lo, hi, sign in (
        ("x0", "V", x0, y0, y1, -1),
        ("x1", "V", x1, y0, y1, 1),
        ("y0", "H", y0, x0, x1, -1),
        ("y1", "H", y1, x0, x1, 1),
    ):
        length = hi - lo
        faces, intervals = [], []
        for key in sorted(lines[orient]):
            signed = (key - coord) * sign
            if band[0] <= signed <= band[1]:
                covered = merge_intervals(
                    (max(a, lo), min(b, hi))
                    for a, b in lines[orient][key]
                    if min(b, hi) > max(a, lo)
                )
                coverage = sum(b - a for a, b in covered) / length if length > 0 else 0.0
                if coverage >= 0.50:
                    offset = round(signed, 2)
                    faces.append((offset, round(coverage, 3)))
                    intervals.append((
                        offset,
                        [(round(a, 2), round(b, 2)) for a, b in covered],
                    ))
        answer[name] = (faces, intervals)
    return answer


@pytest.mark.parametrize("seed", range(25))
def test_outward_wall_band_index_matches_exhaustive_source_key_oracle(seed):
    rng = random.Random(20261030 + seed)
    x0, y0 = rng.uniform(-30, 30), rng.uniform(-30, 30)
    box = (x0, y0, x0 + 80.0, y0 + 90.0)
    band = (3.0, 15.0) if seed % 2 else (0.125, 3.75)
    lines = {"H": {}, "V": {}}
    for orient, left, right in (
        ("H", y0, y0 + 90.0),
        ("V", x0, x0 + 80.0),
    ):
        keys = [rng.uniform(-70, 150) for _ in range(45)]
        # Every side, both signs, both inclusive boundaries and their
        # immediate floating-point neighbours are retained by the oracle.
        for coord in (left, right):
            for sign in (-1, 1):
                for distance in band:
                    boundary = coord + sign * distance
                    keys.extend((
                        math.nextafter(boundary, -math.inf),
                        boundary,
                        math.nextafter(boundary, math.inf),
                    ))
        for key in keys:
            lo = (x0 if orient == "H" else y0) - 8.0
            hi = (x0 + 80.0 if orient == "H" else y0 + 90.0) + 8.0
            lines[orient][key] = [(lo, hi), (lo + 25.0, hi - 10.0)]
    before = repr((box, lines))
    indexed = side_evidence(box, lines, band=band)
    oracle = _exhaustive_outward_second_face_oracle(box, lines, band)
    for name in ("x0", "x1", "y0", "y1"):
        assert indexed[name]["second_face"] == oracle[name][0]
        assert indexed[name]["second_face_intervals"] == oracle[name][1]
    assert repr((box, lines)) == before
    assert side_evidence(box, lines, band=band) == indexed


def test_outward_wall_band_index_large_exact_native_coordinates():
    # Precision and signed outwardness must survive near the source
    # binary64 exact-coordinate ceiling, not merely at page-scale origin.
    origin = float(2**53 - 256)
    box = (origin, origin, origin + 100.0, origin + 100.0)
    lines = {
        orient: {
            origin + offset: [(origin - 20.0, origin + 120.0)]
            for offset in (-20.0, -15.0, -3.0, 0.0, 3.0, 15.0, 20.0, 100.0, 103.0, 115.0, 120.0)
        }
        for orient in "HV"
    }
    indexed = side_evidence(box, lines)
    oracle = _exhaustive_outward_second_face_oracle(box, lines, (3.0, 15.0))
    for name in ("x0", "x1", "y0", "y1"):
        assert indexed[name]["second_face"] == oracle[name][0]
        assert indexed[name]["second_face_intervals"] == oracle[name][1]


def test_outward_wall_band_index_20000_native_keys_many_boxes():
    # A valid complete 20k-key universe and 2k measured boxes used to
    # require 160 million unrelated full-key comparisons across four sides.
    # Assert complete source output, not a fragile wall-clock threshold.
    keys = [float(i * 2) for i in range(20_000)]
    lines = {
        "H": {key: [(0.0, 40_000.0)] for key in keys},
        "V": {key: [(0.0, 40_000.0)] for key in keys},
    }
    before = (len(lines["H"]), len(lines["V"]))
    for i in range(2_000):
        offset = float(i * 2 + 40)
        box = (offset, offset, offset + 50.0, offset + 50.0)
        evidence = side_evidence(box, lines)
        assert all(
            evidence[side]["second_face"]
            for side in ("x0", "x1", "y0", "y1")
        )
    assert (len(lines["H"]), len(lines["V"])) == before


def test_reused_sheet_line_index_matches_full_rebuild_and_rejects_cross_sheet_alias():
    # The same exact source wall evidence must be used with or without a
    # prebuilt index. A target index cannot masquerade as support-wall ink.
    support = build_lines(support_sheet())
    target = build_lines(TARGET_SHEET)
    box = (251.04, 1382.72, 394.80, 1585.04)
    before = repr((support, target, box))
    kwargs = {
        "lines_support": support,
        "lines_target": target,
        "orientation": "identity",
        "translation": TRUE_T,
    }
    rebuilt = box_correspondence(box, **kwargs)
    indexed = box_correspondence(
        box, **kwargs,
        _support_index=LineIndex(support),
        _target_index=LineIndex(target),
    )
    assert indexed == rebuilt
    assert indexed["wall_bounded_on_both_sheets"] is True
    assert indexed["wall_evidence_identical_on_both_sheets"] is True
    assert all(
        indexed["sides"][side]["outward_second_faces_match"]
        for side in ("x0", "x1", "y0", "y1")
    )
    with pytest.raises(ValueError, match="source_line_index_does_not_match_sheet"):
        box_correspondence(box, **kwargs, _support_index=LineIndex(target))
    with pytest.raises(ValueError, match="source_line_index_does_not_match_sheet"):
        box_correspondence(box, **kwargs, _target_index=LineIndex(support))
    assert repr((support, target, box)) == before


def test_producer_reuses_two_source_side_indexes_for_complete_many_box_universe(monkeypatch):
    # Registration and null sampling build their own two indexes. The
    # producer must build only TWO additional sheet-bound side indexes,
    # regardless of how many physical floor boxes are evaluated.
    import pb_source_cross_view_floor_correspondence_shadow as source_module

    original_index = source_module.LineIndex
    indexed_sheets = []

    class CountingIndex(original_index):
        def __init__(self, lines):
            indexed_sheets.append(id(lines))
            super().__init__(lines)

    monkeypatch.setattr(source_module, "LineIndex", CountingIndex)
    boxes = [{
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-room-office",
        "source_room_face_record_id": "face-office",
    }]
    boxes.extend({
        "dimension_box_pdf_pts": (
            3000.0 + 120.0 * i, 3000.0,
            3080.0 + 120.0 * i, 3090.0,
        ),
        "canonical_floor_id": f"far-floor-{i}",
        "physical_room_id": f"far-room-{i}",
        "source_room_face_record_id": f"far-face-{i}",
    } for i in range(256))
    marks = [{
        "x": 327.8, "y": 1437.5, "code": "FT3",
        "registered_region": True,
    }]
    before = copy.deepcopy((boxes, marks))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=boxes,
        marks=marks,
    )
    assert len(indexed_sheets) == 4
    assert indexed_sheets[2] != indexed_sheets[3]
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == len(boxes)
    assert result.records[0].status is EvidenceResolutionStatus.CANDIDATE
    assert all(
        record.status is EvidenceResolutionStatus.ABSTAINED
        for record in result.records[1:]
    )
    assert all(not record.takeoff_eligible and not record.commercial_projection_allowed
               for record in result.records)
    assert (boxes, marks) == before


# Actual-match resource accounting: source-key estimates alone cannot
# bound many target native lines inside the same 0.06pt tolerance band.
def _dense_support_lines():
    src = {
        "H": {0.0: [(0.0, 100.0)]},
        "V": {0.0: [(0.0, 100.0)]},
    }
    dst = {
        "H": {round(i * 0.01, 3): [(0.0, 100.0)] for i in range(10)},
        "V": {round(i * 0.01, 3): [(0.0, 100.0)] for i in range(10)},
    }
    return src, dst


def test_registration_budgets_actual_destination_key_matches(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    src, dst = _dense_support_lines()
    original_src, original_dst = copy.deepcopy(src), copy.deepcopy(dst)
    # Coarse preflight reserves (1 candidate + 3*25 possible refinements)
    # * 2 source keys = 152 visits. The actual one-candidate/25-refinement
    # path exceeds 200 cumulative near-key matches (and interval work).
    monkeypatch.setattr(shadow, "MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS", 200)
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        shadow.rank_registrations(
            src, dst, orientations={"identity": (1.0, 0.0, 0.0, 1.0)},
            identity_scales=(1.0,), topn=1, identity_only=True,
        )
    assert src == original_src
    assert dst == original_dst


def test_null_trials_budget_actual_destination_key_matches(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    src, dst = _dense_support_lines()
    original_src, original_dst = copy.deepcopy(src), copy.deepcopy(dst)
    monkeypatch.setattr(shadow, "MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS", 25)
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        shadow.null_support(src, dst, trials=60, span=(0.0, 0.0))
    assert src == original_src
    assert dst == original_dst


def test_null_resource_exhaustion_preserves_independent_source_negatives(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    def exhausted_null(*args, **kwargs):
        raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)

    monkeypatch.setattr(shadow, "null_support", exhausted_null)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "floor-office",
            "physical_room_id": "room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[
            {"x": 327.8, "y": 1437.5, "code": "FT3",
             "registered_region": True},
            {"x": "unlocated-original-rival", "y": 1437.5,
             "code": "FT2", "registered_region": True},
        ],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED in result.reason_codes
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.reason_codes
    assert not result.records


def test_sparse_registration_and_null_support_remain_source_only():
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    src = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
    dst = copy.deepcopy(src)
    before = copy.deepcopy((src, dst))
    result = shadow.rank_registrations(
        src, dst, orientations={"identity": (1.0, 0.0, 0.0, 1.0)},
        identity_scales=(1.0,), topn=1, identity_only=True,
    )
    assert result and result[0]["orientation"] == "identity"
    assert result[0]["scale"] == 1.0
    null = shadow.null_support(src, dst, trials=60, span=(0.0, 0.0))
    assert null["max"] == 100.0
    assert (src, dst) == before


def test_source_interval_overlap_work_budget_and_exact_positive(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    # One native key can hold many disjoint intervals. A key-only budget
    # would count a single match even though _overlap scans both lists.
    intervals = [(float(i * 2), float(i * 2 + 1)) for i in range(250)]
    src = {"H": {0.0: intervals}, "V": {0.0: intervals}}
    dst = copy.deepcopy(src)
    before = copy.deepcopy((src, dst))
    monkeypatch.setattr(shadow, "MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS", 300)
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        shadow.axis_support(src, shadow.LineIndex(dst), "H", 0.0, 0.0,
                            _visit_budget=[0])
    assert (src, dst) == before

    # With sufficient budget, no interval, overlap value or input changes.
    monkeypatch.setattr(shadow, "MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS", 100_000)
    budget = [0]
    assert shadow.axis_support(src, shadow.LineIndex(dst), "H", 0.0, 0.0,
                               _visit_budget=budget) == 250.0
    assert budget == [751]
    ranked = shadow.rank_registrations(
        src, dst, orientations={"identity": (1.0, 0.0, 0.0, 1.0)},
        identity_scales=(1.0,), topn=1, identity_only=True,
    )
    assert ranked and ranked[0]["min_support_pt"] == 250.0
    assert shadow.null_support(src, dst, trials=60, span=(0.0, 0.0))["max"] == 250.0
    assert (src, dst) == before


def test_interval_heavy_null_and_registration_abstain_before_partial_score(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as shadow

    intervals = [(float(i * 2), float(i * 2 + 1)) for i in range(250)]
    src = {"H": {0.0: intervals}, "V": {0.0: intervals}}
    dst = copy.deepcopy(src)
    before = copy.deepcopy((src, dst))
    # The coarse rank preflight is only 152 key visits, but actual
    # interval work exceeds 2,000 across the complete refinement/null run.
    monkeypatch.setattr(shadow, "MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS", 2_000)
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        shadow.rank_registrations(
            src, dst, orientations={"identity": (1.0, 0.0, 0.0, 1.0)},
            identity_scales=(1.0,), topn=1, identity_only=True,
        )
    with pytest.raises(ValueError, match=SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED):
        shadow.null_support(src, dst, trials=60, span=(0.0, 0.0))
    assert (src, dst) == before


# ==============================================================================
# Cumulative source-side diagnostic work budget (not commercial authority)
# ==============================================================================

def test_source_side_evidence_budget_counts_native_keys_and_intervals(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as cross

    lines = build_lines(room(100.0, 100.0, 300.0, 300.0))
    box = (100.0, 100.0, 300.0, 300.0)
    original = side_evidence(box, lines)
    budget = [0]
    monkeypatch.setattr(cross, "MAX_SOURCE_SIDE_EVIDENCE_VISITS", 1)
    with pytest.raises(ValueError, match=cross.SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED):
        side_evidence(box, lines, _visit_budget=budget)
    assert budget[0] > 1

    monkeypatch.setattr(cross, "MAX_SOURCE_SIDE_EVIDENCE_VISITS", 100000)
    budget = [0]
    assert side_evidence(box, lines, _visit_budget=budget) == original
    assert budget[0] > 0


def test_source_side_evidence_budget_is_cumulative_across_boxes_and_sheets(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as cross

    sup = build_lines(support_sheet())
    tgt = build_lines(TARGET_SHEET)
    box = (251.04, 1382.72, 394.80, 1585.04)
    arguments = dict(
        lines_support=sup,
        lines_target=tgt,
        orientation="identity",
        translation=TRUE_T,
        _support_index=LineIndex(sup),
        _target_index=LineIndex(tgt),
    )
    one_box_visits = [0]
    original = box_correspondence(box, **arguments)
    assert box_correspondence(box, _visit_budget=one_box_visits, **arguments) == original
    assert one_box_visits[0] > 0

    # One complete box fits, but the second box must not silently exceed
    # the shared budget. Both sheets are charged to the same counter.
    monkeypatch.setattr(cross, "MAX_SOURCE_SIDE_EVIDENCE_VISITS", one_box_visits[0] + 1)
    shared = [0]
    assert box_correspondence(box, _visit_budget=shared, **arguments) == original
    with pytest.raises(ValueError, match=cross.SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED):
        box_correspondence(box, _visit_budget=shared, **arguments)
    assert shared[0] > one_box_visits[0] + 1


@pytest.mark.parametrize("reverse", [False, True])
def test_source_side_budget_exhaustion_abstains_without_partial_records_and_keeps_negatives(
    monkeypatch, reverse,
):
    import pb_source_cross_view_floor_correspondence_shadow as cross

    monkeypatch.setattr(cross, "MAX_SOURCE_SIDE_EVIDENCE_VISITS", 1)
    support = support_sheet()
    target = TARGET_SHEET
    if reverse:
        support = list(reversed(support))
        target = list(reversed(target))
    boxes = [
        {
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "invalid trailing space ",
            "physical_room_id": "room-office",
            "source_room_face_record_id": "face-office",
        },
        {"dimension_box_pdf_pts": (1.0, 2.0, 3.0)},
    ]
    marks = [
        {"x": 327.8, "y": 1437.5, "code": "FT3", "registered_region": True},
        {"x": 327.9, "y": 1437.6, "code": None, "registered_region": True},
    ]
    before = copy.deepcopy((support, target, boxes, marks))
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support,
        target_segments=target,
        measured_boxes=boxes,
        marks=marks,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (
        cross.SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED,
        SOURCE_FINISH_MARK_IDENTITY_INVALID,
        SOURCE_MEASURED_FLOOR_BOX_INVALID,
        SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID,
    )
    assert (support, target, boxes, marks) == before


def test_source_side_budget_normal_positive_retains_candidate_and_commercial_isolation(monkeypatch):
    import pb_source_cross_view_floor_correspondence_shadow as cross

    monkeypatch.setattr(cross, "MAX_SOURCE_SIDE_EVIDENCE_VISITS", 100000)
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
        marks=[{
            "x": 327.8, "y": 1437.5, "code": "FT3",
            "registered_region": True,
        }],
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    assert result.records[0].commercial_projection_allowed is False
    assert result.records[0].takeoff_eligible is False
    assert result.records[0].authority_blockers == STANDING_AUTHORITY_BLOCKERS


@pytest.mark.parametrize(
    "refined_rival, expected_best, expected_second",
    [
        (99.0, 100.0, 99.0),   # A nearly equal rival must veto unique ownership.
        (120.0, 120.0, 100.0), # Refined rival becomes winner; old best is rival.
        (30.0, 100.0, 79.0),   # Weaker refinement cannot erase raw rival.
    ],
)
def test_registration_retains_refined_distinct_translation_rivals(
    monkeypatch, refined_rival, expected_best, expected_second,
):
    """Every evaluated source-wall refinement competes for physical identity.

    Previously the best translation was refined, but next_distinct_translation
    was selected from the stale initial pool only. A source room with another
    locally improving placement could therefore appear uniquely registered.
    This test controls support scores, not any benchmark or original drawing.
    """
    import pb_source_cross_view_floor_correspondence_shadow as floor_shadow

    source = build_lines([seg(0, 0, 100, 0), seg(0, 0, 0, 100)])
    target = build_lines([seg(0, 0, 100, 0), seg(0, 0, 0, 100)])
    source_before = copy.deepcopy(source)
    target_before = copy.deepcopy(target)

    def two_source_translations(*args, **kwargs):
        return [0.0, 10.0], [0.0]

    def measured_support(src, dst, dx, dy, tol=0.06, *, _visit_budget=None):
        if abs(dy) < 1e-9 and abs(dx) < 1e-9:
            score = 100.0
        elif abs(dy) < 1e-9 and abs(dx - 10.04) < 1e-9:
            score = refined_rival
        elif abs(dy) < 1e-9 and abs(dx - 10.0) < 1e-9:
            score = 79.0
        else:
            score = 0.0
        return score, score, score

    monkeypatch.setattr(floor_shadow, "_shift_votes", two_source_translations)
    monkeypatch.setattr(floor_shadow, "min_axis_support", measured_support)
    result = floor_shadow.rank_registrations(
        source, target,
        orientations={"identity": (1.0, 0.0, 0.0, 1.0)},
        identity_scales=(1.0,),
        identity_only=True,
        topn=2,
    )

    assert len(result) == 1
    row = result[0]
    assert row["orientation"] == "identity"
    assert row["scale"] == 1.0
    assert row["min_support_pt"] == expected_best
    assert row["next_distinct_min_support_pt"] == expected_second
    if refined_rival == 99.0:
        assert not (row["min_support_pt"] > 1.25 * row["next_distinct_min_support_pt"])
    assert source == source_before
    assert target == target_before
    assert "takeoff_eligible" not in row
    assert "commercial_projection_allowed" not in row
