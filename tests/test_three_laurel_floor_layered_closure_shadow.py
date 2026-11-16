"""Existing room-ring CS / VSD candidates never become billable walls."""

from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_next_wall_ring_preview import (
    KIND_CAVITY_SLIDER,
    KIND_SLIDING_LEAF,
    KIND_STROKE,
    LayeredDoorwayClosure,
    LayeredRoomRingResult,
)
from pb_three_laurel_floor_layered_closure_shadow import (
    match_existing_room_ring_closure_candidates as match,
)
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    FloorWallCandidateReceipt,
    WallFaceCandidate,
)

SHA = "a" * 64


def receipt():
    face = WallFaceCandidate(
        "east",
        (100.0, 0.0),
        (100.0, 80.0),
        80.0,
        45.0,
        (5, 6),
        ((30.0, 65.0),),
    )
    return FloorWallCandidateReceipt(
        label="MEDIA",
        label_center_pdf_pt=(60.0, 40.0),
        floor_candidate_native_path_id=97,
        floor_candidate_bounds_pdf_pts=(20.0, 0.0, 100.0, 80.0),
        wall_face_candidates=(face,),
        supporting_native_wall_paths=(5, 6),
        total_boundary_pdf_pt=80.0,
        supported_boundary_pdf_pt=45.0,
        page_index=2,
        source_sha256=SHA,
    )


def closure(
    *,
    kind=KIND_CAVITY_SLIDER,
    id="cs-original",
    band=(98.0, 100.3),
    gap=(30.0, 65.0),
    paths=(),
    host_paths=(),
    refs=("p3:w342",),
    horizontal=False,
):
    return LayeredDoorwayClosure(
        closure_id=id,
        kind=kind,
        horizontal=horizontal,
        band=band,
        gap_interval=gap,
        native_path_indices=paths,
        wall_path_indices=host_paths,
        native_word_refs=refs,
    )


def result(*closures, status=EvidenceResolutionStatus.CANDIDATE):
    return LayeredRoomRingResult(
        status=status,
        reason_codes=(),
        rings=(),
        closures=tuple(closures),
        wall_strip_count=1,
        wall_gap_count=1,
        unresolved_gap_count=1,
        non_strip_wall_fill_count=0,
        unplaced_swing_count=0,
        ambiguous_swing_count=0,
    )


def test_existing_cs_word_only_producer_corresponds_but_never_authenticates():
    matches = match(receipt(), result(closure()), source_sha256=SHA, page_index=2)
    assert len(matches) == 1
    w = matches[0]
    assert w.producer_kind == KIND_CAVITY_SLIDER
    assert w.evidence_completeness == "word_only_unhosted"
    assert w.original_native_path_ids == ()
    assert w.original_wall_path_ids == ()
    assert w.original_word_refs == ("p3:w342",)
    assert w.room_gap_interval_pdf_pt == (30.0, 65.0)
    assert w.matched_span_pdf_pt == 35.0
    assert w.to_dict()["room_enclosure_authenticated"] is False
    assert w.to_dict()["measurement_authorized"] is False
    assert w.to_dict()["physical_wall_authenticated"] is False


def test_existing_sliding_leaf_frame_producer_keeps_native_path_evidence():
    c = closure(
        kind=KIND_SLIDING_LEAF, id="robe", paths=(1, 2, 3, 4), refs=(), host_paths=()
    )
    v = match(receipt(), result(c), source_sha256=SHA, page_index=2)
    assert len(v) == 1
    assert v[0].evidence_completeness == "native_leaf_without_host_wall_ids"
    assert v[0].original_native_path_ids == (1, 2, 3, 4)
    assert v[0].measurement_authorized is False


def test_stroke_or_bare_unowned_gap_cannot_masquerade_as_hosted_door():
    assert (
        match(
            receipt(),
            result(closure(kind=KIND_STROKE)),
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )
    assert (
        match(
            receipt(),
            result(closure(paths=(), refs=())),
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )


def test_page_and_source_sha_mismatch_fail_closed():
    good = result(closure())
    assert match(receipt(), good, source_sha256="b" * 64, page_index=2) == ()
    assert match(receipt(), good, source_sha256=SHA, page_index=3) == ()
    assert (
        match(
            replace(receipt(), source_sha256=""), good, source_sha256=SHA, page_index=2
        )
        == ()
    )
    assert (
        match(
            replace(receipt(), floor_candidate_native_path_id=None),
            good,
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )
    assert (
        match(
            receipt(),
            result(closure(), status=EvidenceResolutionStatus.ABSTAINED),
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )


def test_nonadjacent_other_axis_or_uncovered_missing_does_not_infer_closure():
    bad = closure(band=(93.0, 95.0))
    assert match(receipt(), result(bad), source_sha256=SHA, page_index=2) == ()
    assert (
        match(
            receipt(), result(closure(horizontal=True)), source_sha256=SHA, page_index=2
        )
        == ()
    )
    assert (
        match(
            receipt(),
            result(closure(gap=(65.0, 90.0))),
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )
    empty_face = replace(
        receipt().wall_face_candidates[0], uncovered_intervals_pdf_pt=()
    )
    assert (
        match(
            replace(receipt(), wall_face_candidates=(empty_face,)),
            result(closure()),
            source_sha256=SHA,
            page_index=2,
        )
        == ()
    )


def test_conflicting_same_face_closure_owners_abstain():
    a = closure(id="same-gap-A", paths=(1, 2), refs=())
    b = closure(id="same-gap-B", paths=(3, 4), refs=())
    assert match(receipt(), result(a, b), source_sha256=SHA, page_index=2) == ()
    assert len(match(receipt(), result(a, a), source_sha256=SHA, page_index=2)) == 1
