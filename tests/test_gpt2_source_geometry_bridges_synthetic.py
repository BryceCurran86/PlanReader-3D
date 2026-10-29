"""Synthetic GPT2 source geometry bridges; tests are NOT implementation count."""
import hashlib

import fitz

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


# GPT2 source-native cyclic wall/finish ring correspondence: the PDF graph
# producer owns both ordered cycles; a common vertex *set* is not wall identity.
# Both are independently drawn SIMPLE, ORTHOGONAL native-PDF rings.
# The same ten source vertices can connect into different cyclic perimeters.
# Do not relax the actual graph producer's orthogonal-stroke contract.
_RING_A=(
    (80.,20.),(20.,20.),(20.,40.),(20.,60.),(20.,80.),
    (80.,80.),(80.,60.),(40.,60.),(40.,40.),(80.,40.),
)
_RING_RIVAL=(
    (80.,20.),(20.,20.),(20.,40.),(40.,40.),(40.,60.),
    (20.,60.),(20.,80.),(80.,80.),(80.,60.),(80.,40.),
)


def _two_original_source_rings(finish_vertices, *, shift=(10.0,7.0)):
    source=fitz.open()
    for ring,offset in ((_RING_A,(0.0,0.0)),(finish_vertices,shift)):
        page=source.new_page(width=240,height=240)
        coords=tuple((x+offset[0],y+offset[1]) for x,y in ring)
        for i in range(len(coords)):
            page.draw_line(coords[i],coords[(i+1)%len(coords)],
                           color=(0,0,0),width=.48)
    data=source.tobytes()
    source.close()
    digest=hashlib.sha256(data).hexdigest()
    ids=tuple(f"d{i}i0" for i in range(len(_RING_A)))
    floor=graph(data,source_sha256=digest,page_1_based=1,source_edge_ids=ids)
    finish=graph(data,source_sha256=digest,page_1_based=2,source_edge_ids=ids)
    assert floor["native_candidate_ring_count"]==1, floor["status"]
    assert finish["native_candidate_ring_count"]==1, finish["status"]
    assert floor["original_native_edge_ids"]==finish["original_native_edge_ids"]

    def native_key(ends, translation=(0.,0.)):
        return frozenset((round(float(p[0])+translation[0],3),
                          round(float(p[1])+translation[1],3))
                         for p in ends)

    finish_by_edge={native_key(edge["endpoints_pdf_pts"]):edge
                    for edge in finish["original_native_edges"]}
    matching=[]
    for edge in floor["original_native_edges"]:
        partner=finish_by_edge.get(native_key(edge["endpoints_pdf_pts"],shift))
        if partner is not None:
            matching.append((edge,partner))
    # Even the competing simple ring shares four real ink strokes; those
    # witnesses do not prove that its remaining perimeter is equivalent.
    assert len(matching)>=4
    roles=("left","right","bottom","top_partial")
    witnesses={}
    for role,(floor_edge,finish_edge) in zip(roles,matching[:4]):
        witnesses[role]={
            "floor_source":{
                "identity":floor_edge["source_id"],
                "ends":floor_edge["endpoints_pdf_pts"],
            },
            "finish_source":{
                "identity":finish_edge["source_id"],
                "ends":finish_edge["endpoints_pdf_pts"],
            },
            "matched_original_ink_only":True,
            "physical_wall_role_proven":False,
        }
    registration={
        "status":"original_four_edge_ink_correspondence_with_unclosed_doorway",
        "original_source_sha256":digest,
        "original_floor_page_id":1,
        "original_finish_page_id":2,
        "source_translation_candidate_pdf_pts":shift,
        "original_witnesses":witnesses,
    }
    return floor,finish,registration


def test_original_source_cyclic_ring_matches_translated_natively_extracted_edges():
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    accepted=compare(floor,finish,original_source_registration=receipt,
                     translation_pdf_pts=(10.0,7.0))
    assert accepted["status"]=="original_source_ink_ring_translation_candidate"
    assert accepted["first_failure"]=="W4_structural_wall_and_physical_room_identity"
    assert accepted["physical_room_identity_proven"] is False
    assert accepted["new_firm_quantities"]==0


def test_original_source_same_vertices_different_cyclic_wall_membership_abstains():
    floor,finish,receipt=_two_original_source_rings(_RING_RIVAL)
    source_ring=floor["native_components"][0]["source_simple_ring_candidate"]
    rival_ring=finish["native_components"][0]["source_simple_ring_candidate"]
    shifted={(round(x+10.,3),round(y+7.,3))
             for x,y in source_ring["vertices_pdf_pts"]}
    assert shifted==set(map(tuple,rival_ring["vertices_pdf_pts"]))
    assert len(source_ring["source_edge_ids"])==len(rival_ring["source_edge_ids"])
    rejected=compare(floor,finish,original_source_registration=receipt,
                     translation_pdf_pts=(10.0,7.0))
    assert rejected["status"]=="source_floor_finish_ring_correspondence_abstained"
    assert rejected["first_failure"]=="competing_cross_sheet_original_perimeter"
    assert rejected["new_firm_quantities"]==0


def test_original_source_ring_cyclic_rotation_reversal_and_deterministic_replay():
    # Neither the original ink stroke starting point nor its traversal
    # direction changes the physical cyclic edge set.
    for ring in (_RING_A[2:]+_RING_A[:2],
                 tuple(reversed(_RING_A)),
                 tuple(reversed(_RING_A[3:]+_RING_A[:3]))):
        floor,finish,receipt=_two_original_source_rings(ring)
        first=compare(floor,finish,original_source_registration=receipt,
                      translation_pdf_pts=(10.0,7.0))
        second=compare(floor,finish,original_source_registration=receipt,
                       translation_pdf_pts=(10.0,7.0))
        assert first==second
        assert first["status"]=="original_source_ink_ring_translation_candidate"
        assert first["new_firm_quantities"]==0


def test_original_registration_witnesses_fail_closed_on_malformed_nested_receipts():
    # All source roles must be typed original-edge identities. Malformed
    # nested receipts must ABSTAIN, not crash or become a source candidate.
    from copy import deepcopy
    floor,finish,registration=_two_original_source_rings(_RING_A)
    bad_roles=(
        None, [], "untrusted", 42,
        {"floor_source":None,"finish_source":{"identity":"d0i0"}},
        {"floor_source":{"identity":"d0i0"},"finish_source":None},
        {"floor_source":{"identity":["d0i0"]},
         "finish_source":{"identity":"d0i0"}},
        {"floor_source":{"identity":"d0i0"},
         "finish_source":{"identity":{"id":"d0i0"}}},
        {"floor_source":{"identity":"unknown"},
         "finish_source":{"identity":"d0i0"}},
    )
    for role in bad_roles:
        receipt=deepcopy(registration)
        receipt["original_witnesses"]["left"]=role
        result=compare(floor,finish,original_source_registration=receipt,
                       translation_pdf_pts=(10.0,7.0))
        assert result["status"]=="source_floor_finish_ring_correspondence_abstained"
        assert result["first_failure"]=="unjoined_source_wall_ancestry"
        assert result["new_firm_quantities"]==0


def test_original_registration_reused_wall_witness_is_not_independent_proof():
    from copy import deepcopy
    floor,finish,registration=_two_original_source_rings(_RING_A)
    receipt=deepcopy(registration)
    receipt["original_witnesses"]["right"]=deepcopy(
        receipt["original_witnesses"]["left"])
    result=compare(floor,finish,original_source_registration=receipt,
                   translation_pdf_pts=(10.0,7.0))
    assert result["first_failure"]=="original_registration_witness_identity_alias_conflict"
    assert result["new_firm_quantities"]==0
    # Two genuinely distinct native source identities remain candidates only.
    receipt["original_witnesses"]["right"]=deepcopy(
        registration["original_witnesses"]["right"])
    candidate=compare(floor,finish,original_source_registration=receipt,
                      translation_pdf_pts=(10.0,7.0))
    assert candidate["status"]=="original_source_ink_ring_translation_candidate"
    assert candidate["physical_room_identity_proven"] is False
    assert candidate["new_firm_quantities"]==0


def test_original_registration_transform_receipt_invalid_shapes_abstain():
    from copy import deepcopy
    floor,finish,registration=_two_original_source_rings(_RING_A)
    for shift in (None,False,0,"10,7",{"x":10,"y":7},
                  (10.,), (10.,7.,0.), (True,7.),
                  (float("nan"),7.), (float("inf"),7.),
                  (10**1000,7.)):
        receipt=deepcopy(registration)
        receipt["source_translation_candidate_pdf_pts"]=shift
        result=compare(floor,finish,original_source_registration=receipt,
                       translation_pdf_pts=(10.0,7.0))
        assert result["status"]=="source_floor_finish_ring_correspondence_abstained"
        assert result["first_failure"]=="original_registration_issuer_or_scope_missing"
        assert result["new_firm_quantities"]==0


def test_original_direct_translation_argument_overflow_and_invalid_types_abstain():
    # The caller's direct transform must fail closed as strictly as the
    # nested original-source registration witness, including huge Python ints.
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    for shift in (
        None, False, [], "10,7", (10.,), (10.,7.,0.),
        (True,7.), (float("nan"),7.), (float("inf"),7.),
        (10**1000,7.), (-10**1000,7.),
    ):
        rejected=compare(floor,finish,original_source_registration=receipt,
                         translation_pdf_pts=shift)
        assert rejected["status"]=="source_floor_finish_ring_correspondence_abstained"
        assert rejected["first_failure"]=="original_registration_transform_invalid"
        assert rejected["physical_room_identity_proven"] is False
        assert rejected["new_firm_quantities"]==0
    accepted=compare(floor,finish,original_source_registration=receipt,
                     translation_pdf_pts=(10.,7.))
    assert accepted["status"]=="original_source_ink_ring_translation_candidate"
    assert accepted["first_failure"]=="W4_structural_wall_and_physical_room_identity"
    assert accepted["physical_room_identity_proven"] is False
    assert accepted["new_firm_quantities"]==0


def test_original_ring_side_membership_must_equal_issued_native_graph_edges():
    # Native PDF issuer proves edge ancestry, not an unverified ring receipt.
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    for side in ("floor","finish"):
        for wrong in (
            ("d999i0",)+tuple(floor["original_native_edge_ids"][1:]),
            ("d0i0",)+tuple(floor["original_native_edge_ids"][1:-1])+("d0i0",),
            (["d0i0"],)+tuple(floor["original_native_edge_ids"][1:]),
            None,
        ):
            a,b=deepcopy(floor),deepcopy(finish)
            graph_side=a if side=="floor" else b
            graph_side["native_components"][0]["source_simple_ring_candidate"][
                "source_edge_ids"]=wrong
            rejected=compare(a,b,original_source_registration=receipt,
                             translation_pdf_pts=(10.0,7.0))
            assert rejected["status"]=="source_floor_finish_ring_correspondence_abstained"
            assert rejected["first_failure"]=="original_cross_sheet_edge_membership_count_conflict"
            assert rejected["physical_room_identity_proven"] is False
            assert rejected["new_firm_quantities"]==0
    positive=compare(floor,finish,original_source_registration=receipt,
                     translation_pdf_pts=(10.0,7.0))
    assert positive["status"]=="original_source_ink_ring_translation_candidate"
    assert positive["new_firm_quantities"]==0


def test_original_native_graph_ids_reject_unhashable_and_duplicate_receipts():
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    for malformed in (
        (["d0i0"],)+tuple(floor["original_native_edge_ids"][1:]),
        ("d0i0","d0i0")+tuple(floor["original_native_edge_ids"][2:]),
        None,
        "d0i0",
    ):
        bad=deepcopy(floor)
        bad["original_native_edge_ids"]=malformed
        result=compare(bad,finish,original_source_registration=receipt,
                       translation_pdf_pts=(10.0,7.0))
        assert result["status"]=="source_floor_finish_ring_correspondence_abstained"
        assert result["first_failure"]=="unjoined_source_wall_ancestry"
        assert result["new_firm_quantities"]==0


def test_original_native_edge_endpoints_must_match_ring_source_geometry():
    # A forged ring may reuse every genuine source ID and remain cross-sheet
    # geometrically identical, while disagreeing with the original PDF ink.
    # Original producer endpoints are the independent ancestry witness.
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    good=compare(floor,finish,original_source_registration=receipt,
                 translation_pdf_pts=(10.0,7.0))
    assert good["status"]=="original_source_ink_ring_translation_candidate"
    for side in ("floor","finish"):
        for mutation in ("shift_endpoint","foreign_id","duplicate_id",
                         "missing_edges","unhashable_endpoint",
                         "nonfinite_endpoint","huge_integer_endpoint"):
            a,b=deepcopy(floor),deepcopy(finish)
            graph_side=a if side=="floor" else b
            native=list(graph_side["original_native_edges"])
            if mutation=="missing_edges":
                graph_side["original_native_edges"]=None
            else:
                first=dict(native[0])
                if mutation=="foreign_id":
                    first["source_id"]="d999i0"
                elif mutation=="duplicate_id":
                    first["source_id"]=native[1]["source_id"]
                else:
                    ends=list(first["endpoints_pdf_pts"])
                    if mutation=="shift_endpoint":
                        ends[0]=(ends[0][0]+1.0,ends[0][1])
                    elif mutation=="unhashable_endpoint":
                        ends[0]=([ends[0][0]],ends[0][1])
                    elif mutation=="nonfinite_endpoint":
                        ends[0]=(float("nan"),ends[0][1])
                    elif mutation=="huge_integer_endpoint":
                        ends[0]=(10**1000,ends[0][1])
                    first["endpoints_pdf_pts"]=tuple(ends)
                native[0]=first
                graph_side["original_native_edges"]=tuple(native)
            rejected=compare(a,b,original_source_registration=receipt,
                             translation_pdf_pts=(10.0,7.0))
            assert rejected["status"]=="source_floor_finish_ring_correspondence_abstained"
            assert rejected["first_failure"]=="original_native_edge_endpoint_ancestry_conflict"
            assert rejected["physical_room_identity_proven"] is False
            assert rejected["new_firm_quantities"]==0


def test_coherently_replaced_source_rings_cannot_borrow_original_edge_ids():
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    a,b=deepcopy(floor),deepcopy(finish)
    a["native_components"][0]["source_simple_ring_candidate"][
        "vertices_pdf_pts"]=_RING_RIVAL
    b["native_components"][0]["source_simple_ring_candidate"][
        "vertices_pdf_pts"]=tuple((x+10.,y+7.) for x,y in _RING_RIVAL)
    # The altered polygons match EACH OTHER and preserve every native ID;
    # only the actual original endpoint receipt can detect this forgery.
    rejected=compare(a,b,original_source_registration=receipt,
                     translation_pdf_pts=(10.0,7.0))
    assert rejected["first_failure"]=="original_native_edge_endpoint_ancestry_conflict"
    assert rejected["new_firm_quantities"]==0
    assert rejected["physical_room_identity_proven"] is False
    assert compare(floor,finish,original_source_registration=receipt,
                   translation_pdf_pts=(10.0,7.0))["status"]==(
                       "original_source_ink_ring_translation_candidate")


def test_original_four_side_issuer_roles_and_ink_proof_are_mandatory():
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    for mutation in ("missing_role","extra_role","missing_proof",
                     "false_proof","untyped_role","untyped_witnesses"):
        bad=deepcopy(receipt)
        witnesses=bad["original_witnesses"]
        if mutation=="missing_role":
            witnesses.pop("bottom")
        elif mutation=="extra_role":
            witnesses["unregistered"]=deepcopy(witnesses["left"])
        elif mutation=="missing_proof":
            witnesses["left"].pop("matched_original_ink_only")
        elif mutation=="false_proof":
            witnesses["left"]["matched_original_ink_only"]=False
        elif mutation=="untyped_role":
            witnesses["left"]=None
        else:
            bad["original_witnesses"]=["left","right","bottom","top_partial"]
        result=compare(floor,finish,original_source_registration=bad,
                       translation_pdf_pts=(10.,7.))
        assert result["status"]=="source_floor_finish_ring_correspondence_abstained"
        assert result["first_failure"]==(
            "original_registration_ink_witness_unproven"
            if mutation in ("missing_proof","false_proof") else
            "unjoined_source_wall_ancestry" if mutation=="untyped_role" else
            "original_registration_four_side_witnesses_missing")
        assert result["new_firm_quantities"]==0
    assert compare(floor,finish,original_source_registration=receipt,
                   translation_pdf_pts=(10.,7.))["status"]==(
                       "original_source_ink_ring_translation_candidate")


def test_original_four_side_witness_endpoints_must_match_both_native_issuers():
    from copy import deepcopy
    floor,finish,receipt=_two_original_source_rings(_RING_A)
    for side in ("floor_source","finish_source"):
        for mutation in ("missing_ends","shift_ends","wrong_native_edge",
                         "nonfinite","huge_integer","unhashable"):
            bad=deepcopy(receipt)
            witness=bad["original_witnesses"]["left"][side]
            if mutation=="missing_ends":
                witness.pop("ends")
            elif mutation=="wrong_native_edge":
                witness["ends"]=deepcopy(
                    receipt["original_witnesses"]["right"][side]["ends"])
            else:
                ends=list(witness["ends"])
                first=list(ends[0])
                if mutation=="shift_ends":
                    first[0]+=1.
                elif mutation=="nonfinite":
                    first[0]=float("nan")
                elif mutation=="huge_integer":
                    first[0]=10**1000
                else:
                    first[0]=[first[0]]
                ends[0]=tuple(first)
                witness["ends"]=tuple(ends)
            result=compare(floor,finish,original_source_registration=bad,
                           translation_pdf_pts=(10.,7.))
            assert result["status"]=="source_floor_finish_ring_correspondence_abstained"
            assert result["first_failure"]=="original_registration_witness_geometry_conflict"
            assert result["physical_room_identity_proven"] is False
            assert result["new_firm_quantities"]==0
    assert compare(floor,finish,original_source_registration=receipt,
                   translation_pdf_pts=(10.,7.))["status"]==(
                       "original_source_ink_ring_translation_candidate")
