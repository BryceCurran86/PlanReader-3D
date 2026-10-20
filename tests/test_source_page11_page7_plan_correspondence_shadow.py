"""Comprehensive unit and regression tests for pb_source_page11_page7_plan_correspondence_shadow (Item 15)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_page11_page7_plan_correspondence_shadow import (
    AMBIGUOUS_REGISTRATION_CANDIDATE,
    COMPETING_FINISH_CODES_IN_ROOM,
    DEGENERATE_ROOM_BOX_GEOMETRY,
    PAGE_PLAN_CORRESPONDENCE_RESOLVED,
    PLAN_CORRESPONDENCE_RECORD_UNAVAILABLE,
    REGISTRATION_SUPPORT_INSUFFICIENT,
    ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS,
    WALL_EVIDENCE_MISMATCH_ACROSS_SHEETS,
    SourcePagePlanCorrespondenceAuthority,
    SourcePagePlanCorrespondenceProducer,
    SourcePagePlanCorrespondenceRecord,
    SourcePagePlanCorrespondenceSelector,
)

DOC = "doc-maryborough"
REV = "rev-001"
SHA = "b" * 64
SNAP = "snap-001"
SUP_PAGE = "11"
TGT_PAGE = "7"
SCOPE = "wall-source:page-11"
ROOM = "OFFICE"


def _make_selector(room: str = ROOM) -> SourcePagePlanCorrespondenceSelector:
    return SourcePagePlanCorrespondenceSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        support_page_id=SUP_PAGE,
        target_page_id=TGT_PAGE,
        decision_scope_id=SCOPE,
        room_name=room,
    )


def _make_synthetic_walled_room(
    box: tuple[float, float, float, float] = (100.0, 100.0, 250.0, 300.0),
    wall_thickness: float = 10.0,
    dx: float = 0.0,
    dy: float = 0.0,
) -> list[dict[str, float]]:
    """Create inner face and outer face linework for a 4-walled rectangular room."""
    x0, y0, x1, y1 = (v + dx if i % 2 == 0 else v + dy for i, v in enumerate(box))
    segs = []
    # Inner face lines
    segs.append({"x1": x0, "y1": y0, "x2": x0, "y2": y1})  # Left inner
    segs.append({"x1": x1, "y1": y0, "x2": x1, "y2": y1})  # Right inner
    segs.append({"x1": x0, "y1": y0, "x2": x1, "y2": y0})  # Bottom inner
    segs.append({"x1": x0, "y1": y1, "x2": x1, "y2": y1})  # Top inner

    # Outer face lines (separated by wall_thickness)
    segs.append({"x1": x0 - wall_thickness, "y1": y0 - wall_thickness, "x2": x0 - wall_thickness, "y2": y1 + wall_thickness})
    segs.append({"x1": x1 + wall_thickness, "y1": y0 - wall_thickness, "x2": x1 + wall_thickness, "y2": y1 + wall_thickness})
    segs.append({"x1": x0 - wall_thickness, "y1": y0 - wall_thickness, "x2": x1 + wall_thickness, "y2": y0 - wall_thickness})
    segs.append({"x1": x0 - wall_thickness, "y1": y1 + wall_thickness, "x2": x1 + wall_thickness, "y2": y1 + wall_thickness})

    # Add extra context linework so registration support is robust (> 1000 pt)
    segs.append({"x1": x0, "y1": y0 + 350.0, "x2": x0 + 600.0, "y2": y0 + 350.0})
    segs.append({"x1": x0, "y1": y0 + 360.0, "x2": x0 + 600.0, "y2": y0 + 360.0})
    segs.append({"x1": x0 + 600.0, "y1": y0, "x2": x0 + 600.0, "y2": y0 + 500.0})
    segs.append({"x1": x0 + 610.0, "y1": y0, "x2": x0 + 610.0, "y2": y0 + 500.0})

    return segs


def test_positive_page11_to_page7_room_correspondence() -> None:
    selector = _make_selector()
    producer = SourcePagePlanCorrespondenceProducer.create()

    box_p11 = (100.0, 100.0, 250.0, 300.0)
    # Page 7 is translated by (-78.0, 0.0) relative to page 11
    shift_x = -78.0
    shift_y = 0.0

    segs_p11 = _make_synthetic_walled_room(box_p11, dx=0.0, dy=0.0)
    segs_p7 = _make_synthetic_walled_room(box_p11, dx=shift_x, dy=shift_y)

    plan_marks = [{"code": "FT3", "pos": (150.0, 180.0)}]  # inside box_p11

    res = producer.evaluate_and_publish(
        selector,
        support_segments=segs_p11,
        target_segments=segs_p7,
        room_box_support=box_p11,
        plan_marks=plan_marks,
        expected_finish_code="FT3",
        min_registration_support=500.0,
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert PAGE_PLAN_CORRESPONDENCE_RESOLVED in res.reason_codes
    assert res.record is not None

    rec = res.record
    assert rec.room_name == ROOM
    assert rec.orientation == "identity"
    assert rec.scale == 1.0
    assert rec.translation == pytest.approx((-78.0, 0.0), abs=0.1)
    assert rec.wall_bounded_both_sheets is True
    assert rec.wall_evidence_identical is True
    assert rec.contained_finish_marks == ("FT3",)
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False


def test_open_plan_room_fails_wall_bounded_gate() -> None:
    selector = _make_selector("FOOD_PREP")
    producer = SourcePagePlanCorrespondenceProducer.create()

    box_p11 = (100.0, 100.0, 250.0, 300.0)
    # Missing x1 wall (open plan zone)
    segs_p11 = _make_synthetic_walled_room(box_p11)
    segs_p11 = [s for s in segs_p11 if s["x1"] != 250.0 and s["x2"] != 250.0]
    segs_p7 = _make_synthetic_walled_room(box_p11, dx=-78.0)
    segs_p7 = [s for s in segs_p7 if s["x1"] != (250.0 - 78.0) and s["x2"] != (250.0 - 78.0)]

    res = producer.evaluate_and_publish(
        selector,
        support_segments=segs_p11,
        target_segments=segs_p7,
        room_box_support=box_p11,
        min_registration_support=500.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS in res.reason_codes
    assert res.record is None


def test_wall_evidence_mismatch_across_sheets() -> None:
    selector = _make_selector("OFFICE_MODIFIED")
    producer = SourcePagePlanCorrespondenceProducer.create()

    box_p11 = (100.0, 100.0, 250.0, 300.0)
    segs_p11 = _make_synthetic_walled_room(box_p11)

    # On page 7, create a substantial opening in y1 that doesn't exist on p11
    segs_p7 = _make_synthetic_walled_room(box_p11, dx=-78.0)
    segs_p7 = [s for s in segs_p7 if not (s.get("y1") == 300.0 and s.get("y2") == 300.0)]
    # Add a short partial stub
    segs_p7.append({"x1": 100.0 - 78.0, "y1": 300.0, "x2": 130.0 - 78.0, "y2": 300.0})

    res = producer.evaluate_and_publish(
        selector,
        support_segments=segs_p11,
        target_segments=segs_p7,
        room_box_support=box_p11,
        min_registration_support=500.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert (
        WALL_EVIDENCE_MISMATCH_ACROSS_SHEETS in res.reason_codes
        or ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS in res.reason_codes
    )


def test_competing_finish_codes_rejected() -> None:
    selector = _make_selector("COLD_ROOM")
    producer = SourcePagePlanCorrespondenceProducer.create()

    box_p11 = (100.0, 100.0, 250.0, 300.0)
    segs_p11 = _make_synthetic_walled_room(box_p11)
    segs_p7 = _make_synthetic_walled_room(box_p11, dx=-78.0)

    # Box has FT3 expected, but contains competing EPX mark
    plan_marks = [{"code": "EPX", "pos": (150.0, 180.0)}]

    res = producer.evaluate_and_publish(
        selector,
        support_segments=segs_p11,
        target_segments=segs_p7,
        room_box_support=box_p11,
        plan_marks=plan_marks,
        expected_finish_code="FT3",
        min_registration_support=500.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert COMPETING_FINISH_CODES_IN_ROOM in res.reason_codes
    assert res.record is None


def test_insufficient_registration_support_rejected() -> None:
    selector = _make_selector()
    producer = SourcePagePlanCorrespondenceProducer.create()

    # Empty segments
    res = producer.evaluate_and_publish(
        selector,
        support_segments=[],
        target_segments=[],
        room_box_support=(100.0, 100.0, 250.0, 300.0),
        min_registration_support=1000.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert REGISTRATION_SUPPORT_INSUFFICIENT in res.reason_codes


def test_degenerate_room_box_geometry_rejected() -> None:
    selector = _make_selector()
    producer = SourcePagePlanCorrespondenceProducer.create()

    # x0 >= x1
    res = producer.evaluate_and_publish(
        selector,
        support_segments=[],
        target_segments=[],
        room_box_support=(250.0, 100.0, 100.0, 300.0),
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert DEGENERATE_ROOM_BOX_GEOMETRY in res.reason_codes


def test_authority_lookup_and_unknown_selector() -> None:
    selector = _make_selector("OFFICE")
    producer = SourcePagePlanCorrespondenceProducer.create()

    box_p11 = (100.0, 100.0, 250.0, 300.0)
    segs_p11 = _make_synthetic_walled_room(box_p11)
    segs_p7 = _make_synthetic_walled_room(box_p11, dx=-78.0)

    producer.evaluate_and_publish(
        selector,
        support_segments=segs_p11,
        target_segments=segs_p7,
        room_box_support=box_p11,
        min_registration_support=500.0,
    )

    auth = producer.authority()
    assert type(auth) is SourcePagePlanCorrespondenceAuthority

    res_known = auth.resolve(selector)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert res_known.record is not None

    unknown_sel = _make_selector("UNKNOWN_ROOM")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert PLAN_CORRESPONDENCE_RECORD_UNAVAILABLE in res_unknown.reason_codes


def test_sealed_record_and_authority_forbids_direct_construction() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SourcePagePlanCorrespondenceRecord(
            record_id="r1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            support_page_id=SUP_PAGE,
            target_page_id=TGT_PAGE,
            decision_scope_id=SCOPE,
            room_name=ROOM,
            box_support_sheet=(0.0, 0.0, 10.0, 10.0),
            box_target_sheet=(0.0, 0.0, 10.0, 10.0),
            orientation="identity",
            scale=1.0,
            translation=(0.0, 0.0),
            min_support_pt=100.0,
            wall_bounded_both_sheets=True,
            wall_evidence_identical=True,
            contained_finish_marks=(),
            side_coverage_summary={},
            corroborating_evidence_ids=(),
        )

    with pytest.raises(TypeError, match="producer-owned"):
        SourcePagePlanCorrespondenceAuthority({})

    with pytest.raises(TypeError, match="create()"):
        SourcePagePlanCorrespondenceProducer()
