"""Synthetic functional examples for distinct GPT1 quantity calculators.

These examples are NOT owner-authenticated source evidence or FIRM output.
"""
import math
from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide, FiguredPolygonMetricShadow
from pb_gpt1_figured_wall_surface_shadow import (
    DocumentedWallHeight, DocumentedWallOpening, measure_figured_wall_lining_shadow,
)
from pb_gpt1_figured_finish_zones_shadow import (
    OriginalFiguredFinishZone, measure_figured_finish_zones_shadow,
)
from pb_gpt1_figured_ceiling_grid_shadow import (
    DocumentedCeilingGridSystem, measure_source_figured_ceiling_grid_shadow,
)
from pb_gpt1_original_figured_face_witness_shadow import (
    SourceFiguredAxis, SourceStructuralFaceStroke,
    source_figured_terminal_wall_faces_shadow,
)
from pb_gpt1_figured_open_plan_sections_shadow import (
    OriginalOpenPlanSection, partition_figured_open_plan_sections_shadow,
)
from pb_gpt1_figured_wall_elevation_shadow import (
    SourceFiguredElevationStation, measure_source_figured_wall_elevation_shadow,
)
from pb_gpt1_figured_layer_volume_shadow import (
    OriginalMaterialLayer, measure_source_figured_layer_volumes_shadow,
)
from pb_gpt1_figured_finish_interface_shadow import (
    OriginalFinishInterfaceFace, measure_figured_finish_transition_trims_shadow,
)
from pb_gpt1_figured_opening_reveals_shadow import (
    DocumentedPhysicalOpeningFrame, measure_source_figured_opening_reveals_shadow,
)

SHA = "a" * 64


def metric(points=((0,0),(10000,0),(10000,5000),(0,5000)), area=50.0):
    return FiguredPolygonMetricShadow(
        Status.CANDIDATE, ("synthetic",), area, points, ("figure-source",), (),
        SHA, "rev", "7", "room-one",
    )


def test_figured_wall_gross_net_opening_and_skirting():
    ring=tuple(
        FiguredPhysicalSide(f"side-{i}",(0,i),(0,i+1),(f"ink-{i}",))
        for i in range(4)
    )
    heights=tuple(DocumentedWallHeight(f"side-{i}",3000,(f"height-{i}",),SHA,"rev","7")
                  for i in range(4))
    door=DocumentedWallOpening(
        "door-1","side-0",1000,2100,"signed-void-1",
        ("host-evidence",),("frame-evidence",),SHA,"rev","7",
        published_original_opening_area_m2=2.1,
    )
    measured=measure_figured_wall_lining_shadow(ring,metric(),heights,(door,))
    assert measured.status is Status.CANDIDATE
    assert measured.candidate_perimeter_m==30.0
    assert measured.candidate_gross_lining_m2==90.0
    assert math.isclose(measured.candidate_net_lining_m2,87.9)
    assert measured.candidate_skirting_m==29.0
    assert measured.candidate_opening_deductions_m2==(("door-1",2.1),)


def test_figured_finish_zones_publish_distinct_candidate_material_areas():
    parent=metric()
    outer=((0,0),(10,0),(10,5),(0,5))
    left=((0,0),(5,0),(5,5),(0,5))
    right=((5,0),(10,0),(10,5),(5,5))
    left_rec=OriginalFiguredFinishZone(
        "left",left,metric(((0,0),(5000,0),(5000,5000),(0,5000)),25),
        "FT2","tile","definition-ft2","original-mark-ft2",
        ("source-mark-ft2",),"11","registration-1",
    )
    right_rec=replace(
        left_rec,physical_zone_id="right",original_zone_pdf_ring=right,
        material_code="FT3",semantic_finish="resin",
        source_definition_id="definition-ft3",
        source_occurrence_id="original-mark-ft3",
        source_material_evidence_ids=("source-mark-ft3",),
    )
    r=measure_figured_finish_zones_shadow(parent,outer,(left_rec,right_rec),
                                          require_complete_finish_coverage=True)
    assert r.status is Status.CANDIDATE
    assert r.candidate_finish_areas_m2 == (
        ("left","FT2",25),("right","FT3",25)
    )
    assert r.candidate_remaining_unassigned_m2==0


def test_grid_full_cells_and_both_original_support_rail_axes():
    orig=metric()
    system=DocumentedCeilingGridSystem(
        "ceiling-one",(0,0),1000,1000,0,
        ("grid-native-module",),("grid-native-origin",),
        SHA,"rev","7",
    )
    out=measure_source_figured_ceiling_grid_shadow(orig,system)
    assert out.status is Status.CANDIDATE
    assert out.full_panel_count_candidate==50
    assert out.cut_panel_count_candidate==0
    assert out.total_panel_count_candidate==50
    assert out.coverage_area_m2==50
    assert out.grid_tee_length_m_by_axis == (45.0, 40.0)


def test_figured_vertical_axis_joins_only_unique_finished_transverse_faces():
    dim=SourceFiguredAxis("original-3570",3570,"vertical",
                         (157.68,1774.64),(157.68,2179.52),
                         ("terminal-1","terminal-2"),"26")
    a=SourceStructuralFaceStroke("face-top",(200,1774.64),(300,1774.64),
                                 "physical-wall-top","finished_inner_face","style-1")
    b=SourceStructuralFaceStroke("face-bottom",(200,2179.52),(300,2179.52),
                                 "physical-wall-bottom","finished_inner_face","style-1")
    r=source_figured_terminal_wall_faces_shadow(dim,(a,b))
    assert r.status is Status.CANDIDATE
    assert r.uniquely_bound_face_ids==("face-top","face-bottom")
    outer=replace(a,original_stroke_id="outer-rival",classified_physical_wall_id="rival")
    conflict=source_figured_terminal_wall_faces_shadow(dim,(a,b,outer))
    assert conflict.status is Status.ABSTAINED
    assert "face-top" in conflict.terminal_competitor_ids[0]


def test_open_plan_sections_share_only_one_sourced_divider():
    parent=metric()
    left=OriginalOpenPlanSection(
        "food-service","room-one",((0,0),(5,0),(5,5),(0,5)),
        metric(((0,0),(5000,0),(5000,5000),(0,5000)),25),
        ("left-bottom","shared-divider","left-top","left-outer"),
        ("label-food-service",),
    )
    right=OriginalOpenPlanSection(
        "pos-counter","room-one",((5,0),(10,0),(10,5),(5,5)),
        metric(((5000,0),(10000,0),(10000,5000),(5000,5000)),25),
        ("right-bottom","right-outer","right-top","shared-divider"),
        ("label-pos-counter",),
    )
    result=partition_figured_open_plan_sections_shadow(
        parent,((0,0),(10,0),(10,5),(0,5)),(left,right)
    )
    assert result.status is Status.CANDIDATE
    assert result.candidate_section_areas_m2 == (
        ("food-service",25),("pos-counter",25)
    )
    assert result.candidate_unallocated_area_m2==0
    assert result.candidate_shared_divider_length_m==5.0


def test_figured_nonrect_wall_elevation_integrates_a_raked_edge():
    records=(
        SourceFiguredElevationStation(0,3000,"x0","h0",("w0a","w0b")),
        SourceFiguredElevationStation(10000,5000,"x1","h1",("w1a","w1b")),
    )
    r=measure_source_figured_wall_elevation_shadow(
        physical_wall_id="wall-1",figured_wall_length_mm=10000,
        source_wall_length_figure_id="original-length",
        source_sha256=SHA,revision_id="rev",page_id="7",stations=records,
    )
    assert r.status is Status.CANDIDATE
    assert r.candidate_face_area_m2==40
    assert math.isclose(r.candidate_upper_edge_length_m,math.hypot(10,2))


def test_figured_layers_produce_independent_source_thickness_volumes():
    layers=(
        OriginalMaterialLayer("slab","surface","CONC","def-conc",100,
                              ("depth-slab",),SHA,"rev","7"),
        OriginalMaterialLayer("screed","surface","SCD","def-screed",50,
                              ("depth-screed",),SHA,"rev","7"),
    )
    r=measure_source_figured_layer_volumes_shadow(metric(),"surface",layers)
    assert r.status is Status.CANDIDATE
    assert r.candidate_volume_by_layer_m3 == (("screed",2.5),("slab",5.0))
    assert r.candidate_total_volume_m3==7.5


def test_figured_material_transition_length_deduplicates_two_zone_faces():
    left=OriginalFinishInterfaceFace(
        "physical-interface","zone-ft2","occurrence-ft2","FT2",
        (5000,0),(5000,5000),("shared-ink",),SHA,"rev","7",
    )
    right=replace(left,physical_zone_id="zone-ft3",
                  source_material_occurrence_id="occurrence-ft3",
                  material_code="FT3",start_metric_mm=(5000,5000),
                  end_metric_mm=(5000,0))
    r=measure_figured_finish_transition_trims_shadow((left,right))
    assert r.status is Status.CANDIDATE
    assert r.candidate_total_trim_length_m==5
    assert r.distinct_material_pairs==(("FT2","FT3"),)


def test_figured_opening_reveals_keep_door_and_window_sills_distinct():
    door=DocumentedPhysicalOpeningFrame(
        "physical-open-1","door",1000,2000,100,
        "width","height","depth","host-wall",
        ("host-evidence",),("frame-evidence",),SHA,"rev","7",
    )
    a=measure_source_figured_opening_reveals_shadow(door)
    b=measure_source_figured_opening_reveals_shadow(
        replace(door,physical_opening_id="window-one",
                source_opening_kind="window")
    )
    assert a.status is Status.CANDIDATE and b.status is Status.CANDIDATE
    assert a.candidate_reveal_surface_m2==0.5
    assert b.candidate_reveal_surface_m2==0.6
    assert a.candidate_frame_linear_m==5
    assert b.candidate_frame_linear_m==6
    assert a.candidate_structural_void_area_m2==2


def test_hosted_opening_cannot_deduct_without_existing_source_signed_area():
    ring=tuple(FiguredPhysicalSide(f"side-{i}",(0,i),(0,i+1),(f"ink-{i}",))
               for i in range(4))
    heights=tuple(DocumentedWallHeight(f"side-{i}",3000,(f"height-{i}",),SHA,"rev","7")
                  for i in range(4))
    baseline=DocumentedWallOpening(
        "door-1","side-0",1000,2100,"area-issuer",
        ("host-evidence",),("frame-evidence",),SHA,"rev","7",
    )
    for candidate in (baseline,replace(baseline,published_original_opening_area_m2=1.5)):
        result=measure_figured_wall_lining_shadow(ring,metric(),heights,(candidate,))
        assert result.status is Status.ABSTAINED
        assert result.candidate_net_lining_m2 is None
