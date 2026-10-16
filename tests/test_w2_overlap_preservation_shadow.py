"""Same-side source intervals must not cancel during an opt-in W2 merge."""
from copy import deepcopy
import math
import random

import pytest

from pb_wall_room_topology_stage_a import (
    _has_opposing_endpoint_rays, _merge_collinear_degree_two_nodes_indexed,
    _snap_geometry_indexed, build_wall_graph_for_viewport,
    merge_collinear_degree_two_nodes,
)


def segment(identity, a, b):
    return dict(id=identity, x1=a[0], y1=a[1], x2=b[0], y2=b[1], kind="line")


def prepared(rows):
    return _snap_geometry_indexed(rows, tolerance_pt=0., exact_endpoint_index_shadow=True)


def geometry(graph):
    return sorted(tuple(sorted(((e["x1"],e["y1"]),(e["x2"],e["y2"])))) for e in graph["edges"])


def test_same_side_original_overlap_is_preserved_instead_of_far_end_chord():
    rows=[segment("long",(0.,0.),(0.,24.5)),segment("short",(0.,0.),(0.,24.))]
    graph=prepared(rows)
    before=deepcopy(graph)
    legacy=_merge_collinear_degree_two_nodes_indexed(graph)
    assert geometry(legacy)==[((0.,24.),(0.,24.5))]
    for merge in (merge_collinear_degree_two_nodes,_merge_collinear_degree_two_nodes_indexed):
        guarded=merge(graph,preserve_overlapping_spans_shadow=True)
        assert geometry(guarded)==geometry(graph)
        assert len(guarded["edges"])==2
        assert not any(n.get("merged_into_edge") for n in guarded["nodes"])
    assert graph==before


def test_genuine_opposite_ray_join_remains_unchanged():
    graph=prepared([segment("a",(0.,0.),(12.,0.)),segment("b",(0.,0.),(-10.,0.))])
    a=_merge_collinear_degree_two_nodes_indexed(graph)
    b=_merge_collinear_degree_two_nodes_indexed(graph,preserve_overlapping_spans_shadow=True)
    assert a==b
    assert geometry(b)==[((-10.,0.),(12.,0.))]


@pytest.mark.parametrize("angle", [0.,37.,90.,211.])
@pytest.mark.parametrize("scale", [.25,1.,9.])
def test_rotation_translation_scale_and_input_reversal_preserve_all_source_spans(angle,scale):
    theta=math.radians(angle)
    def p(x):return (scale*x*math.cos(theta)+17.,scale*x*math.sin(theta)-31.)
    rows=[segment("a",p(0.),p(24.)),segment("b",p(0.),p(24.5))]
    for ordered in (rows,list(reversed(rows))):
        g=build_wall_graph_for_viewport(ordered,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True,
            exact_split_parent_lineage_shadow=True,preserve_overlapping_spans_shadow=True)
        for original in ordered:
            sid=original["id"]
            es=[e for e in g["edges"] if sid in e["primitive_lineage"]["source_primitive_ids"]]
            assert es
            # No far-end-only chord may be substituted for either full parent.
            assert max(e["length_pt"] for e in es)==pytest.approx((24. if sid=="a" else 24.5)*scale)
    assert rows==[segment("a",p(0.),p(24.)),segment("b",p(0.),p(24.5))]


def test_true_gap_corner_and_overtraced_pair_do_not_gain_new_geometry():
    for rows in (
        [segment("a",(0.,0.),(10.,0.)),segment("b",(10.1,0.),(20.,0.))],
        [segment("a",(0.,0.),(10.,0.)),segment("b",(0.,0.),(0.,10.))],
        [segment("a",(0.,0.),(10.,0.)),segment("b",(0.,0.),(10.,0.))],
    ):
        graph=prepared(rows)
        out=_merge_collinear_degree_two_nodes_indexed(graph,preserve_overlapping_spans_shadow=True)
        assert geometry(out)==geometry(graph)
        assert [e['id'] for e in out['edges']]==[e['id'] for e in graph['edges']]


def test_splitting_and_unrelated_content_conserve_original_parent_intervals():
    for split in (False,True):
        rows=[segment("a",(0.,0.),(24.5,0.))]
        rows += ([segment("b1",(0.,0.),(12.,0.)),segment("b2",(12.,0.),(24.,0.))]
                 if split else [segment("b",(0.,0.),(24.,0.))])
        rows.append(segment("remote",(100.,100.),(120.,100.)))
        g=build_wall_graph_for_viewport(rows,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True,
            preserve_overlapping_spans_shadow=True,exact_split_parent_lineage_shadow=True)
        assert any(e["x1"]==0. and e["x2"]==24.5 for e in g["edges"])
        assert any(e["x1"]==100. and e["x2"]==120. for e in g["edges"])


def test_indexed_and_reference_guard_have_identical_deterministic_results():
    rng=random.Random(47)
    for _ in range(30):
        rows=[]
        for i in range(8):
            origin=float(i*100)
            lengths=(rng.randrange(5,30),rng.randrange(31,50))
            for j,length in enumerate(lengths):
                sign=-1 if i%2 and j else 1
                rows.append(segment(f"{i}-{j}",(origin,0.),(origin+sign*length,0.)))
        rng.shuffle(rows)
        graph=prepared(rows)
        a=merge_collinear_degree_two_nodes(graph,preserve_overlapping_spans_shadow=True)
        b=_merge_collinear_degree_two_nodes_indexed(graph,preserve_overlapping_spans_shadow=True)
        assert a==b
        assert b==_merge_collinear_degree_two_nodes_indexed(graph,preserve_overlapping_spans_shadow=True)


@pytest.mark.parametrize("bad", [1,0,None,"true",[]])
def test_opt_in_is_never_inferred(bad):
    for merge in (merge_collinear_degree_two_nodes,_merge_collinear_degree_two_nodes_indexed):
        with pytest.raises(ValueError,match="explicit boolean"):
            merge(prepared([]),preserve_overlapping_spans_shadow=bad)
    with pytest.raises(ValueError,match="explicit boolean"):
        build_wall_graph_for_viewport([],preserve_overlapping_spans_shadow=bad)


def test_nonfinite_or_degenerate_endpoint_vectors_cannot_authorize_a_merge():
    node={"x":0.,"y":0.}
    for bad in (0.,float("inf"),float("nan")):
        assert not _has_opposing_endpoint_rays(node,{"x":bad,"y":0.},{"x":-1.,"y":0.})


def test_default_graph_is_exactly_unchanged():
    rows=[segment("a",(0.,0.),(24.5,0.)),segment("b",(0.,0.),(24.,0.))]
    assert build_wall_graph_for_viewport(rows)==build_wall_graph_for_viewport(rows,preserve_overlapping_spans_shadow=False)
