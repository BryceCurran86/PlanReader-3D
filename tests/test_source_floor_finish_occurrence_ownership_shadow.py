"""Tests for producer-owned source floor finish occurrence and physical floor ownership shadow authority (Item 14)."""

from __future__ import annotations

import copy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_finish_occurrence_ownership_shadow import (
    COMPETING_FINISH_CODES_IN_ROOM,
    COMPETING_FINISH_MARKS_IN_ROOM,
    DOORWAY_THRESHOLD_GEOMETRY_ALIGNED_UNAUTHENTICATED,
    DOORWAY_TRANSITION_MISALIGNED,
    FINISH_MATERIAL_CODE_MISMATCH,
    INVALID_ROOM_POLYGON,
    MARK_NOT_IN_ROOM_POLYGON,
    MARK_TOO_CLOSE_TO_WALL_FACE,
    SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE,
    SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED,
    SOURCE_LINEAGE_MISMATCH,
    SourceDoorwayThreshold,
    SourceFloorFinishMark,
    SourceFloorFinishOwnershipRecord,
    SourceFloorFinishOwnershipResult,
    SourceFloorFinishOwnershipSelector,
    evaluate_source_floor_finish_ownership_shadow,
)

VALID_SHA = "b" * 64


def _selector(
    room_id: str = "ROOM_PWD",
    material_code: str = "FT2",
    source_sha256: str = VALID_SHA,
) -> SourceFloorFinishOwnershipSelector:
    return SourceFloorFinishOwnershipSelector(
        document_id="doc_maryborough",
        revision_id="rev_01",
        source_sha256=source_sha256,
        snapshot_id="snap_01",
        page_id="page_07",
        room_id=room_id,
        material_code=material_code,
    )


def test_positive_ft2_floor_finish_ownership_in_pwd():
    """Authentic FT2 mark cleanly enclosed in PWD internal wall face polygon."""
    # Room polygon: 100 x 200 pt
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    # Mark in center (150, 200) -> 50 pt from closest wall, clearance passes
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_PWD",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(150.0, 200.0),
        source_word_address=(56, 0, 0),
    )
    doorway = SourceDoorwayThreshold("DOOR_D13", (100.0, 300.0), (150.0, 300.0))

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[doorway],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED in res.reason_codes
    assert SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE in res.reason_codes

    record = res.record
    assert isinstance(record, SourceFloorFinishOwnershipRecord)
    assert record.material_code == "FT2"
    assert record.occurrence_id == "OCC_FT2_PWD"
    assert record.terminates_at_internal_faces is False
    assert record.under_wall_finish_excluded is False
    assert record.doorway_transition_authenticated is False
    assert DOORWAY_THRESHOLD_GEOMETRY_ALIGNED_UNAUTHENTICATED in record.reason_codes
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
    assert record.diagnostic_only is True


def test_positive_ft3_floor_finish_ownership_in_office():
    """Authentic FT3 mark cleanly enclosed in OFFICE internal wall face polygon."""
    poly = [(300.0, 100.0), (500.0, 100.0), (500.0, 400.0), (300.0, 400.0)]
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT3_OFFICE",
        page_id="page_11",
        material_code="FT3",
        mark_center_pt=(400.0, 250.0),
        source_word_address=(113, 0, 0),
    )
    doorway = SourceDoorwayThreshold("DOOR_D07", (300.0, 400.0), (380.0, 400.0))

    sel = _selector("ROOM_OFFICE", "FT3")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[doorway],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED in res.reason_codes
    assert res.record.material_code == "FT3"


def test_negative_mark_not_in_room_polygon():
    """Mark located outside the room internal face polygon fails closed."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    # Mark at (250, 200) - outside the room
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_OUTSIDE",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(250.0, 200.0),
    )

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert MARK_NOT_IN_ROOM_POLYGON in res.reason_codes
    assert res.record is None


def test_negative_mark_too_close_to_wall_face():
    """Mark located within 1.0 pt of wall face fails closed on ambiguous boundary clearance."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    # Mark at (101.0, 200.0) -> only 1.0 pt from left wall edge at x=100.0 (less than 2.5 pt tolerance)
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_EDGE",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(101.0, 200.0),
    )

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert MARK_TOO_CLOSE_TO_WALL_FACE in res.reason_codes
    assert res.record is None


def test_conflict_competing_finish_codes_in_same_room():
    """An FT2 and FT3 mark located in the same room polygon conflicts."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark_ft2 = SourceFloorFinishMark(
        occurrence_id="OCC_FT2",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(150.0, 200.0),
    )
    mark_ft3 = SourceFloorFinishMark(
        occurrence_id="OCC_FT3_COMPETITOR",
        page_id="page_11",
        material_code="FT3",
        mark_center_pt=(160.0, 220.0),
    )

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark_ft2,
        internal_face_polygon_pdf_pts=poly,
        other_finish_marks=[mark_ft3],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert COMPETING_FINISH_CODES_IN_ROOM in res.reason_codes
    assert res.record is None


def test_conflict_duplicate_same_code_marks_in_same_room():
    """Multiple marks of the same finish code without multi-bay zoning conflicts."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark1 = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_1",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(130.0, 200.0),
    )
    mark2 = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_2",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(170.0, 200.0),
    )

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark1,
        internal_face_polygon_pdf_pts=poly,
        other_finish_marks=[mark2],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert COMPETING_FINISH_MARKS_IN_ROOM in res.reason_codes
    assert res.record is None


def test_negative_material_code_mismatch():
    """Selector queried for FT2 but mark carries FT3 fails closed."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT3",
        page_id="page_11",
        material_code="FT3",
        mark_center_pt=(150.0, 200.0),
    )

    sel = _selector("ROOM_PWD", "FT2")  # Queried FT2 but mark is FT3
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert FINISH_MATERIAL_CODE_MISMATCH in res.reason_codes
    assert res.record is None


def test_negative_invalid_polygon():
    """Degenerate polygon fails closed."""
    sel = _selector()
    mark = SourceFloorFinishMark("OCC_1", "p11", "FT2", (5.0, 5.0))

    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=[(0.0, 0.0), (10.0, 0.0)],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert INVALID_ROOM_POLYGON in res.reason_codes


def test_negative_lineage_mismatch():
    """Invalid SHA or non-selector object fails closed."""
    with pytest.raises(ValueError):
        _selector(source_sha256="invalid")

    mark = SourceFloorFinishMark("OCC_1", "p11", "FT2", (5.0, 5.0))
    res = evaluate_source_floor_finish_ownership_shadow(
        None,  # type: ignore
        finish_mark=mark,
        internal_face_polygon_pdf_pts=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_LINEAGE_MISMATCH in res.reason_codes


def test_metamorphic_translation_invariance():
    """Shifting the room polygon, mark, and doorway threshold preserves floor area and validity."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_PWD",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(150.0, 200.0),
    )
    doorway = SourceDoorwayThreshold("DOOR_D13", (100.0, 300.0), (150.0, 300.0))

    sel = _selector("ROOM_PWD", "FT2")
    res1 = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[doorway],
    )
    assert res1.status == EvidenceResolutionStatus.CANDIDATE

    # Shift by dx=78.0, dy=-55.0
    dx, dy = 78.0, -55.0
    poly_shifted = [(x + dx, y + dy) for x, y in poly]
    mark_shifted = SourceFloorFinishMark(
        occurrence_id=mark.occurrence_id,
        page_id=mark.page_id,
        material_code=mark.material_code,
        mark_center_pt=(mark.mark_center_pt[0] + dx, mark.mark_center_pt[1] + dy),
    )
    doorway_shifted = SourceDoorwayThreshold(
        doorway.threshold_id,
        (doorway.start_pt[0] + dx, doorway.start_pt[1] + dy),
        (doorway.end_pt[0] + dx, doorway.end_pt[1] + dy),
    )

    res2 = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark_shifted,
        internal_face_polygon_pdf_pts=poly_shifted,
        doorway_transitions=[doorway_shifted],
    )
    assert res2.status == EvidenceResolutionStatus.CANDIDATE
    assert res1.record.internal_floor_area_sq_pt == res2.record.internal_floor_area_sq_pt
    assert res1.record.material_code == res2.record.material_code


def test_input_no_mutation():
    """Verify input collections and objects are never mutated."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark("OCC_1", "p11", "FT2", (150.0, 200.0))
    doorway = SourceDoorwayThreshold("D1", (100.0, 300.0), (150.0, 300.0))

    poly_copy = copy.deepcopy(poly)
    mark_copy = copy.deepcopy(mark)
    doorway_copy = copy.deepcopy(doorway)

    sel = _selector()
    evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[doorway],
    )

    assert poly == poly_copy
    assert mark == mark_copy
    assert doorway == doorway_copy


def test_unaligned_doorway_threshold_not_authenticated():
    """Doorway threshold distant from the room polygon boundary must not authenticate transition."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark(
        occurrence_id="OCC_FT2_PWD",
        page_id="page_11",
        material_code="FT2",
        mark_center_pt=(150.0, 200.0),
    )
    # Threshold 400 pt away from room polygon
    distant_doorway = SourceDoorwayThreshold("DOOR_DISTANT", (500.0, 500.0), (550.0, 500.0))

    sel = _selector("ROOM_PWD", "FT2")
    res = evaluate_source_floor_finish_ownership_shadow(
        sel,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[distant_doorway],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.record is not None
    assert res.record.doorway_transition_authenticated is False
    assert res.record.terminates_at_internal_faces is False
    assert res.record.under_wall_finish_excluded is False
    assert DOORWAY_TRANSITION_MISALIGNED in res.record.reason_codes
    assert DOORWAY_THRESHOLD_GEOMETRY_ALIGNED_UNAUTHENTICATED not in res.record.reason_codes


def test_overhanging_threshold_is_not_geometry_aligned_or_authenticated():
    """A chord that overhangs both ends of a finite room edge is not a doorway owner."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark("OCC_FT2_PWD", "page_11", "FT2", (150.0, 200.0))
    overhang = SourceDoorwayThreshold("DOOR_OVERHANG", (80.0, 300.0), (250.0, 300.0))
    res = evaluate_source_floor_finish_ownership_shadow(
        _selector("ROOM_PWD", "FT2"),
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[overhang],
    )
    assert res.record is not None
    assert res.record.doorway_transition_authenticated is False
    assert DOORWAY_THRESHOLD_GEOMETRY_ALIGNED_UNAUTHENTICATED not in res.record.reason_codes


def test_short_overlap_threshold_is_not_geometry_aligned_or_authenticated():
    """A mostly-external collinear chord with a tiny edge overlap is not a doorway owner."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark("OCC_FT2_PWD", "page_11", "FT2", (150.0, 200.0))
    short = SourceDoorwayThreshold("DOOR_SHORT", (195.0, 300.0), (260.0, 300.0))
    res = evaluate_source_floor_finish_ownership_shadow(
        _selector("ROOM_PWD", "FT2"),
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[short],
    )
    assert res.record is not None
    assert res.record.doorway_transition_authenticated is False
    assert DOORWAY_THRESHOLD_GEOMETRY_ALIGNED_UNAUTHENTICATED not in res.record.reason_codes


def test_forged_threshold_id_cannot_authenticate_doorway_or_faces():
    """Non-empty invented IDs are not SourceRoomFace / W4 / stroke ownership."""
    poly = [(100.0, 100.0), (200.0, 100.0), (200.0, 300.0), (100.0, 300.0)]
    mark = SourceFloorFinishMark("OCC_FT2_PWD", "page_11", "FT2", (150.0, 200.0))
    forged = SourceDoorwayThreshold("stroke_threshold_1", (100.0, 300.0), (150.0, 300.0))
    res = evaluate_source_floor_finish_ownership_shadow(
        _selector("ROOM_PWD", "FT2"),
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        doorway_transitions=[forged],
    )
    assert res.record is not None
    assert res.record.doorway_transition_authenticated is False
    assert res.record.terminates_at_internal_faces is False
    assert res.record.under_wall_finish_excluded is False
