"""Order 6 real consumer fixtures & collision negatives for unified opening evidence handoff."""

from __future__ import annotations

from pathlib import Path

from pb_opening_schedule_v171 import ScheduleEntry
from pb_schedule_instance_quantity_lineage_shadow import (
    PhysicalOpeningInstanceCandidate,
    ScheduleMarkRowCandidate,
)
from pb_shared_opening_cluster_callout_shadow import (
    ClusterOpeningLegCandidate,
    OpeningClusterCalloutWitness,
)
from pb_source_cavity_slider_vs_push_pull_shadow import DoorApertureSymbolObservation
from pb_source_external_glazing_reconciliation_shadow import (
    GlazingElevationWitness,
    GlazingLineageRef,
    GlazingScheduleRowWitness,
    PhysicalGlazingApertureWitness,
)
from pb_source_garage_panel_door_dimension_shadow import (
    GarageDoorDimensionWitness,
    GarageDoorHostWitness,
    SourceLineageRef,
)
from pb_source_host_stroke_exclusion_shadow import (
    ApertureHostCandidateContext,
    SourceMarkerPrimitive,
    SourceTextBox,
    SourceVectorStroke,
    StrokeLineageRef,
)
from pb_source_opening_evidence_handoff_shadow import build_opening_evidence_handoff_shadow
from pb_source_opening_host_membership_proof_shadow import (
    CandidateHostWallBand,
    HostLineageRef,
    PhysicalOpeningApertureWitness,
)
from pb_source_unmarked_opening_figure_witness_shadow import (
    FigureLineageRef,
    NativeVectorSegment,
    TrustedFigureText,
    UnmarkedOpeningTarget,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


_SHA = "1" * 64


def test_real_consumer_scheduled_cavity_slider_from_schedule_entry_and_host_strokes() -> None:
    """Consumer fixture: real ScheduleEntry -> host strokes -> host wall -> cavity slider -> handoff."""
    entry = ScheduleEntry(
        type_mark="D05",
        width_mm=820,
        height_mm=2040,
        description="Cavity Slider",
        page_no=28,
        dimension_basis="leaf",
    )
    h_lin = HostLineageRef("doc_arch", "rev_01", _SHA, "page_07", "vp_plan_main")
    s_lin = StrokeLineageRef("doc_arch", "rev_01", _SHA, "page_07", "vp_plan_main")

    aperture = PhysicalOpeningApertureWitness("phys_open_d05", h_lin, (80.0, 50.0), (105.0, 50.0), 8.0)
    walls = (
        CandidateHostWallBand("wall_true_host", h_lin, (20.0, 50.0), (200.0, 50.0), 8.0),
        CandidateHostWallBand("wall_parallel_neighbor", h_lin, (20.0, 72.0), (200.0, 72.0), 8.0),
        CandidateHostWallBand(
            "wall_other_viewport",
            HostLineageRef("doc_arch", "rev_01", _SHA, "page_07", "vp_inset"),
            (20.0, 50.0),
            (200.0, 50.0),
            8.0,
        ),
    )
    stroke_ctx = ApertureHostCandidateContext(
        opening_id="phys_open_d05",
        lineage=s_lin,
        aperture_center=(92.5, 50.0),
        aperture_axis_unit=(1.0, 0.0),
        aperture_half_span_pts=12.5,
        wall_thickness_pts=8.0,
        expected_host_layers=("A-WALL-INTR",),
    )
    strokes = (
        SourceVectorStroke("st_host_left", (20.0, 46.0), (80.0, 46.0), 0.9, "A-WALL-INTR", s_lin),
        SourceVectorStroke("st_leader_spoof", (92.5, 50.0), (125.0, 72.0), 0.7, "A-WALL-INTR", s_lin),
        SourceVectorStroke("st_dim_rail", (80.0, 26.0), (105.0, 26.0), 0.25, "A-WALL-INTR", s_lin),
    )
    markers = (
        SourceMarkerPrimitive("mk_arrow", "arrow", (92.5, 50.0), "A-ANNO", s_lin),
        SourceMarkerPrimitive("mk_t1", "slash", (80.0, 26.0), "A-ANNO", s_lin),
        SourceMarkerPrimitive("mk_t2", "slash", (105.0, 26.0), "A-ANNO", s_lin),
    )
    texts = (SourceTextBox("tx_820", "820", (87.0, 18.0, 98.0, 25.0), "A-ANNO", s_lin),)

    # Single cavity slider pocket extending left into host wall [55..80] + parallel sliding leaf
    op_obs = DoorApertureSymbolObservation(
        opening_id="phys_open_d05",
        document_id="doc_arch",
        revision_id="rev_01",
        source_sha256=_SHA,
        page_id="page_07",
        viewport_id="vp_plan_main",
        host_wall_id="wall_true_host",
        jamb_a=(80.0, 50.0),
        jamb_b=(105.0, 50.0),
        wall_thickness_pt=8.0,
        leaf_segments=(((60.0, 50.0), (96.0, 50.0)),),
        pocket_recess_segments=(
            ((55.0, 48.0), (80.0, 48.0)),
            ((55.0, 52.0), (80.0, 52.0)),
        ),
        text_cues=("CAVITY SLIDER",),
    )

    sched_row = ScheduleMarkRowCandidate(
        document_id="doc_arch",
        revision_id="rev_01",
        source_sha256=_SHA,
        schedule_page_id="page_28",
        schedule_viewport_id="vp_sched",
        row_observation_ids=("obs_sched_d05",),
        type_mark=entry.type_mark,
        width_mm=entry.width_mm,
        height_mm=entry.height_mm,
        dimension_basis="leaf",
        basis_source="door leaf",
    )
    inst = PhysicalOpeningInstanceCandidate(
        instance_id="phys_open_d05",
        document_id="doc_arch",
        revision_id="rev_01",
        source_sha256=_SHA,
        plan_page_id="page_07",
        plan_viewport_id="vp_plan_main",
        physical_evidence_ids=("obs_open_d05",),
        plan_tag_mark="D05",
        plan_tag_observation_id="obs_tag_d05",
        host_wall_id="wall_true_host",
    )

    pkt = build_opening_evidence_handoff_shadow(
        opening_category="scheduled_door",
        host_aperture=aperture,
        candidate_walls=walls,
        stroke_context=stroke_ctx,
        candidate_strokes=strokes,
        stroke_texts=texts,
        stroke_markers=markers,
        operation_observation=op_obs,
        schedule_rows=(sched_row,),
        schedule_instances=(inst,),
    )
    assert pkt.host_membership_proven is True
    assert pkt.proven_host_wall_id == "wall_true_host"
    assert pkt.accepted_host_stroke_ids == ("st_host_left",)
    assert pkt.rejected_host_stroke_count == 2
    assert pkt.operation_classification == "cavity_slider_pocket_leaf"
    assert pkt.dimension_proven is True
    assert pkt.width_mm == 820.0
    assert pkt.height_mm == 2040.0
    assert pkt.dimension_basis == "leaf_dimension"
    assert pkt.first_remaining_gate == "host_and_frame_authority_promotion_required"
    assert pkt.host_authority_granted is False
    assert pkt.frame_authority_granted is False
    assert pkt.commercial_authority_granted is False


def test_real_consumer_garage_blocks_2040_glazing_reconciles_cluster_and_unmarked_proves_figure_line() -> None:
    h_lin = HostLineageRef("doc_arch", "rev_01", _SHA, "page_03", "vp_plan")
    true_wall = CandidateHostWallBand("wall_ext_01", h_lin, (0.0, 50.0), (300.0, 50.0), 8.0)

    # 1. Garage panel door missing height MUST block 2040 mm fallback
    g_ap = PhysicalOpeningApertureWitness("phys_garage_01", h_lin, (60.0, 50.0), (196.06, 50.0), 8.0)
    g_host = GarageDoorHostWitness(
        opening_id="phys_garage_01",
        lineage=SourceLineageRef("doc_arch", "rev_01", _SHA, "page_03", "vp_plan"),
        start_host_wall_id="wall_ext_l",
        end_host_wall_id="wall_ext_r",
        jamb_cap_ids=("cap_l", "cap_r"),
        aperture_span_pts=136.06,
        native_label_text="PANEL LIFT GARAGE DOOR",
        calibrated_mm_per_pt=35.2778,
    )
    g_w_2040 = GarageDoorDimensionWitness(
        witness_id="w_bad_2040",
        source_kind="assumed_standard_external_door_height",
        lineage=SourceLineageRef("doc_arch", "rev_01", _SHA, "page_03", "vp_plan"),
        linked_opening_id="phys_garage_01",
        width_mm=4800.0,
        height_mm=2040.0,
        is_default_assumption=True,
    )
    pkt_garage = build_opening_evidence_handoff_shadow(
        opening_category="garage_panel_door",
        host_aperture=g_ap,
        candidate_walls=(true_wall,),
        garage_host=g_host,
        garage_dim_witnesses=(g_w_2040,),
    )
    assert pkt_garage.dimension_proven is False
    assert pkt_garage.height_mm is None
    assert pkt_garage.standard_door_2040_fallback_blocked is True
    assert "assumed_2040_door_height_rejected_for_garage_door" in pkt_garage.blocking_reasons

    # 2. External glazing reconciled across schedule + elevation + calibrated aperture + corner cluster
    gl_ap = PhysicalOpeningApertureWitness("phys_w01", h_lin, (80.0, 50.0), (131.02, 50.0), 8.0)
    gl_lin = GlazingLineageRef("doc_arch", "rev_01", _SHA, "page_03", "vp_plan")
    c_legs = (
        ClusterOpeningLegCandidate("phys_w01", "doc_arch", "rev_01", _SHA, "page_03", "vp_plan", "wall_ext_01", (80.0, 50.0), (131.02, 50.0), ("ev1",)),
        ClusterOpeningLegCandidate("phys_w02", "doc_arch", "rev_01", _SHA, "page_03", "vp_plan", "wall_ext_02", (131.02, 50.0), (131.02, 101.02), ("ev2",)),
    )
    c_callouts = (
        OpeningClusterCalloutWitness("cal_corner", "doc_arch", "rev_01", _SHA, "page_03", "vp_plan", "obs_c", "2124", (142.0, 62.0), 2100, 2400),
    )
    pkt_glaz = build_opening_evidence_handoff_shadow(
        opening_category="external_glazing",
        host_aperture=gl_ap,
        candidate_walls=(true_wall,),
        cluster_legs=c_legs,
        cluster_callouts=c_callouts,
        glazing_aperture=PhysicalGlazingApertureWitness("phys_w01", gl_lin, "wall_ext_01", 51.02, 35.2778, "W01"),
        glazing_schedule_rows=(
            GlazingScheduleRowWitness("r_w01", GlazingLineageRef("doc_arch", "rev_01", _SHA, "page_10", "vp_s"), "W01", 1800.0, 1500.0, "frame_dimension"),
        ),
        glazing_elevations=(
            GlazingElevationWitness("e_w01", GlazingLineageRef("doc_arch", "rev_01", _SHA, "page_06", "vp_e"), "W01", "phys_w01", 1800.0, 1500.0, 900.0, 2400.0, "frame_dimension"),
        ),
    )
    assert pkt_glaz.dimension_proven is True
    assert pkt_glaz.cluster_id is not None
    assert (pkt_glaz.width_mm, pkt_glaz.height_mm, pkt_glaz.dimension_basis) == (1800.0, 1500.0, "frame_dimension")

    # 3. Unmarked opening proved from native figure lines
    f_lin = FigureLineageRef("doc_arch", "rev_01", _SHA, "page_03", "vp_plan")
    um_ap = PhysicalOpeningApertureWitness("phys_unmarked_01", h_lin, (80.0, 50.0), (120.0, 50.0), 8.0)
    pkt_um = build_opening_evidence_handoff_shadow(
        opening_category="unmarked_opening",
        host_aperture=um_ap,
        candidate_walls=(true_wall,),
        unmarked_target=UnmarkedOpeningTarget("phys_unmarked_01", f_lin, (80.0, 50.0), (120.0, 50.0)),
        unmarked_segments=(
            NativeVectorSegment("r1", (80.0, 25.0), (120.0, 25.0), f_lin),
            NativeVectorSegment("wa", (80.0, 22.0), (80.0, 50.0), f_lin),
            NativeVectorSegment("wb", (120.0, 22.0), (120.0, 50.0), f_lin),
        ),
        unmarked_texts=(TrustedFigureText("t1", "870", (100.0, 20.0), f_lin),),
    )
    assert pkt_um.dimension_proven is True
    assert pkt_um.width_mm == 870.0
    assert pkt_um.height_mm is None

    # 4. Collision negative: parallel-neighbor-only wall fails closed!
    parallel_only = CandidateHostWallBand("wall_parallel_only", h_lin, (0.0, 75.0), (300.0, 75.0), 8.0)
    pkt_fail = build_opening_evidence_handoff_shadow(
        opening_category="unmarked_opening",
        host_aperture=um_ap,
        candidate_walls=(parallel_only,),
        unmarked_target=UnmarkedOpeningTarget("phys_unmarked_01", f_lin, (80.0, 50.0), (120.0, 50.0)),
    )
    assert pkt_fail.host_membership_proven is False
    assert pkt_fail.first_remaining_gate == "no_authenticated_host_wall_found"


def test_handoff_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_opening_evidence_handoff_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
