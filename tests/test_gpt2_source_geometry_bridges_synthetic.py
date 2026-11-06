"""Synthetic GPT2 source geometry bridges; tests are NOT implementation count."""
import hashlib

import fitz
import pytest

from tools.diag_gpt2_source_room_graph_shadow import (
    audit_original_room_edge_graph as graph,
)
from tools.diag_gpt2_source_finish_floor_handoff_shadow import (
    audit_gpt2_original_cross_sheet_ring_correspondence as compare,
    audit_gpt2_source_material_floor_handoff as material_handoff,
    audit_gpt2_competing_source_floor_handoffs as floor_universe,
)
from tools.diag_gpt2_original_doorway_room_closure_shadow import (
    audit_original_doorway_ring_candidate as doorway,
)
from tools.diag_gpt2_source_rcp_geometry_shadow import (
    audit_original_rcp_grid_ink_intersections as crossings,
    audit_competing_original_rcp_zone_owners as ceiling_universe,
)


def _source(*,open_top=False, crossing=False):
    pdf=fitz.open()
    p=pdf.new_page(width=280,height=230)
    lines=[
        ((20,20),(20,120)),
        ((20,120),(120,120)),
        ((120,120),(120,20)),
        ((70,20),(120,20)) if open_top else ((20,20),(120,20)),
    ]
    if open_top:
        lines.append(((20,20),(40,20)))
    if crossing:
        lines.append(((70,0),(70,200)))
    for a,b in lines:
        p.draw_line(a,b,color=(0,0,0),width=.48)
    data=pdf.tobytes()
    pdf.close()
    return data,tuple(f"d{i}i0" for i in range(len(lines)))


def test_gpt2_simple_original_closed_source_ring_has_pdf_area_not_metric_area():
    data,ids=_source()
    result=graph(data,source_sha256=hashlib.sha256(data).hexdigest(),
                 page_1_based=1,source_edge_ids=ids)
    assert result["status"]=="original_closed_ink_ring_candidates_only"
    assert result["native_candidate_ring_count"]==1
    ring=result["native_components"][0]["source_simple_ring_candidate"]
    assert ring["native_area_pdf_pt2"]==10000.
    assert len(result["original_native_edges"])==4
    assert not result["source_physical_room_identity_issued"]
    assert not result["source_room_metric_area_issued"]
    assert result["new_firm_quantities"]==0


def test_open_original_room_has_two_actual_unjoined_door_endpoints():
    data,ids=_source(open_top=True)
    source=graph(data,source_sha256=hashlib.sha256(data).hexdigest(),
                 page_1_based=1,source_edge_ids=ids)
    assert source["status"]=="original_source_branches_or_open_ends"
    assert source["native_candidate_ring_count"]==0
    endpoints=source["native_components"][0]["source_open_endpoint_coordinates_pdf_pts"]
    assert {tuple(p) for p in endpoints}=={(40.,20.),(70.,20.)}
    gaps=source["native_components"][0]["native_unfilled_collinear_gap_candidates"]
    assert gaps[0]["native_gap_distance_pdf_pt"]==30.
    assert not gaps[0]["source_gap_filled_by_imputation"]


def test_native_crossing_does_not_mint_a_false_enclosed_room():
    data,ids=_source(crossing=True)
    outcome=graph(data,source_sha256=hashlib.sha256(data).hexdigest(),
                  page_1_based=1,source_edge_ids=ids)
    assert outcome["interior_stroke_intersections_and_overlaps"]
    assert outcome["status"]=="original_native_stroke_intersection_competition"
    assert outcome["native_candidate_ring_count"]==0
    assert outcome["new_firm_quantities"]==0


def test_jamb_bound_virtual_closure_is_not_a_real_wall_or_metric_area():
    data,ids=_source(open_top=True)
    pdf=fitz.open(stream=data,filetype="pdf")
    # The second PDF is only for creating independent jamb ink; this source
    # bytes file must hold both original wall fragments and jamb returns.
    page=pdf[0]
    page.draw_line((40,20),(40,26),color=(0,0,0),width=.96)
    page.draw_line((70,20),(70,26),color=(0,0,0),width=.96)
    raw=pdf.tobytes()
    printed=page.get_drawings()
    receipt={
        "status":"exact_original_native_jamb_endpoint_chain_candidate",
        "native_ink_contact_proved":True,
        "original_pdf_page_index_zero_based":0,
        "source_native_wall_run_axis":"native_x",
        "source_original_wall_axis_pdf_pt":20.,
        "source_native_unbridged_wall_gap_pdf_pts":[40.,70.],
        "original_primitive_paths":{},
    }
    for role,ident in {
        "left_wall":"d4i0","right_wall":"d3i0",
        "left_jamb":"d5i0","right_jamb":"d6i0",
    }.items():
        item=printed[int(ident[1:-2])]["items"][0]
        a,b=item[1:3]
        receipt["original_primitive_paths"][role]={
            "original_source_primitive_id":ident,
            "original_native_endpoints_pdf_pts":[
                round(a.x,3),round(a.y,3),round(b.x,3),round(b.y,3)
            ],
        }
    pdf.close()
    source=graph(raw,source_sha256=hashlib.sha256(raw).hexdigest(),
                 page_1_based=1,source_edge_ids=ids)
    result=doorway(
        raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
        original_page_1_based=1,source_room_graph=source,
        original_jamb_source_receipt=receipt,
    )
    assert result["status"]=="source_jamb_bound_open_door_perimeter_candidate_only"
    assert result["source_jamb_roles_same_sha_rechecked"]
    assert not result["source_virtual_door_connector_is_structural_wall"]
    assert result["source_only_native_polygon_area_pdf_pt2_not_m2"]==10000.
    assert result["new_firm_quantities"]==0


def test_ft2_ft3_handoff_must_have_real_producer_issued_source_authority():
    candidate={"status":"original_source_ink_ring_translation_candidate",
               "original_source_sha256":"a"*64}
    outcome=material_handoff(candidate,material_authority=None,
                             definition_selector=None,
                             occurrence_selector=None,
                             original_finish_code="FT3")
    assert outcome["first_failure"]=="producer_owned_material_authority_required"
    assert not outcome["canonical_floor_finish_quantity_granted"]
    assert outcome["new_firm_quantities"]==0


def test_reused_original_finish_occurrence_cannot_be_assigned_to_two_rooms():
    c={"status":"source_owned_material_on_original_ink_ring_candidate",
       "original_source_sha256":"f"*64,"original_revision_id":"one",
       "original_snapshot_id":"snapshot",
       "original_mark_source_record_ids":("ft3-source-mark",)}
    result=floor_universe((c,dict(c)))
    assert result["status"]=="original_finish_mark_competing_physical_rooms"
    assert len(result["original_mark_ownership_conflicts"])==1
    assert not result["unique_source_mark_identity_elected"]


def test_original_rcp_grid_crossings_require_actual_source_segments():
    grid=(
        {"original_source_axis":"source_grid_vertical_candidate",
         "source_ink":{"ends":((30.,15.),(30.,110.))}},
        {"original_source_axis":"source_grid_horizontal_candidate",
         "source_ink":{"ends":((15.,55.),(110.,55.))}},
        {"original_source_axis":"source_grid_horizontal_candidate",
         "source_ink":{"ends":((60.,70.),(110.,70.))}},
    )
    result=crossings({
        "status":"original_rcp_source_ink_ceiling_polygon_candidate",
        "source_ceiling_ink_polygon_pdf_pts":(
            (20.,20.),(100.,20.),(100.,100.),(20.,100.)),
        "original_grid_source_ink_candidates":grid,
    })
    assert result["original_source_grid_intersections_pdf_pts"]==((30.,55.),)
    assert not result["source_ceiling_area_or_grid_quantity_issued"]


def test_competing_original_rcp_grid_lines_not_issued_to_two_zones():
    zone={"status":"original_rcp_source_ink_ceiling_polygon_candidate",
          "original_source_sha256":"f"*64,
          "original_revision_id":"r","original_snapshot_id":"s",
          "source_boundary_graph":{"original_native_edge_ids":("d0i0",)},
          "original_grid_source_ink_candidates":(
              {"native_source_id":"d5i0"},)}
    result=ceiling_universe((zone,dict(zone)))
    assert result["status"]=="original_rcp_competing_zone_source_ownership"
    assert len(result["source_competing_grid_boundary_or_finish_mark_owners"])==2
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("rival_position", ["inside", "crossing", "outside"])
def test_source_material_handoff_keeps_all_other_finish_code_rivals(
    reverse, rival_position,
):
    """A viewport-scoped original FT3 result cannot hide an in-room FT2."""
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    import pb_source_material_semantic_authority as semantic

    sha="a"*64
    lineage=dict(
        document_id="source-document", revision_id="source-revision",
        source_sha256=sha, snapshot_id="source-snapshot",
    )
    definition_selector=semantic.SourceMaterialDefinitionSelector(
        **lineage, code="FT3",
    )
    occurrence_selector=semantic.SourceMaterialOccurrenceSelector(
        **lineage, page_id="11", viewport_id="source-finish-plan",
    )
    definition=semantic.SourceMaterialDefinitionRecord(
        record_id="source-ft3-definition", **lineage,
        code="FT3", description="Floor tile FT3", substrate="",
        finish="tile", semantic_finish="tile",
        source_definition_ids=("source-def-word",),
        source_page_ids=("11",),
        source_viewport_ids=("source-finish-plan",),
    )
    ft3=semantic.SourceMaterialOccurrenceRecord(
        record_id="source-ft3-office", **lineage,
        page_id="11", viewport_id="source-finish-plan",
        code="FT3", semantic_finish="tile",
        definition_record_id=definition.record_id,
        bbox_pdf_pts=(20.,20.,30.,30.),
        raw_text="FT3",source_evidence_id="source-text-ft3",
        source_text_observation_ids=("source-word-ft3",),
    )
    rival_rect={
        "inside":(50.,20.,60.,30.),
        "crossing":(95.,20.,105.,30.),
        "outside":(130.,20.,140.,30.),
    }[rival_position]
    ft2=semantic.SourceMaterialOccurrenceRecord(
        record_id="source-ft2-rival", **lineage,
        page_id="11", viewport_id="source-finish-plan",
        code="FT2", semantic_finish="tile",
        definition_record_id="source-ft2-definition",
        bbox_pdf_pts=rival_rect,
        raw_text="FT2",source_evidence_id="source-text-ft2",
        source_text_observation_ids=("source-word-ft2",),
    )
    rows=(ft2,ft3) if reverse else (ft3,ft2)
    authority=semantic.SourceMaterialSemanticAuthority(
        {
            definition_selector.key: semantic.SourceMaterialDefinitionResult(
                status=Status.CORROBORATED, reason_codes=(),
                record=definition,
            ),
        },
        {
            occurrence_selector.key: semantic.SourceMaterialOccurrenceScopeResult(
                status=Status.CORROBORATED, reason_codes=(),
                scope_complete=True,records=rows,
                source_viewport_ownership_id="source-finish-viewport-owner",
            ),
        },
        _seal=semantic._AUTHORITY_SEAL,
    )
    registration={
        "status":"original_source_ink_ring_translation_candidate",
        "original_source_sha256":sha,
        "original_floor_page":7,
        "original_finish_page":11,
        "source_floor_perimeter_polygon_pdf_pts":(
            (0.,0.),(100.,0.),(100.,100.),(0.,100.)
        ),
        "source_finishes_perimeter_polygon_pdf_pts":(
            (0.,0.),(100.,0.),(100.,100.),(0.,100.)
        ),
    }
    result=material_handoff(
        registration,material_authority=authority,
        definition_selector=definition_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="FT3",
    )
    if rival_position=="outside":
        assert result["status"]=="source_owned_material_on_original_ink_ring_candidate"
        assert result["original_mark_source_record_ids"]==(ft3.record_id,)
        assert result["all_same_code_source_occurrence_record_ids"]==(ft3.record_id,)
        assert not result["canonical_floor_finish_quantity_granted"]
    else:
        assert result["status"]=="source_finished_floor_material_handoff_abstained"
        assert result["first_failure"]=="competing_source_material_codes_in_one_room"
        assert result["competing_source_material_record_ids"]==(ft2.record_id,)
    assert result["new_firm_quantities"]==0
