"""Focused tests for generic physical room-ring provenance binder (MAX #7236315096, Claude #7236464810)."""
from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_surface_wall_support_veto import (
    FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
    FloorSurfaceWallSupportInput,
)
from pb_source_physical_room_ring_provenance_binder import (
    AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL,
    NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL,
    OPEN_PLAN_FINISH_ZONE_WITNESS_ONLY_NO_PHYSICAL_RING,
    ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED,
    PHYSICAL_ROOM_RING_PROVENANCE_REBOUND,
    RING_CONTAINS_MULTIPLE_DISTINCT_ROOM_LABELS,
    RING_INSUFFICIENT_POSITIVE_WALL_SUPPORT,
    RING_STATUS_NOT_CANDIDATE,
    RoomProvenanceBindingCandidate,
    SourceProvenFinishZoneWitness,
    bind_room_provenance_to_physical_rings_shadow,
)

SHA = "a" * 64
GRID_CELL = ((10.0, 10.0), (44.0, 10.0), (44.0, 44.0), (10.0, 44.0))
OPEN_CELL = ((300.0, 10.0), (334.0, 10.0), (334.0, 44.0), (300.0, 44.0))
PARTIAL_ROOM = ((500.0, 10.0), (650.0, 10.0), (650.0, 160.0), (500.0, 160.0))
PHYSICAL_RING = ((0.0, 0.0), (180.0, 0.0), (180.0, 160.0), (0.0, 160.0))


def _surf(sid: str, qid: str, poly) -> FloorSurfaceWallSupportInput:
    return FloorSurfaceWallSupportInput(
        surface_entity_id=sid,
        quantity_id=qid,
        document_id="doc1",
        revision_id="rev1",
        source_sha256=SHA,
        page_id="7",
        viewport_id="view_p7_2",
        polygon_pdf_pts=poly,
    )


def _wall_predicate(poly, drawings, closures=()):
    x0 = poly[0][0]
    if x0 in (10.0, 300.0):
        # 0% physical wall support drafting/grid cell
        return SimpleNamespace(
            edges=(
                SimpleNamespace(length=34.0, unsupported=34.0),
                SimpleNamespace(length=34.0, unsupported=34.0),
            )
        )
    if x0 == 500.0:
        # 28% paired-wall supported room (e.g. cold room)
        return SimpleNamespace(
            edges=(
                SimpleNamespace(length=100.0, unsupported=44.0),
                SimpleNamespace(length=100.0, unsupported=100.0),
            )
        )
    # 99.6% physical room ring with doorway closure
    return SimpleNamespace(
        edges=(
            SimpleNamespace(length=180.0, unsupported=0.0),
            SimpleNamespace(length=160.0, unsupported=1.36),
        )
    )


def test_false_cell_rebinds_to_unique_wall_supported_ring_while_open_zone_stays_withheld() -> None:
    ring = SimpleNamespace(
        record_id="layered_wall_doorway_room_ring_demo_enclosed",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28800.0,
        wall_edge_count=10,
        closure_edge_count=1,
        bounding_closure_ids=("layered_doorway_closure_demo_1",),
        bounding_wall_path_indices=(1, 2, 3, 4),
    )

    c_enclosed_false_cell = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid_cell", "q_enclosed", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
        explicit_area_authority="documented_dimension",
        explicit_area_evidence_ids=("dim_x", "dim_y"),
        floor_finish_code="FT1",
        floor_finish_evidence_ids=("fin_1",),
        rcp_ceiling_material="PLASTERBOARD",
        rcp_ceiling_height_mm=2700,
        rcp_ceiling_evidence_ids=("rcp_1",),
    )
    c_open_zone_false_cell = RoomProvenanceBindingCandidate(
        surface=_surf("surf_open_cell", "q_open", OPEN_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(315.0, 25.0),
        explicit_area_m2=13.270425,
        explicit_area_authority="documented_dimension",
        explicit_area_evidence_ids=("dim_a", "dim_b"),
    )
    c_partial_supported = RoomProvenanceBindingCandidate(
        surface=_surf("surf_partial_wall", "q_partial", PARTIAL_ROOM),
        page_index=6,
        room_label_anchor_pdf_pt=(550.0, 50.0),
        explicit_area_m2=25.37875,
        explicit_area_authority="documented_dimension",
        explicit_area_evidence_ids=("dim_c", "dim_d"),
    )

    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(c_enclosed_false_cell, c_open_zone_false_cell, c_partial_supported),
        physical_rings=(ring,),
        drawings=(),
        wall_support_predicate=_wall_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    by_qid = {b.quantity_id: b for b in bindings}

    # 1. Enclosed room rebound from false grid cell -> physical ring with all provenance preserved
    b_enc = by_qid["q_enclosed"]
    assert b_enc.withheld is False
    assert b_enc.status is EvidenceResolutionStatus.CORROBORATED
    assert b_enc.bound_ring_record_id == "layered_wall_doorway_room_ring_demo_enclosed"
    assert b_enc.bound_surface_entity_id == "layered_wall_doorway_room_ring_demo_enclosed"
    assert b_enc.bound_ring_closure_ids == ("layered_doorway_closure_demo_1",)
    assert b_enc.wall_support_fraction > 0.99
    assert b_enc.explicit_area_m2 == 9.05352
    assert b_enc.explicit_area_evidence_ids == ("dim_x", "dim_y")
    assert b_enc.floor_finish_code == "FT1"
    assert b_enc.rcp_ceiling_material == "PLASTERBOARD"
    assert b_enc.rcp_ceiling_height_mm == 2700
    assert b_enc.reason_codes == (PHYSICAL_ROOM_RING_PROVENANCE_REBOUND,)
    assert b_enc.shadow_only is True
    assert b_enc.commercial_authority_granted is False

    # 2. Unenclosed open-plan zone stays strictly withheld (false-cell veto preserved!)
    b_open = by_qid["q_open"]
    assert b_open.withheld is True
    assert b_open.status is EvidenceResolutionStatus.ABSTAINED
    assert b_open.bound_ring_record_id is None
    assert b_open.explicit_area_m2 is None
    assert b_open.reason_codes == (
        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
        NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL,
    )

    # 3. Already wall-supported surface retained directly without rebinding
    b_part = by_qid["q_partial"]
    assert b_part.withheld is False
    assert b_part.status is EvidenceResolutionStatus.CORROBORATED
    assert b_part.bound_surface_entity_id == "surf_partial_wall"
    assert b_part.bound_ring_record_id is None
    assert b_part.explicit_area_m2 == 25.37875
    assert ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED in b_part.reason_codes


def test_ambiguous_overlapping_physical_rings_fail_closed_with_conflict() -> None:
    ring1 = SimpleNamespace(
        record_id="ring_1",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28800.0,
        wall_edge_count=8,
        closure_edge_count=1,
        bounding_closure_ids=("c1",),
        bounding_wall_path_indices=(1, 2),
    )
    ring2 = SimpleNamespace(
        record_id="ring_2",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28800.0,
        wall_edge_count=8,
        closure_edge_count=1,
        bounding_closure_ids=("c2",),
        bounding_wall_path_indices=(3, 4),
    )
    cand = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid", "q_ambig", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
    )
    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(cand,),
        physical_rings=(ring1, ring2),
        drawings=(),
        wall_support_predicate=_wall_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    assert len(bindings) == 1
    assert bindings[0].withheld is True
    assert bindings[0].status is EvidenceResolutionStatus.CONFLICT
    assert bindings[0].reason_codes == (
        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
        AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL,
    )


def test_multi_room_open_plan_shell_ring_is_rejected_while_single_room_ring_binds() -> None:
    # Mimics real Sheet-7 discovery: giant open-plan shell ring encloses multiple
    # distinct room labels (open zone + adjacent zone), while single enclosed room
    # ring contains only its own label.
    single_room_ring = SimpleNamespace(
        record_id="ring_single_enclosed",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28197.7,
        wall_edge_count=10,
        closure_edge_count=1,
        bounding_closure_ids=("c_door_1",),
        bounding_wall_path_indices=(1, 2, 3),
    )
    giant_shell_ring = SimpleNamespace(
        record_id="ring_open_plan_shell",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=((200.0, 0.0), (1200.0, 0.0), (1200.0, 1000.0), (200.0, 1000.0)),
        area_pt2=1000000.0,
        wall_edge_count=40,
        closure_edge_count=9,
        bounding_closure_ids=("c1", "c2", "c3"),
        bounding_wall_path_indices=(10, 11, 12),
    )

    c_single = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid_single", "q_single", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
    )
    c_open_zone = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid_open", "q_open_zone", OPEN_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(315.0, 25.0),
        explicit_area_m2=13.270425,
    )
    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(c_single, c_open_zone),
        physical_rings=(single_room_ring, giant_shell_ring),
        drawings=(),
        wall_support_predicate=_wall_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
        page_room_label_anchors=(
            (6, "lbl_single", (25.0, 25.0)),
            (6, "lbl_open_zone", (315.0, 25.0)),
            (6, "lbl_adjacent_zone", (450.0, 250.0)),
        ),
    )
    by_qid = {b.quantity_id: b for b in bindings}

    assert by_qid["q_single"].withheld is False
    assert by_qid["q_single"].bound_ring_record_id == "ring_single_enclosed"
    assert by_qid["q_single"].explicit_area_m2 == 9.05352

    assert by_qid["q_open_zone"].withheld is True
    assert by_qid["q_open_zone"].status is EvidenceResolutionStatus.ABSTAINED
    assert by_qid["q_open_zone"].bound_ring_record_id is None
    assert by_qid["q_open_zone"].reason_codes == (
        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
        RING_CONTAINS_MULTIPLE_DISTINCT_ROOM_LABELS,
    )


def test_abstained_and_conflict_rings_are_rejected_even_with_supported_edges() -> None:
    # Claude #7236597561 & #7236809130 exact synthetic probe: an ABSTAINED ring
    # with 1 of 4 edges supported must NEVER be bound as corroborated.
    abstained_ring = SimpleNamespace(
        record_id="ring_abstained_open_gap",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.ABSTAINED,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28800.0,
        wall_edge_count=4,
        closure_edge_count=1,
        bounding_closure_ids=("c1",),
        bounding_wall_path_indices=(1, 2),
    )
    cand = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid", "q_abstained_probe", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
    )
    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(cand,),
        physical_rings=(abstained_ring,),
        drawings=(),
        wall_support_predicate=_wall_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    assert len(bindings) == 1
    assert bindings[0].withheld is True
    assert bindings[0].status is EvidenceResolutionStatus.ABSTAINED
    assert bindings[0].bound_ring_record_id is None
    assert bindings[0].reason_codes == (
        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
        RING_STATUS_NOT_CANDIDATE,
    )


def test_ring_wall_support_check_receives_only_rings_own_closures() -> None:
    # Claude #7236597561: wall_support_predicate for a candidate ring must receive
    # strictly that ring's own bounding_closure_ids, not unrelated page closures.
    seen_closure_ids: list[tuple[str, ...]] = []

    def _capturing_pred(poly, drawings, closures=()):
        if poly == PHYSICAL_RING:
            seen_closure_ids.append(tuple(c.closure_id for c in closures))
        return _wall_predicate(poly, drawings, closures=closures)

    ring = SimpleNamespace(
        record_id="ring_own_closure",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28197.7,
        wall_edge_count=10,
        closure_edge_count=1,
        bounding_closure_ids=("cl_mine",),
        bounding_wall_path_indices=(1, 2),
    )
    cand = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid", "q_closure_scope", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
    )
    all_closures = (
        SimpleNamespace(closure_id="cl_mine"),
        SimpleNamespace(closure_id="cl_other_room"),
    )
    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(cand,),
        physical_rings=(ring,),
        drawings=(),
        wall_support_predicate=_capturing_pred,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
        closures=all_closures,
    )
    assert bindings[0].withheld is False
    assert bindings[0].bound_ring_record_id == "ring_own_closure"
    assert seen_closure_ids == [("cl_mine",)]


def test_weak_25pct_ring_rejected_by_positive_support_threshold_and_open_zone_keeps_finish_witness_only() -> None:
    def _weak_ring_pred(poly, drawings, closures=()):
        if poly == PHYSICAL_RING:
            # Only 1 of 4 edges supported (25% < 50% default positive threshold)
            return SimpleNamespace(
                edges=(
                    SimpleNamespace(length=100.0, unsupported=0.0),
                    SimpleNamespace(length=300.0, unsupported=300.0),
                )
            )
        return _wall_predicate(poly, drawings, closures=closures)

    weak_ring = SimpleNamespace(
        record_id="ring_weak_25pct",
        source_sha256=SHA,
        page_index=6,
        status=EvidenceResolutionStatus.CANDIDATE,
        polygon_pdf_pts=PHYSICAL_RING,
        area_pt2=28800.0,
        wall_edge_count=1,
        closure_edge_count=0,
        bounding_closure_ids=(),
        bounding_wall_path_indices=(1,),
    )
    cand_weak = RoomProvenanceBindingCandidate(
        surface=_surf("surf_grid_weak", "q_weak", GRID_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(25.0, 25.0),
        explicit_area_m2=9.05352,
    )
    cand_open_fz = RoomProvenanceBindingCandidate(
        surface=_surf("surf_open_fz", "q_open_fz", OPEN_CELL),
        page_index=6,
        room_label_anchor_pdf_pt=(315.0, 25.0),
        explicit_area_m2=13.270425,
    )
    fz_witness = SourceProvenFinishZoneWitness(
        witness_id="fz_witness_ft2",
        surface_entity_id="surf_open_fz",
        document_id="doc1",
        revision_id="rev1",
        source_sha256=SHA,
        finish_code="FT2",
        evidence_ids=("ev_sched_ft2", "ev_plan_ft2"),
    )
    bindings = bind_room_provenance_to_physical_rings_shadow(
        candidates=(cand_weak, cand_open_fz),
        physical_rings=(weak_ring,),
        drawings=(),
        wall_support_predicate=_weak_ring_pred,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
        finish_zone_witnesses_by_surface_id={"surf_open_fz": fz_witness},
    )
    by_qid = {b.quantity_id: b for b in bindings}

    # 1. Weak 25% ring fails positive support threshold (veto != positive selector)
    b_weak = by_qid["q_weak"]
    assert b_weak.withheld is True
    assert b_weak.bound_ring_record_id is None
    assert RING_INSUFFICIENT_POSITIVE_WALL_SUPPORT in b_weak.reason_codes

    # 2. Open-plan zone keeps source-proven finish-zone witness strictly withheld (zero invented walls)
    b_fz = by_qid["q_open_fz"]
    assert b_fz.withheld is True
    assert b_fz.status is EvidenceResolutionStatus.ABSTAINED
    assert b_fz.bound_ring_record_id is None
    assert b_fz.explicit_area_m2 is None
    assert b_fz.bound_finish_zone_witness_id == "fz_witness_ft2"
    assert b_fz.floor_finish_code == "FT2"
    assert b_fz.floor_finish_evidence_ids == ("ev_sched_ft2", "ev_plan_ft2")
    assert b_fz.commercial_authority_granted is False
    assert OPEN_PLAN_FINISH_ZONE_WITNESS_ONLY_NO_PHYSICAL_RING in b_fz.reason_codes
