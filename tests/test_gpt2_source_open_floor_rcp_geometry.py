"""Prove one original OPEN plan perimeter with exactly one unprinted chord.

No original PDF, physical W4 closure, wall snap, m2 or customer records.
"""
from copy import deepcopy

import pytest

from pb_gpt2_source_open_floor_rcp_geometry import (
    audit_source_open_floor_native_ink_virtual_gap as audit,
)


IDS = ("bottom", "left", "right", "top-left", "top-right")
POLY = ((0.,0.),(100.,0.),(100.,100.),(0.,100.))
EDGES = (
    ("bottom",((0.,0.),(100.,0.))),
    ("left",((0.,0.),(0.,100.))),
    ("right",((100.,0.),(100.,100.))),
    ("top-left",((0.,100.),(40.,100.))),
    ("top-right",((60.,100.),(100.,100.))),
)
DEGREES = (
    ((0.,0.),2),((0.,100.),2),((40.,100.),1),
    ((60.,100.),1),((100.,0.),2),((100.,100.),2),
)


def original_open_graph():
    return {
        "status":"original_source_branches_or_open_ends",
        "native_candidate_ring_count":0,
        "interior_stroke_intersections_and_overlaps":(),
        "original_native_edge_ids":IDS,
        "original_native_edges":tuple(
            {"source_id":key,"endpoints_pdf_pts":tuple(map(tuple,ends)),
             "source_ink_length_pdf_pt":1.}
            for key,ends in EDGES
        ),
        "native_components":({
            "source_edge_ids":IDS,
            "source_simple_ring_candidate":None,
            "source_branch_coordinates_pdf_pts":(),
            "source_open_endpoint_coordinates_pdf_pts":(
                (40.,100.),(60.,100.),
            ),
            "native_endpoint_degrees":tuple(
                {"point_pdf_pt":point,"degree":degree,
                 "original_source_edge_ids":()}
                for point,degree in DEGREES
            ),
        },),
    }


def source_result(graph=None, polygon=POLY):
    return audit(
        original_open_graph() if graph is None else graph,
        original_source_edge_ids=IDS,
        virtual_floor_vertices_pdf_pts=polygon,
    )


def test_exact_source_open_room_one_unprinted_doorway_chord_is_not_physical_wall():
    result=source_result()
    assert result["status"]=="source_open_floor_one_original_door_gap_candidate_only"
    assert result["original_source_floor_gap_endpoints_pdf_pts"]==(
        (40.,100.),(60.,100.),
    )
    assert result["source_original_physical_wall_closure_authenticated"] is False
    assert result["source_doorway_threshold_authenticated"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("mutation",[
    lambda g:g.update(status="original_closed_ink_ring_candidates_only"),
    lambda g:g.update(native_candidate_ring_count=1),
    lambda g:g.update(interior_stroke_intersections_and_overlaps=("crossing",)),
    lambda g:g.update(original_native_edge_ids=IDS[:-1]),
    lambda g:g.update(original_native_edge_ids=IDS+("bottom",)),
    lambda g:g["native_components"][0].update(
        source_branch_coordinates_pdf_pts=((40.,100.),),
    ),
    lambda g:g["native_components"][0].update(
        source_open_endpoint_coordinates_pdf_pts=((40.,100.),),
    ),
    lambda g:g["native_components"][0].update(
        source_simple_ring_candidate={"vertices_pdf_pts":POLY},
    ),
    lambda g:g["original_native_edges"][2].update(
        endpoints_pdf_pts=((100.,0.),(99.76,100.)),
    ),
    lambda g:g["original_native_edges"][2].update(
        source_id="foreign-edge",
    ),
    lambda g:g["original_native_edges"][2].update(
        endpoints_pdf_pts=((100.,0.),(True,100.)),
    ),
])
def test_wrong_or_repaired_original_open_source_graph_never_authorizes_chord(
    mutation,
):
    graph=original_open_graph()
    mutation(graph)
    result=source_result(graph)
    assert result["status"]=="source_open_floor_wall_ink_or_gap_unverified"
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("poly",[
    ((0.,0.),(100.,0.),(100.,99.76),(0.,100.)),
    ((0.,0.),(100.,0.),(100.,100.),(0.,100.),(40.,100.),(60.,100.)),
    ((0.,0.),(100.,0.),(100.,100.),(0.,100.),(0.,100.)),
    ((0.,0.),(100.,0.),(100.,100.),(0.,100.),(float("inf"),10.)),
    (),
    None,
])
def test_virtually_closed_floor_must_match_exact_original_wall_ink_except_gap(
    poly,
):
    result=source_result(polygon=poly)
    assert result["status"]=="source_open_floor_wall_ink_or_gap_unverified"
    assert result["new_firm_quantities"]==0
