"""Source-page and metric continuity through the real figured-room -> finish shadow path.

A CANDIDATE here never authorizes floor_finish_area, a customer row, or score.
"""
from dataclasses import replace

import pytest

from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide,
    measure_figured_room_edge_chain_shadow,
)
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    AuthenticatedFloorFinishPlanMark,
    OriginalPhysicalFloorToFinishScope,
    OriginalTwoSheetBoundaryOwner,
    bind_source_finish_mark_to_corresponded_floor_shadow,
    resolve_source_physical_floor_correspondence_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _actual_figured_producer():
    ring = ((0, 0), (10, 0), (10, 5), (0, 5))
    sides = tuple(
        FiguredPhysicalSide(
            f"side-{i}",
            ring[i],
            ring[(i + 1) % 4],
            (f"room-ink-{i}",),
            {0: 5000, 1: 2000}.get(i),
            f"fig-{i}" if i in (0, 1) else None,
            (f"witness-{i}-a", f"witness-{i}-b") if i in (0, 1) else (),
        )
        for i in range(4)
    )
    result = measure_figured_room_edge_chain_shadow(
        sides,
        source_sha256="a" * 64,
        revision_id="rev",
        page_id="7",
        physical_room_id="room",
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_area_m2 == 10.0
    return result


def _source_scope():
    owners = tuple(
        OriginalTwoSheetBoundaryOwner(
            f"wall-{i}",
            (f"room-ink-{i}",),
            (f"finish-ink-{i}",),
            f"wall-receipt-{i}",
            "source_closed_physical_wall_equivalence",
        )
        for i in range(4)
    )
    return OriginalPhysicalFloorToFinishScope(
        physical_room_id="room",
        canonical_floor_id="floor",
        source_sha256="a" * 64,
        revision_id="rev",
        producer_snapshot_id="snapshot",
        decision_scope_id="decision",
        original_room_page_id="7",
        original_finish_page_id="11",
        physical_boundary_source_ids=tuple(f"room-ink-{i}" for i in range(4)),
        finish_support_source_ids=tuple(f"finish-ink-{i}" for i in range(4)),
        wall_owners=owners,
        original_finish_room_polygon_pts=((0, 0), (10, 0), (10, 5), (0, 5)),
        source_room_face_record_id="room-face",
    )


def _mark(*, bbox=(3, 1, 4, 2), mark_id="finish-mark"):
    return AuthenticatedFloorFinishPlanMark(
        mark_id, "definition", "glyph-paint", "clip", "partition",
        "FT3", "tile", bbox, "a" * 64, "rev", "11", "vp", True,
    )


def _inputs():
    measured = _actual_figured_producer()
    correspondence = resolve_source_physical_floor_correspondence_shadow(
        measured, _source_scope()
    )
    assert correspondence.status is EvidenceResolutionStatus.CANDIDATE
    return measured, correspondence


def test_valid_original_room_page_and_metric_survive_as_candidate_only():
    measured, correspondence = _inputs()
    original = (measured, correspondence)
    result = bind_source_finish_mark_to_corresponded_floor_shadow(
        measured, correspondence, (_mark(),)
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.original_floor_id == "floor"
    assert result.original_occurrence_id == "finish-mark"
    assert result.candidate_area_m2 == 10.0
    assert result.diagnostic_only
    assert not hasattr(result, "quantity_id")
    assert original == (measured, correspondence)


@pytest.mark.parametrize("foreign_page", ["8", "11", "", None, 7])
def test_same_physical_room_id_on_foreign_source_page_cannot_borrow_metric(foreign_page):
    measured, correspondence = _inputs()
    tampered = replace(measured, page_id=foreign_page)
    result = bind_source_finish_mark_to_corresponded_floor_shadow(
        tampered, correspondence, (_mark(),)
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == ("original_floor_finish_correspondence_unavailable",)
    assert result.candidate_area_m2 is None


@pytest.mark.parametrize("field,value", [
    ("original_room_page_id", "8"),
    ("original_room_page_id", None),
    ("original_finish_page_id", "7"),
    ("original_finish_page_id", ""),
    ("canonical_floor_id", ""),
    ("canonical_floor_id", " floor "),
    ("producer_snapshot_id", ""),
    ("decision_scope_id", None),
    ("source_room_face_record_id", ""),
    ("wall_equivalence_receipts", ()),
    ("wall_equivalence_receipts", ("one", "one")),
    ("diagnostic_only", False),
])
def test_rekeyed_original_physical_room_receipts_do_not_supply_finish(field, value):
    measured, correspondence = _inputs()
    altered = replace(correspondence, **{field: value})
    result = bind_source_finish_mark_to_corresponded_floor_shadow(
        measured, altered, (_mark(),)
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidate_area_m2 is None


@pytest.mark.parametrize("bad", [None, 0, -0.1, float("nan"), float("inf"), -float("inf"), 10 ** 1000, "10", True])
def test_reconstructed_nonmetric_area_is_never_reexported_as_candidate(bad):
    measured, correspondence = _inputs()
    result = bind_source_finish_mark_to_corresponded_floor_shadow(
        replace(measured, candidate_area_m2=bad), correspondence, (_mark(),)
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == ("original_floor_finish_metric_area_unavailable",)
    assert result.candidate_area_m2 is None


def test_multiple_original_material_occurrences_preserve_ambiguity_in_either_order():
    measured, correspondence = _inputs()
    a = _mark()
    b = replace(_mark(mark_id="other"), source_material_code="FT2")
    for marks in ((a, b), (b, a)):
        result = bind_source_finish_mark_to_corresponded_floor_shadow(
            measured, correspondence, marks
        )
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == ("original_floor_finish_mark_missing_or_competing",)


def test_unrelated_outside_source_mark_does_not_erase_unique_inside_candidate():
    measured, correspondence = _inputs()
    inside = _mark()
    outside = _mark(bbox=(20, 20, 21, 21), mark_id="separate-mark")
    for marks in ((inside, outside), (outside, inside)):
        result = bind_source_finish_mark_to_corresponded_floor_shadow(
            measured, correspondence, marks
        )
        assert result.status is EvidenceResolutionStatus.CANDIDATE
        assert result.original_occurrence_id == inside.source_occurrence_id


def test_existing_other_page_original_mark_does_not_claim_room_finish():
    measured, correspondence = _inputs()
    foreign = replace(_mark(), page_id="7")
    result = bind_source_finish_mark_to_corresponded_floor_shadow(
        measured, correspondence, (foreign,)
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidate_area_m2 is None
