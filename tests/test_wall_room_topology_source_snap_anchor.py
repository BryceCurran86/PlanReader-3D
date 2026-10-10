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
        _edge("true-compact-T",1,3,p,(410.25,342.72),"raster_segment:sourceimage:terminal_solid_wall_band_v1:registeredpaint:0",(p,(410.25,342.72))),
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
        g["edges"][1]["x2"]=381.5
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



@pytest.mark.parametrize("damage", [
    "ordinary_t","native_t","unknown_raster_producer","supplement_parent_missing",
    "supplement_two_parents","supplement_record_unproved","supplement_parent_remote",
    "supplement_near_end","supplement_wrong_end","supplement_not_perpendicular",
])
def test_only_exact_positive_producer_owned_supplemental_t_can_reanchor(damage):
    g=_graph()
    branch=g["edges"][2]
    payload=branch["primitive_lineage"]
    if damage=="ordinary_t":
        payload["source_primitive_ids"]=["raster_segment:sourceimage:1.0.0:12"]
        payload["source_records"][0]["id"]=payload["source_primitive_ids"][0]
    elif damage=="native_t":
        payload["source_primitive_ids"]=["segment:source:12"]
        payload["source_records"][0]["id"]=payload["source_primitive_ids"][0]
    elif damage=="unknown_raster_producer":
        payload["source_primitive_ids"]=["raster_segment:sourceimage:not_a_supplemental_line:12"]
        payload["source_records"][0]["id"]=payload["source_primitive_ids"][0]
    elif damage=="supplement_parent_missing":
        payload["source_records"]=[]
    elif damage=="supplement_two_parents":
        payload["source_primitive_ids"].append("other")
    elif damage=="supplement_record_unproved":
        payload["source_records"][0]["page_coords_present"]=False
    elif damage=="supplement_parent_remote":
        payload["source_records"][0]["x1"]+=10.
        payload["source_records"][0]["x2"]+=10.
    elif damage=="supplement_near_end":
        payload["source_records"][0]["x1"]+=.01
    elif damage=="supplement_wrong_end":
        payload["source_records"][0]["x1"]=376.
        payload["source_records"][0]["x2"]=412.
    else:
        # A positive but diagonal source branch does not establish a
        # perpendicular through/junction correction.
        branch["y2"]+=.75
        payload["source_records"][0]["y2"]+=.75
    before=deepcopy(g)
    after=reanchor(g,tolerance_pt=2.5)
    assert not after["exact_source_through_junction_anchors"]
    assert after["nodes"]==before["nodes"]
    assert after["edges"]==before["edges"]


def test_first_party_compact_namespace_can_prove_exact_positive_t_without_guessing():
    g=_graph()
    p=g["edges"][2]["primitive_lineage"]
    p["source_primitive_ids"]=[
        "raster_segment:sourceimage:compact_solid_wall_band_v1:registeredpaint:0"
    ]
    p["source_records"][0]["id"]=p["source_primitive_ids"][0]
    after=reanchor(g,tolerance_pt=2.5)
    assert after["nodes"][1]["x"]==381.
    assert len(after["exact_source_through_junction_anchors"])==1


def test_real_registered_terminal_source_short_overhang_retains_original_through_node():
    g=_graph()
    branch=g["edges"][2]["primitive_lineage"]["source_records"][0]
    # Exact original raster record in the failed real Lot16 source run:
    # split piece starts at (381,342.72), but the independently registered
    # painted parent line extends back to (379.2,342.72).
    branch["x1"]=379.2
    branch["x2"]=411.6
    before=deepcopy(g)
    out=reanchor(g,tolerance_pt=2.5)
    assert out["nodes"][1]["x"]==381.
    assert out["nodes"][1]["y"]==342.72
    assert len(out["exact_source_through_junction_anchors"])==1
    assert g==before
    assert out["edges"]==before["edges"]


def test_registered_parent_overhang_cannot_exceed_existing_snap_footprint():
    g=_graph()
    branch=g["edges"][2]["primitive_lineage"]["source_records"][0]
    branch["x1"]=377.2
    branch["x2"]=411.6
    out=reanchor(g,tolerance_pt=2.5)
    assert out["nodes"][1]["x"]==380.64
    assert not out["exact_source_through_junction_anchors"]


def test_real_full_crossing_stays_unmodified_even_if_paint_overhang_is_short():
    g=_graph()
    # Both independently observed opposite fragments share the same
    # supplemental parent: genuine source crossing is not a terminal T.
    source_id=g["edges"][2]["primitive_lineage"]["source_primitive_ids"][0]
    extra=_edge(
        "terminal-overhang-opposite",1,4,(381.,342.72),(379.2,342.72),
        source_id,((379.2,342.72),(411.6,342.72)),
    )
    g["edges"][2]["primitive_lineage"]["source_records"][0]["x1"]=379.2
    g["edges"][2]["primitive_lineage"]["source_records"][0]["x2"]=411.6
    g["edges"].append(extra)
    g["adjacency"][1].append(3)
    g["adjacency"][4]=[3]
    g["nodes"].append({"id":4,"x":379.2,"y":342.72,"degree":1})
    g["nodes"][1]["degree"]=4
    out=reanchor(g,tolerance_pt=2.5)
    assert not out["exact_source_through_junction_anchors"]
    assert out["nodes"][1]["x"]==380.64
