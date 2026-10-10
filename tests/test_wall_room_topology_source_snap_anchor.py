"""W2 exact original-source junction anchoring: preserve true T, reject guesses."""
from copy import deepcopy
from math import nan

import pytest

from pb_wall_room_topology_source_snap_anchor import (
    reanchor_exact_source_through_junctions as reanchor,
)


def _lineage(parent, p, q):
    return {
        "source_primitive_ids": [parent],
        "source_records": [{
            "id": parent, "x1": p[0], "y1": p[1],
            "x2": q[0], "y2": q[1], "page_coords_present": True,
        }],
    }


def _edge(name, a, b, p, q, parent, extent):
    return {"id": name, "a": a, "b": b,
            "x1": p[0], "y1": p[1],
            "x2": q[0], "y2": q[1],
            "primitive_lineage": _lineage(parent, *extent)}


def _graph():
    # Actual W2 source-owned line coordinates from original Lot16 compact
    # experiment, independent of the benchmark object universe.
    p=(381.,342.72)
    edges=[
        _edge("ordinary-upper",0,1,(381.,338.75),p,"ordinary-1567",((381.,297.),(381.,349.))),
        _edge("ordinary-lower",1,2,p,(381.,349.),"ordinary-1567",((381.,297.),(381.,349.))),
        _edge("true-compact-T",1,3,p,(410.25,342.72),"compact-T",(p,(410.25,342.72))),
    ]
    nodes=[
        {"id":0,"x":381.,"y":338.75,"degree":1},
        {"id":1,"x":380.64,"y":342.72,"degree":3},
        {"id":2,"x":381.,"y":349.,"degree":1},
        {"id":3,"x":410.25,"y":342.72,"degree":1},
    ]
    return {"nodes":nodes,"edges":edges,"adjacency":{0:[0],1:[0,1,2],2:[1],3:[2]}}


def test_positive_exact_source_vertical_spine_reanchors_without_discarding_t():
    g=_graph()
    before=deepcopy(g)
    out=reanchor(g,tolerance_pt=2.5)
    assert out["nodes"][1]["x"] == 381.
    assert out["nodes"][1]["y"] == 342.72
    assert out["nodes"][1]["degree"] == 3
    assert out["exact_source_through_junction_anchors"][0]["node_id"]==1
    assert out["edges"] == before["edges"]
    assert out["adjacency"] == before["adjacency"]
    assert g == before


@pytest.mark.parametrize("damage", [
    "missing_lineage","different_parent","missing_record",
    "no_source_authority","source_ends_at_t","wrong_parent_line",
    "bent_upper","not_through","other_endpoint_far",
    "nan_node","no_snap_scope",
])
def test_ambiguous_or_unproven_through_geometry_preserves_original_graph(damage):
    g=_graph()
    if damage=="missing_lineage":
        g["edges"][0]["primitive_lineage"]["source_primitive_ids"]=[]
    elif damage=="different_parent":
        g["edges"][1]["primitive_lineage"]["source_primitive_ids"]=["other"]
    elif damage=="missing_record":
        g["edges"][0]["primitive_lineage"]["source_records"]=[]
    elif damage=="no_source_authority":
        g["edges"][0]["primitive_lineage"]["source_records"][0]["page_coords_present"]=False
    elif damage=="source_ends_at_t":
        g["edges"][0]["primitive_lineage"]["source_records"][0]["y2"]=342.72
    elif damage=="wrong_parent_line":
        g["edges"][0]["primitive_lineage"]["source_records"][0]["x1"]=380.
    elif damage=="bent_upper":
        g["edges"][0]["x1"]=380.8
    elif damage=="not_through":
        g["edges"][1]["y2"]=342.74
    elif damage=="other_endpoint_far":
        g["edges"][2]["x1"]=375.
    elif damage=="nan_node":
        g["nodes"][1]["x"]=nan
    else:
        g["nodes"][1]["x"]=375.
    before=deepcopy(g)
    out=reanchor(g,tolerance_pt=2.5)
    assert out["edges"] == before["edges"]
    assert out["adjacency"] == before["adjacency"]
    assert not out["exact_source_through_junction_anchors"]
    if damage != "nan_node":
        assert out["nodes"] == before["nodes"]


def test_without_perpendicular_t_no_three_way_junction_is_modified():
    g=_graph()
    g["nodes"][1]["degree"]=2
    g["adjacency"][1]=[0,1]
    assert not reanchor(g,tolerance_pt=2.5)["exact_source_through_junction_anchors"]


def test_exact_source_anchor_is_never_new_source_gap_witness():
    g=_graph()
    # Distinct unproven local interval remains 336.75..338.75. The positive
    # local T junction at 342.72 is within the exact lower source fragment.
    out=reanchor(g,tolerance_pt=2.5)
    assert g["edges"][0]["y1"]==338.75
    assert out["nodes"][1]["y"]==342.72
    assert not any("source_gap_proven" in str(v) for v in out.values())


def test_zero_or_invalid_existing_snap_tolerance_cannot_expand_geometry():
    g=_graph()
    assert reanchor(g,tolerance_pt=0) is g
    for bad in (nan,):
        with pytest.raises(ValueError):
            reanchor(g,tolerance_pt=bad)
