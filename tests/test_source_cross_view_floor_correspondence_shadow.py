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
    COMPETING_FINISH_CODES_IN_BOX,
    NO_FINISH_MARK_IN_BOX,
    BOX_OWNED_BY_OTHER_FINISH_CODE,
    MARK_TOO_CLOSE_TO_BOX_SIDE,
    MARK_IN_UNREGISTERED_REGION,
    OVERLAPPING_MEASURED_BOXES,
    REGISTRATION_NOT_UNIQUE,
    STANDING_AUTHORITY_BLOCKERS,
    SOURCE_FINISH_MARK_IDENTITY_INVALID,
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


# Fresh-main GPT2 source-mark integrity: no source evidence is manufactured.
def _source_complete_correspondence():
    return {
        "wall_bounded_on_both_sheets": True,
        "wall_evidence_identical_on_both_sheets": True,
    }


def _source_complete_mark():
    return {"code": "FT3", "margin_pt": 8.0, "registered_region": True}


def test_one_explicit_source_registered_ft3_remains_candidate_only():
    result = classify_floor(
        _source_complete_correspondence(),
        registration_unique=True, marks_inside=[_source_complete_mark()],
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    assert result["status"] is EvidenceResolutionStatus.CANDIDATE
    assert result["authenticated_physical_wall_face_equivalence"] is False


@pytest.mark.parametrize("marks", [
    [_source_complete_mark(), _source_complete_mark()],
    [{**_source_complete_mark(), "registered_region": None}],
    [{k: v for k, v in _source_complete_mark().items()
      if k != "registered_region"}],
    [{**_source_complete_mark(), "registered_region": "True"}],
    [{**_source_complete_mark(), "margin_pt": float("nan")}],
    [{**_source_complete_mark(), "margin_pt": float("inf")}],
    [{**_source_complete_mark(), "margin_pt": None}],
    [{**_source_complete_mark(), "margin_pt": True}],
    [{**_source_complete_mark(), "code": " FT3 "}],
    [{"code": "FT3", "margin_pt": 8., "registered_region": True},
     {"code": "FT2", "margin_pt": 8., "registered_region": True}],
])
def test_ambiguous_duplicate_or_unregistered_source_ft_mark_cannot_be_candidate(marks):
    result = classify_floor(
        _source_complete_correspondence(),
        registration_unique=True, marks_inside=marks,
        other_labelled_boxes_overlapping=0, material_code="FT3",
    )
    assert result["status"] in (
        EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT,
    )
    assert result["authority_blockers"] == ()
    assert not result["authenticated_physical_wall_face_equivalence"]


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"identity_ambiguous": True}, "duplicate_physical_floor_identity"),
    ({"identity_missing": True}, "missing_physical_floor_identity"),
    ({"registration_unique": 1}, REGISTRATION_NOT_UNIQUE),
    ({"min_margin_pt": float("nan")}, MARK_TOO_CLOSE_TO_BOX_SIDE),
    ({"min_margin_pt": -1.0}, MARK_TOO_CLOSE_TO_BOX_SIDE),
])
def test_original_finish_source_identity_and_threshold_inputs_fail_closed(kwargs, reason):
    args = {
        "registration_unique": True,
        "marks_inside": [_source_complete_mark()],
        "other_labelled_boxes_overlapping": 0,
        "material_code": "FT3",
    }
    args.update(kwargs)
    result = classify_floor(_source_complete_correspondence(), **args)
    assert result["status"] is EvidenceResolutionStatus.ABSTAINED
    assert reason in result["reason_codes"]


def test_duplicated_ft3_marks_abstain_through_real_source_shadow_producer():
    selector = sample_selector()
    prod = SourceCrossViewFloorCorrespondenceProducer()
    marks = [
        {"x": 327.8, "y": 1437.5, "code": "FT3",
         "registered_region": True},
        {"x": 350.0, "y": 1450.0, "code": "FT3",
         "registered_region": True},
    ]
    result = prod.evaluate_synthetic(
        selector=selector, support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=marks,
    )
    assert result.records
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert "multiple_same_code_finish_marks_in_box" in result.records[0].reason_codes
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert not any(rec.takeoff_eligible for rec in result.records)


def test_missing_registered_region_propagates_abstain_to_source_shadow_collection():
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(),
        support_segments=support_sheet(), target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "canonical-floor-office",
            "physical_room_id": "physical-room-office",
            "source_room_face_record_id": "face-office",
        }],
        marks=[{"x": 327.8, "y": 1437.5, "code": "FT3"}],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert MARK_IN_UNREGISTERED_REGION in result.records[0].reason_codes



def test_original_physical_room_identity_collision_abstains_both_floor_boxes():
    measured = [{
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-office",
        "source_room_face_record_id": "face-office",
    }]
    # Disjoint boxes cannot both claim ONE underlying original physical room.
    second = dict(measured[0])
    second["dimension_box_pdf_pts"] = (418.5, 1390., 638.2, 1600.)
    second["canonical_floor_id"] = "second-canonical-floor"
    second["source_room_face_record_id"] = "second-face"
    measured.append(second)
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=support_sheet(),
        target_segments=TARGET_SHEET, measured_boxes=measured,
        marks=[{
            "x": 327.8, "y": 1437.5, "code": "FT3",
            "registered_region": True,
        }],
    )
    assert len(result.records) == 2
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in result.records)
    assert all("duplicate_physical_floor_identity" in r.reason_codes for r in result.records)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert all(r.commercial_projection_allowed is False for r in result.records)


@pytest.mark.parametrize(("field", "invalid"), [
    ("canonical_floor_id", None),
    ("physical_room_id", 1234),
    ("source_room_face_record_id", ""),
    ("physical_room_id", " physical-office "),
    ("source_room_face_record_id", True),
])
def test_missing_or_coerced_original_physical_source_identity_abstains(
    field, invalid,
):
    box = {
        "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
        "canonical_floor_id": "canonical-floor-office",
        "physical_room_id": "physical-office",
        "source_room_face_record_id": "face-office",
    }
    box[field] = invalid
    result = SourceCrossViewFloorCorrespondenceProducer().evaluate_synthetic(
        selector=sample_selector(), support_segments=support_sheet(),
        target_segments=TARGET_SHEET, measured_boxes=[box],
        marks=[{
            "x": 327.8, "y": 1437.5, "code": "FT3",
            "registered_region": True,
        }],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 1
    assert result.records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert "missing_physical_floor_identity" in result.records[0].reason_codes



@pytest.mark.parametrize("bad_mark", [
    {"x": float("nan"), "y": 100., "code": "FT2"},
    {"x": float("inf"), "y": 100., "code": "FT2"},
    {"x": True, "y": 100., "code": "FT2"},
    {"x": "500", "y": 100., "code": "FT2"},
    {"x": 2**54, "y": 100., "code": "FT2"},
    {"x": 500., "y": 100., "code": " FT2 "},
    {"x": 500., "y": 100., "code": None},
    {"y": 100., "code": "FT2"},
    "malformed-original-observation",
])
def test_foreign_invalid_source_mark_cannot_leave_ft3_uniquely_registered(
    bad_mark,
):
    # Invalid competing source evidence is not silently omitted merely
    # because a second original FT3 glyph remains inside the target box.
    valid = {"x": 327.8, "y": 1437.5,
             "code": "FT3", "registered_region": True}
    producer = SourceCrossViewFloorCorrespondenceProducer()
    result = producer.evaluate_synthetic(
        selector=sample_selector(), support_segments=support_sheet(),
        target_segments=TARGET_SHEET,
        measured_boxes=[{
            "dimension_box_pdf_pts": (251.04, 1382.72, 394.80, 1585.04),
            "canonical_floor_id": "floor-office",
            "physical_room_id": "physical-office",
            "source_room_face_record_id": "w4-office",
        }],
        marks=[valid, bad_mark],
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FINISH_MARK_IDENTITY_INVALID in result.reason_codes
    assert result.records == ()
