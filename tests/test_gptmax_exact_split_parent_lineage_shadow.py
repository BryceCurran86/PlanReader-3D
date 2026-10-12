"""Actual splitter ancestry is retained only in explicit nonpublishing shadow."""
from copy import deepcopy
import math

import pytest

from pb_accuracy_v13_engines_v145 import split_segments_at_intersections
from pb_wall_room_topology_primitive_lineage import attach_lineage_to_split_fragments
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport, _point_pairs_to_segment_dicts
from tools.diag_gptmax_full_foreground_run_source import _trace_sources
from test_gptmax_exact_endpoint_flank_shadow import record


def _sources():
    return [dict(id='axis',x1=0.,y1=0.,x2=20.,y2=0.),
            dict(id='cross-a',x1=8.,y1=-3.,x2=8.,y2=3.),
            dict(id='cross-b',x1=8.000003,y1=-3.,x2=8.000003,y2=3.)]


def _split(sources):
    indexes=[]
    pairs=split_segments_at_intersections([((s['x1'],s['y1']),(s['x2'],s['y2'])) for s in sources],source_parent_indexes=indexes)
    return pairs,indexes


def test_splitter_default_geometry_and_shadow_emitter_are_exact_no_mutation():
    sources=_sources(); original=deepcopy(sources); pairs,indexes=_split(sources)
    assert pairs==split_segments_at_intersections([((s['x1'],s['y1']),(s['x2'],s['y2'])) for s in sources])
    assert len(indexes)==len(pairs)
    ordinary=attach_lineage_to_split_fragments(pairs,sources)
    shadow=attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes)
    tiny=[(a,b,i) for a,b,i in zip(ordinary,shadow,indexes) if math.hypot(a['x2']-a['x1'],a['y2']-a['y1'])<=1e-5]
    assert tiny
    for a,b,i in tiny:
        assert a['primitive_lineage']['source_primitive_ids']==[]
        assert b['primitive_lineage']['source_primitive_ids']==[sources[i]['id']]
    assert sources==original
    assert [{k:v for k,v in e.items() if k!='primitive_lineage'} for e in ordinary]==[
        {k:v for k,v in e.items() if k!='primitive_lineage'} for e in shadow]


def test_overlapping_plural_parents_are_never_narrowed_to_emitter():
    sources=[dict(id='a',x1=0.,y1=0.,x2=10.,y2=0.),dict(id='b',x1=0.,y1=0.,x2=10.,y2=0.)]
    pairs,indexes=_split(sources)
    rows=attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes)
    assert all(r['primitive_lineage']['source_primitive_ids']==['a','b'] for r in rows)


@pytest.mark.parametrize('bad',[True,-1,999,'0'])
def test_corrupt_split_emitter_indexes_fail_closed(bad):
    sources=_sources();pairs,indexes=_split(sources); indexes[0]=bad
    with pytest.raises(ValueError,match='parent inventory'):
        attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes)


def test_distant_source_cannot_inherit_tiny_fragment_by_fake_origin():
    sources=_sources()+[dict(id='remote',x1=50.,y1=50.,x2=60.,y2=50.)]
    pairs,indexes=_split(sources);indexes[0]=3
    with pytest.raises(ValueError,match='contradicts'):
        attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes)


def test_length_or_output_inventory_mismatch_is_not_repaired():
    sources=_sources();pairs,indexes=_split(sources)
    with pytest.raises(ValueError,match='parent inventory'):
        attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes[:-1])
    with pytest.raises(ValueError,match='empty list'):
        split_segments_at_intersections([((0.,0.),(10.,0.))],source_parent_indexes=[0])


def test_shadow_graph_keeps_exact_topology_and_default_replay():
    sources=_sources();original=deepcopy(sources)
    ordinary=build_wall_graph_for_viewport(sources,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True)
    shadow=build_wall_graph_for_viewport(sources,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True,exact_split_parent_lineage_shadow=True)
    def topology(g):
        x=deepcopy(g)
        for row in [*x['edges'],*x['snap_collapsed_fragments']]:row.pop('primitive_lineage',None)
        return x
    assert topology(ordinary)==topology(shadow)
    assert ordinary==build_wall_graph_for_viewport(sources,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True)
    assert sources==original


def test_rotation_translation_source_order_and_unrelated_content_keep_emitter_ancestry():
    for quarter_turn in range(4):
        def transform(x,y):
            for _ in range(quarter_turn):x,y=-y,x
            return x+100.,y-70.
        sources=[]
        for s in reversed(_sources()):
            x1,y1=transform(s['x1'],s['y1']);x2,y2=transform(s['x2'],s['y2'])
            sources.append(dict(s,x1=x1,y1=y1,x2=x2,y2=y2))
        sources.append(dict(id='remote',x1=500.,y1=500.,x2=520.,y2=500.))
        pairs,indexes=_split(sources)
        rows=attach_lineage_to_split_fragments(pairs,sources,source_parent_indexes=indexes)
        for row,i in zip(rows,indexes):
            assert sources[i]['id'] in row['primitive_lineage']['source_primitive_ids']
        assert any(math.hypot(r['x2']-r['x1'],r['y2']-r['y1'])<=1e-5 and
                   r['primitive_lineage']['source_primitive_ids']==['axis'] for r in rows)


def test_w4_guard_and_negative_publication_survive_shadow_parent_capture():
    records=(record('a',[0.,0.,10.,0.]),record('b',[10.,0.,4e-8,0.]))
    with pytest.raises(ValueError,match='cannot start and end'):
        _trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,exact_split_parent_lineage_shadow=True)
    out=_trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,w4_identity_abstention_shadow=True,exact_split_parent_lineage_shadow=True)
    assert out['all_w4_abstained_chain_rows']
    assert out['host_publication_allowed'] is False and out['physical_equivalence_proven'] is False


def test_shadow_mode_cannot_be_enabled_with_a_truthy_non_boolean():
    with pytest.raises(ValueError,match='explicit boolean'):
        build_wall_graph_for_viewport(_sources(),exact_split_parent_lineage_shadow=1)
    with pytest.raises(ValueError,match='require original source'):
        _point_pairs_to_segment_dicts([((0.,0.),(10.,0.))],source_parent_indexes=[0])
