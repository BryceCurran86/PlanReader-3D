"""Tests for source-backed room legend number-to-name linkage shadow evidence (Item 25)."""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_source_room_legend_linkage_shadow as rll
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA_1 = "c" * 64
_SHA_2 = "d" * 64


def _row(
    cells: tuple[str, ...],
    *,
    obs: str,
    page: str = "2",
    vp: str = "vp-legend",
    rev: str = "rev-1",
    sha: str = _SHA_1,
) -> rll.RoomLegendTableRowInput:
    return rll.RoomLegendTableRowInput(
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        legend_page_id=page,
        legend_viewport_id=vp,
        observation_ids=(obs,),
        cells=cells,
    )


def _rect(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _face(
    face_id: str,
    poly: tuple[tuple[float, float], ...],
    *,
    page: str = "7",
    vp: str = "vp-floor",
    rev: str = "rev-1",
    sha: str = _SHA_1,
    direct_name: str | None = None,
) -> rll.PhysicalRoomFaceCandidate:
    return rll.PhysicalRoomFaceCandidate(
        room_face_id=face_id,
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        plan_page_id=page,
        plan_viewport_id=vp,
        polygon_pdf_pts=poly,
        room_face_evidence_ids=(f"face-ev-{face_id}",),
        direct_room_name_text=direct_name,
        direct_room_name_observation_id=f"name-obs-{face_id}" if direct_name else None,
    )


def _bubble(
    cid: str,
    text: str,
    pt: tuple[float, float],
    *,
    page: str = "7",
    vp: str = "vp-floor",
    rev: str = "rev-1",
    sha: str = _SHA_1,
) -> rll.RoomNumberBubbleCandidate:
    return rll.RoomNumberBubbleCandidate(
        callout_id=cid,
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        plan_page_id=page,
        plan_viewport_id=vp,
        observation_id=f"obs-{cid}",
        raw_text=text,
        anchor_pt_pdf_pts=pt,
    )


def test_parses_tabular_and_inline_room_legends_and_rejects_door_schedules() -> None:
    rows = [
        # Door schedule MUST be ignored (never read as room legend)
        _row(("DOOR NO.", "ROOM NAME", "DOOR LEAF"), obs="r0"),
        _row(("D01", "Sales", "920"), obs="r1"),
        # Valid 2-column room legend table
        _row(("ROOM NO.", "ROOM NAME"), obs="r2"),
        _row(("01", "OFFICE"), obs="r3"),
        _row(("02", "STAFF AMENITIES"), obs="r4"),
        _row(("R03", "STORAGE"), obs="r5"),
        # Separate inline legend on another viewport
        _row(("ROOM LEGEND",), obs="r6", vp="vp-legend-2"),
        _row(("101 - ENTRY LOBBY",), obs="r7", vp="vp-legend-2"),
    ]
    parsed = rll.parse_room_legend_rows(rows)
    assert parsed.conflicting_canonical_numbers == ()
    by_num = {e.canonical_room_number: (e.room_name, e.parse_source) for e in parsed.entries}
    assert by_num == {
        "1": ("OFFICE", "room_legend_table"),
        "2": ("STAFF AMENITIES", "room_legend_table"),
        "R3": ("STORAGE", "room_legend_table"),
        "101": ("ENTRY LOBBY", "room_legend_inline"),
    }


def test_links_room_bubbles_to_unique_physical_room_faces_with_full_lineage() -> None:
    parsed = rll.parse_room_legend_rows([
        _row(("ROOM NO.", "ROOM NAME"), obs="h"),
        _row(("01", "OFFICE"), obs="e1"),
        _row(("02", "PANTRY"), obs="e2"),
        _row(("03", "ARCHIVE"), obs="e3"),
    ])
    faces = [
        _face("room-a", _rect(0, 0, 100, 100), direct_name="Office"),
        _face("room-b", _rect(120, 0, 220, 100)),
        _face("room-c", _rect(240, 0, 340, 100)),
    ]
    bubbles = [
        # Notice "1" canonically matches "01"; "D01" and "FT2" are ignored non-room codes
        _bubble("b1", "1", (50.0, 50.0)),
        _bubble("b-door", "D01", (20.0, 20.0)),
        _bubble("b-finish", "FT2", (80.0, 80.0)),
        _bubble("b2", "02", (170.0, 50.0)),
    ]
    report = rll.link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=faces, number_callouts=bubbles,
    )
    assert report.commercial_authority_granted is False
    assert report.floor_area_authority_granted is False
    by_face = {link.room_face_id: link for link in report.room_links}

    assert by_face["room-a"].status == EvidenceResolutionStatus.CORROBORATED
    assert by_face["room-a"].linked_room_name == "OFFICE"
    assert by_face["room-a"].legend_page_id == "2"
    assert by_face["room-a"].legend_viewport_id == "vp-legend"
    assert "corroborated_with_direct_room_name" in by_face["room-a"].reason_codes

    assert by_face["room-b"].status == EvidenceResolutionStatus.CORROBORATED
    assert by_face["room-b"].linked_room_name == "PANTRY"

    assert by_face["room-c"].status == EvidenceResolutionStatus.ABSTAINED
    assert "no_room_number_bubble_in_room_face" in by_face["room-c"].reason_codes

    # Unmatched legend entry 03 stays unmatched (never creates a 4th floor polygon)
    assert [e.canonical_room_number for e in report.unmatched_legend_entries] == ["3"]


def test_duplicate_legend_number_multi_bubble_overlap_and_name_conflict_fail_closed() -> None:
    # Duplicate canonical number ("01" and "1") in legend fails closed
    parsed = rll.parse_room_legend_rows([
        _row(("ROOM NO.", "ROOM NAME"), obs="h"),
        _row(("01", "OFFICE"), obs="e1"),
        _row(("1", "STORE"), obs="e2"),
        _row(("02", "KITCHEN"), obs="e3"),
    ])
    assert parsed.conflicting_canonical_numbers == ("1",)
    assert "duplicate_room_legend_number" in parsed.reason_codes

    faces = [
        _face("room-dup-legend", _rect(0, 0, 100, 100)),
        _face("room-two-bubbles", _rect(120, 0, 220, 100)),
        _face("room-name-clash", _rect(240, 0, 340, 100), direct_name="BATHROOM"),
        _face("room-ov-1", _rect(400, 0, 520, 100)),
        _face("room-ov-2", _rect(460, 0, 580, 100)),
    ]
    bubbles = [
        _bubble("b-dup", "01", (50.0, 50.0)),
        _bubble("b-multi-1", "02", (150.0, 50.0)),
        _bubble("b-multi-2", "03", (190.0, 50.0)),
        _bubble("b-clash", "02", (290.0, 50.0)),
        _bubble("b-overlap", "02", (490.0, 50.0)),  # inside BOTH room-ov-1 and room-ov-2
    ]
    report = rll.link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=faces, number_callouts=bubbles,
    )
    by_face = {link.room_face_id: link for link in report.room_links}
    assert by_face["room-dup-legend"].status == EvidenceResolutionStatus.CONFLICT
    assert "conflicting_room_legend_definition" in by_face["room-dup-legend"].reason_codes
    assert by_face["room-two-bubbles"].status == EvidenceResolutionStatus.CONFLICT
    assert "multiple_room_numbers_in_one_room_face" in by_face["room-two-bubbles"].reason_codes
    assert by_face["room-name-clash"].status == EvidenceResolutionStatus.CONFLICT
    assert "legend_vs_direct_room_name_conflict" in by_face["room-name-clash"].reason_codes
    assert by_face["room-ov-1"].status == EvidenceResolutionStatus.CONFLICT
    assert by_face["room-ov-2"].status == EvidenceResolutionStatus.CONFLICT
    assert "bubble_in_multiple_room_polygons" in by_face["room-ov-1"].reason_codes


def test_cross_revision_sha_viewport_isolation_determinism_and_zero_literals() -> None:
    parsed = rll.parse_room_legend_rows([
        _row(("ROOM NO.", "ROOM NAME"), obs="h", rev="rev-2", sha=_SHA_2),
        _row(("01", "OFFICE"), obs="e1", rev="rev-2", sha=_SHA_2),
    ])
    face = _face("room-1", _rect(0, 0, 100, 100), rev="rev-1", sha=_SHA_1)
    bubble_same_vp = _bubble("b1", "01", (50.0, 50.0), rev="rev-1", sha=_SHA_1)
    bubble_other_vp = _bubble("b2", "01", (50.0, 50.0), vp="vp-other", rev="rev-1", sha=_SHA_1)

    r1 = rll.link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=[face], number_callouts=[bubble_same_vp, bubble_other_vp],
    )
    r2 = rll.link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=[face], number_callouts=[bubble_other_vp, bubble_same_vp],
    )
    assert r1 == r2
    assert r1.room_links[0].status == EvidenceResolutionStatus.ABSTAINED
    assert "room_number_not_in_legend" in r1.room_links[0].reason_codes

    # Degenerate self-crossing bowtie polygon abstains cleanly
    bowtie = _face("room-bowtie", ((0.0, 0.0), (100.0, 100.0), (100.0, 0.0), (0.0, 100.0)))
    r_bad = rll.link_room_legend_to_physical_rooms(
        legend_result=parsed, room_faces=[bowtie], number_callouts=[bubble_same_vp],
    )
    assert r_bad.room_links[0].status == EvidenceResolutionStatus.ABSTAINED
    assert "invalid_or_degenerate_room_polygon" in r_bad.room_links[0].reason_codes

    mod_path = Path(rll.__file__)
    assert audit_shared_source(mod_path.read_text(encoding="utf-8"), filename=mod_path.name) == ()
