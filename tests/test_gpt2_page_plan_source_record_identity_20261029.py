"""GPT2 producer-to-authority page-plan source claim identity regressions.

These are source-free shadow tests; no benchmark, private PDF or FIRM quantity.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_page11_page7_plan_correspondence_shadow import (
    SourcePagePlanCorrespondenceProducer,
    SourcePagePlanCorrespondenceSelector,
)


BOX = (100.0, 100.0, 250.0, 300.0)


def _selector(scope: str = "owner-wall-scope") -> SourcePagePlanCorrespondenceSelector:
    return SourcePagePlanCorrespondenceSelector(
        document_id="source-doc",
        revision_id="source-rev",
        source_sha256="b" * 64,
        snapshot_id="source-snapshot",
        support_page_id="support-page",
        target_page_id="floor-page",
        decision_scope_id=scope,
        room_name="SOURCE_ROOM",
    )


def _walled(
    box=BOX, *, shift_x=0.0, shift_y=0.0, thickness=10.0,
):
    """Two physical faces per side and independent non-grid context."""
    x0, y0, x1, y1 = box
    x0, x1 = x0 + shift_x, x1 + shift_x
    y0, y1 = y0 + shift_y, y1 + shift_y
    return [
        {"x1": x0, "y1": y0, "x2": x0, "y2": y1},
        {"x1": x1, "y1": y0, "x2": x1, "y2": y1},
        {"x1": x0, "y1": y0, "x2": x1, "y2": y0},
        {"x1": x0, "y1": y1, "x2": x1, "y2": y1},
        {"x1": x0 - thickness, "y1": y0 - thickness, "x2": x0 - thickness, "y2": y1 + thickness},
        {"x1": x1 + thickness, "y1": y0 - thickness, "x2": x1 + thickness, "y2": y1 + thickness},
        {"x1": x0 - thickness, "y1": y0 - thickness, "x2": x1 + thickness, "y2": y0 - thickness},
        {"x1": x0 - thickness, "y1": y1 + thickness, "x2": x1 + thickness, "y2": y1 + thickness},
        {"x1": x0, "y1": y0 + 350, "x2": x0 + 600, "y2": y0 + 350},
        {"x1": x0, "y1": y0 + 360, "x2": x0 + 600, "y2": y0 + 360},
        {"x1": x0 + 600, "y1": y0, "x2": x0 + 600, "y2": y0 + 500},
        {"x1": x0 + 610, "y1": y0, "x2": x0 + 610, "y2": y0 + 500},
    ]


def _evaluate(
    *, selector=None, box=BOX, thickness=10.0, mark=(150.0, 180.0),
    support_segments=None, target_segments=None, outside_marks=(),
):
    selector = _selector() if selector is None else selector
    p11 = _walled(box, thickness=thickness) if support_segments is None else support_segments
    p7 = _walled(box, shift_x=-78.0, thickness=thickness) if target_segments is None else target_segments
    marks = [{"code": "FT3", "pos": mark}]
    marks.extend({"code": "EPX", "pos": p} for p in outside_marks)
    producer = SourcePagePlanCorrespondenceProducer.create()
    res = producer.evaluate_and_publish(
        selector,
        support_segments=p11,
        target_segments=p7,
        room_box_support=box,
        plan_marks=marks,
        expected_finish_code="FT3",
        min_registration_support=500.0,
    )
    assert res.status == EvidenceResolutionStatus.CANDIDATE, res.reason_codes
    assert res.record is not None
    assert res.record.commercial_projection_allowed is False
    assert res.record.takeoff_eligible is False
    assert producer.authority().resolve(selector).record == res.record
    return res.record


def _split_segment(segment):
    """Split one native stroke without changing its physical interval union."""
    x0, y0, x1, y1 = (segment[k] for k in ("x1", "y1", "x2", "y2"))
    middle = ((x0 + x1) / 2, (y0 + y1) / 2)
    return (
        {"x1": x0, "y1": y0, "x2": middle[0], "y2": middle[1]},
        {"x1": middle[0], "y1": middle[1], "x2": x1, "y2": y1},
    )


def test_record_id_binds_decision_scope_without_granting_authority():
    first = _evaluate(selector=_selector("scope-a"))
    second = _evaluate(selector=_selector("scope-b"))
    assert first.record_id != second.record_id
    assert first.document_id == second.document_id
    assert first.box_target_sheet == second.box_target_sheet


def test_record_id_binds_distinct_source_room_face_shape():
    original = _evaluate()
    changed = _evaluate(box=(100.0, 100.0, 260.0, 300.0))
    assert original.record_id != changed.record_id
    assert original.box_target_sheet != changed.box_target_sheet


def test_record_id_binds_distinct_second_physical_wall_faces():
    original = _evaluate()
    changed = _evaluate(thickness=11.0)
    assert original.record_id != changed.record_id
    # The same candidate classification must not erase differing ink.
    assert original.side_coverage_summary == changed.side_coverage_summary


def test_record_id_binds_native_finish_mark_center_without_inventing_occurrence():
    original = _evaluate(mark=(150.0, 180.0))
    shifted = _evaluate(mark=(162.0, 192.0))
    assert original.record_id != shifted.record_id
    assert original.contained_finish_marks == shifted.contained_finish_marks == ("FT3",)


def test_deterministic_replay_input_permutation_and_native_segment_split():
    original = _evaluate()
    p11, p7 = _walled(), _walled(shift_x=-78.0)
    split_11 = [*_split_segment(p11[0]), *p11[1:]]
    split_7 = [*_split_segment(p7[0]), *p7[1:]]
    replay = _evaluate(
        support_segments=list(reversed(split_11)),
        target_segments=list(reversed(split_7)),
        outside_marks=((999.0, 999.0),),
    )
    assert original.record_id == replay.record_id
    assert original.contained_finish_marks == replay.contained_finish_marks
    assert _evaluate().record_id == original.record_id


def test_same_selector_with_different_diagnostic_claim_replaces_only_its_own_result():
    producer = SourcePagePlanCorrespondenceProducer.create()
    selector = _selector()
    marks = [{"code": "FT3", "pos": (150.0, 180.0)}]
    first = producer.evaluate_and_publish(
        selector, support_segments=_walled(),
        target_segments=_walled(shift_x=-78.0),
        room_box_support=BOX, plan_marks=marks,
        expected_finish_code="FT3", min_registration_support=500.0,
    )
    marks[0]["pos"] = (160.0, 180.0)
    second = producer.evaluate_and_publish(
        selector, support_segments=_walled(),
        target_segments=_walled(shift_x=-78.0),
        room_box_support=BOX, plan_marks=marks,
        expected_finish_code="FT3", min_registration_support=500.0,
    )
    assert first.record is not None and second.record is not None
    assert first.record.record_id != second.record.record_id
    assert producer.authority().resolve(selector).record == second.record
    assert first.record.commercial_projection_allowed is False
    assert second.record.takeoff_eligible is False
