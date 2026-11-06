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
    SOURCE_FINISH_PAGE_CORRESPONDENCE_UNVERIFIED,
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
        page_id="page_11",
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
    mark = SourceFloorFinishMark("OCC_1", "page_11", "FT2", (5.0, 5.0))

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

    mark = SourceFloorFinishMark("OCC_1", "page_11", "FT2", (5.0, 5.0))
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
    mark = SourceFloorFinishMark("OCC_1", "page_11", "FT2", (150.0, 200.0))
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

def test_cross_sheet_mark_same_coordinates_abstains_without_registration():
    polygon = [(100.,100.),(200.,100.),(200.,300.),(100.,300.)]
    selector = SourceFloorFinishOwnershipSelector(
        "doc", "rev", VALID_SHA, "snap", "page_07", "OFFICE", "FT3"
    )
    foreign = SourceFloorFinishMark("OCC_FT3_P11","page_11","FT3",(150.,200.))
    blocked = evaluate_source_floor_finish_ownership_shadow(
        selector, finish_mark=foreign, internal_face_polygon_pdf_pts=polygon,
    )
    assert blocked.status == EvidenceResolutionStatus.ABSTAINED
    assert blocked.reason_codes == (SOURCE_FINISH_PAGE_CORRESPONDENCE_UNVERIFIED,)
    assert blocked.record is None
    local = evaluate_source_floor_finish_ownership_shadow(
        selector, finish_mark=SourceFloorFinishMark(
            "OCC_FT3_P7","page_07","FT3",(150.,200.)
        ), internal_face_polygon_pdf_pts=polygon,
    )
    assert local.status == EvidenceResolutionStatus.CANDIDATE
    assert local.record.page_id == "page_07"
    assert local.record.takeoff_eligible is False
    assert local.record.commercial_projection_allowed is False
    assert local.record.terminates_at_internal_faces is False


def test_foreign_page_competitor_abstains_in_all_orders():
    polygon = [(100.,100.),(200.,100.),(200.,300.),(100.,300.)]
    primary = SourceFloorFinishMark("FT2_PRIMARY","page_11","FT2",(150.,200.))
    foreign = SourceFloorFinishMark("FT3_FOREIGN","page_07","FT3",(160.,210.))
    for rivals in ((foreign,), (foreign, primary), (primary, foreign)):
        result = evaluate_source_floor_finish_ownership_shadow(
            _selector(), finish_mark=primary,
            internal_face_polygon_pdf_pts=polygon, other_finish_marks=rivals,
        )
        assert result.status == EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (SOURCE_FINISH_PAGE_CORRESPONDENCE_UNVERIFIED,)
        assert result.record is None


def test_blank_page_and_invalid_competitor_fail_closed():
    with pytest.raises(ValueError, match="page_id"):
        SourceFloorFinishMark("FT2","","FT2",(150.,200.))
    result = evaluate_source_floor_finish_ownership_shadow(
        _selector(), finish_mark=SourceFloorFinishMark(
            "FT2","page_11","FT2",(150.,200.)
        ), internal_face_polygon_pdf_pts=[
            (100.,100.),(200.,100.),(200.,300.),(100.,300.)
        ], other_finish_marks=(None,),
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_LINEAGE_MISMATCH,)
    assert result.record is None


def test_private_original_ft3_mark_cannot_claim_unregistered_floor_page():
    """Original page-11 FT3 glyph is never a page-7 floor owner by equal XY.

    Source-private negative only: it does not authenticate a cross-page transform,
    physical wall faces, doorway threshold, finish definition, or FIRM quantities.
    """
    import hashlib
    import os
    from pathlib import Path
    from dataclasses import replace

    source = Path(os.getenv(
        "PLANREADER_MARYBOROUGH_ORIGINAL_PDF",
        "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
    ))
    if not source.is_file():
        pytest.skip("private original not provisioned: source check NOT VERIFIED")
    content = source.read_bytes()
    original_sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    assert len(content) == 5709675
    assert hashlib.sha256(content).hexdigest() == original_sha
    fitz = pytest.importorskip("fitz")
    with fitz.open(stream=content, filetype="pdf") as pdf:
        assert len(pdf) == 31
        page_7_ft3 = [
            w for w in pdf[6].get_text("words")
            if w[4].strip().upper() == "FT3"
        ]
        page_11_ft3 = [
            w for w in pdf[10].get_text("words")
            if w[4].strip().upper() == "FT3"
        ]
    assert not page_7_ft3
    assert page_11_ft3  # Genuine source glyph, not a synthetic FT3 label.
    source_word = page_11_ft3[0]
    mark = SourceFloorFinishMark(
        occurrence_id="original_private_p11_ft3",
        page_id="page_11",
        material_code="FT3",
        mark_center_pt=(
            (source_word[0] + source_word[2]) / 2,
            (source_word[1] + source_word[3]) / 2,
        ),
        source_word_address=tuple(int(v) for v in source_word[5:8]),
    )
    floor_selector = replace(
        _selector(material_code="FT3", source_sha256=original_sha),
        page_id="page_07",
    )
    result = evaluate_source_floor_finish_ownership_shadow(
        floor_selector,
        finish_mark=mark,
        internal_face_polygon_pdf_pts=(),  # No cross-page registration supplied.
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        SOURCE_FINISH_PAGE_CORRESPONDENCE_UNVERIFIED,
    )
    assert result.record is None


def test_native_floor_finish_word_address_and_glyph_location_are_in_receipt_identity():
    """Distinct native observations must not hash into the same source receipt."""
    from dataclasses import replace

    polygon = ((100.0, 100.0), (300.0, 100.0),
               (300.0, 300.0), (100.0, 300.0))
    mark = SourceFloorFinishMark(
        "OCC_FT3", "page_11", "FT3", (150.0, 150.0), (113, 0, 0)
    )
    selector = _selector(material_code="FT3")

    def record_for(candidate, transitions=()):
        result = evaluate_source_floor_finish_ownership_shadow(
            selector,
            finish_mark=candidate,
            internal_face_polygon_pdf_pts=polygon,
            doorway_transitions=transitions,
        )
        assert result.status == EvidenceResolutionStatus.CANDIDATE
        assert result.record is not None
        assert result.record.commercial_projection_allowed is False
        assert result.record.takeoff_eligible is False
        return result.record

    baseline = record_for(mark)
    replay = record_for(mark)
    new_address = record_for(replace(mark, source_word_address=(113, 1, 0)))
    new_position = record_for(replace(mark, mark_center_pt=(155.0, 155.0)))
    assert baseline.record_id == replay.record_id
    assert len({baseline.record_id, new_address.record_id, new_position.record_id}) == 3
    assert baseline.internal_floor_area_sq_pt == new_address.internal_floor_area_sq_pt
    assert baseline.internal_floor_area_sq_pt == new_position.internal_floor_area_sq_pt

    aligned = SourceDoorwayThreshold("D13", (100.0, 100.0), (200.0, 100.0))
    misaligned = SourceDoorwayThreshold("D13", (20.0, 20.0), (50.0, 20.0))
    aligned_record = record_for(mark, (aligned,))
    misaligned_record = record_for(mark, (misaligned,))
    assert aligned_record.record_id != misaligned_record.record_id
    assert aligned_record.record_id != baseline.record_id
    assert misaligned_record.record_id != baseline.record_id


@pytest.mark.parametrize("address", [
    None, (), (0, 0), (0, 0, -1), (True, 0, 0), (0.0, 0, 0),
    [0, 0, 0], "113,0,0", (0, 0, 0, 0),
])
def test_invalid_native_word_address_rejected_before_receipt_hash(address):
    with pytest.raises(ValueError, match="source_word_address"):
        SourceFloorFinishMark("OCC", "page_11", "FT3", (10.0, 10.0), address)


@pytest.mark.parametrize("conflict_code,other_center,other_word", [
    ("FT2", (145.0, 145.0), (12, 0, 2)),
    ("FT3", (145.0, 145.0), (12, 0, 2)),
    ("FT2", (250.0, 250.0), (12, 0, 2)),
    ("FT2", (100.0, 100.0), (12, 0, 1)),
])
def test_direct_finish_evaluator_does_not_skip_distinct_reused_occurrence(
    conflict_code, other_center, other_word,
):
    """One repeated source occurrence cannot masquerade as an identical mark."""
    from dataclasses import replace

    poly = ((0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0))
    mark = SourceFloorFinishMark(
        "NATIVE_O1", "page_11", "FT2", (100.0, 100.0), (12, 0, 0)
    )
    rival = replace(
        mark, material_code=conflict_code, mark_center_pt=other_center,
        source_word_address=other_word,
    )
    assert rival is not mark and rival.occurrence_id == mark.occurrence_id
    before = copy.deepcopy((mark, rival, poly))
    for others in ((mark, rival), (rival, mark)):
        result = evaluate_source_floor_finish_ownership_shadow(
            _selector(material_code="FT2"),
            finish_mark=mark,
            internal_face_polygon_pdf_pts=poly,
            other_finish_marks=others,
        )
        assert result.status == EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (SOURCE_LINEAGE_MISMATCH,)
        assert result.record is None
    assert (mark, rival, poly) == before
    # The single exact observation is allowed as "self" in the complete
    # source candidate list; it remains diagnostic, never a FIRM quantity.
    control = evaluate_source_floor_finish_ownership_shadow(
        _selector(material_code="FT2"),
        finish_mark=mark,
        internal_face_polygon_pdf_pts=poly,
        other_finish_marks=(mark,),
    )
    assert control.status == EvidenceResolutionStatus.CANDIDATE
    assert control.record is not None
    assert control.record.takeoff_eligible is False
    assert control.record.commercial_projection_allowed is False
