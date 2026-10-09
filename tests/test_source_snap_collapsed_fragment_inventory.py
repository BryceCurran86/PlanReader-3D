"""Collapsed source fragments remain typed negatives, never continuity proof."""
from copy import deepcopy
from types import SimpleNamespace
import math

import pytest

from pb_physical_wall_candidate_authority import _source_snap_collapsed_fragment_inventory
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY, SNAP_COLLAPSE_REASON
from pb_raster_source_wall_frame_projection import source_edge_axis_projection


def _fixture():
    def edge(key, start, end, a, b):
        return dict(id=key, x1=start, y1=5., x2=end, y2=5., a=a, b=b,
                    **{LINEAGE_KEY: {'source_primitive_ids': ['source']}})
    gap = edge('collapsed', 0., 2., 1, 1)
    gap['reason'] = SNAP_COLLAPSE_REASON
    graph = dict(edges=[edge('left', -10., 0., 0, 1), edge('right', 2., 15., 1, 2)],
                 snap_collapsed_fragments=[gap])
    identity = SimpleNamespace(usable=True, edge_ids=('left', 'right'),
                               source_primitive_ids=('source',))
    return graph, {'wall': identity}


def test_exact_source_negative_is_retained_without_mutating_graph_or_identity():
    graph, identities = _fixture()
    before = repr((graph, identities))
    receipt, = _source_snap_collapsed_fragment_inventory(graph, identities)['wall']
    assert receipt.edge_id == 'collapsed'
    assert receipt.geometry == (0., 5., 2., 5.)
    assert receipt.source_primitive_ids == ('source',)
    assert receipt.reason_code == SNAP_COLLAPSE_REASON
    assert repr((graph, identities)) == before
    graph['edges'].reverse()
    assert _source_snap_collapsed_fragment_inventory(graph, identities) == {'wall': (receipt,)}


@pytest.mark.parametrize('damage', ['remote', 'different_node', 'other_parent', 'missing_parent',
    'different_owner', 'multiple_owners', 'unusable', 'wrong_reason', 'duplicate_id', 'nan'])
def test_unowned_or_ambiguous_collapsed_source_never_attaches_to_a_candidate(damage):
    graph, identities = _fixture()
    right = graph['edges'][1]
    gap = graph['snap_collapsed_fragments'][0]
    if damage == 'remote': right['x1'] = 2.01
    elif damage == 'different_node': right['a'] = 3
    elif damage == 'other_parent': right[LINEAGE_KEY]['source_primitive_ids'] = ['other']
    elif damage == 'missing_parent': identities['wall'].source_primitive_ids = ('other',)
    elif damage == 'different_owner': identities['wall'].edge_ids = ('left',)
    elif damage == 'multiple_owners': identities['other_wall'] = deepcopy(identities['wall'])
    elif damage == 'unusable': identities['wall'].usable = False
    elif damage == 'wrong_reason': gap['reason'] = 'missing'
    elif damage == 'duplicate_id': graph['snap_collapsed_fragments'].append(deepcopy(gap))
    elif damage == 'nan': gap['x1'] = math.nan
    assert _source_snap_collapsed_fragment_inventory(graph, identities) == {}


@pytest.mark.parametrize('theta,scale,dx,dy', [(0.,1.,30.,-7.), (.8,2.,-8.,13.), (1.57,.5,0.,0.)])
def test_source_coordinates_survive_rotation_translation_and_scale(theta,scale,dx,dy):
    graph, identities = _fixture()
    c,s = math.cos(theta),math.sin(theta)
    def point(x,y): return scale*(x*c-y*s)+dx,scale*(x*s+y*c)+dy
    for edge in [*graph['edges'], *graph['snap_collapsed_fragments']]:
        edge['x1'],edge['y1'] = point(edge['x1'],edge['y1'])
        edge['x2'],edge['y2'] = point(edge['x2'],edge['y2'])
    receipt, = _source_snap_collapsed_fragment_inventory(graph, identities)['wall']
    assert receipt.geometry == pytest.approx((*point(0.,5.),*point(2.,5.)))


def test_negative_sidecar_cannot_bridge_source_projection_gap():
    from test_raster_source_wall_frame_projection import _fixture as projection_fixture
    record, geometry, lines = projection_fixture()
    from dataclasses import replace
    a,b = record.source_edge_fragments
    record.source_edge_fragments = (a,replace(b,geometry=(2.,5.,15.,5.)))
    graph, identities = _fixture()
    record.source_snap_collapsed_fragments = _source_snap_collapsed_fragment_inventory(graph, identities)['wall']
    assert source_edge_axis_projection(record, geometry, lines) is None


def test_real_w2_collapse_retains_exact_source_interval_without_graph_repair():
    from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
    def line(key,x1,y1,x2,y2):
        return dict(id=key,x1=x1,y1=y1,x2=x2,y2=y2,kind='line',layer='Structural Bearing')
    graph = build_wall_graph_for_viewport([
        line('source',0.,0.,30.,0.),
        line('junction_a',10.,-10.,10.,10.),
        line('junction_b',12.,-10.,12.,10.)])
    collapsed = [f for f in graph['snap_collapsed_fragments']
                 if f[LINEAGE_KEY]['source_primitive_ids']==['source']]
    assert len(collapsed)==1
    source_edges = tuple(str(e['id']) for e in graph['edges']
                         if e[LINEAGE_KEY]['source_primitive_ids']==['source'])
    identities = {'wall': SimpleNamespace(usable=True,edge_ids=source_edges,
                                          source_primitive_ids=('source',))}
    before = deepcopy(graph)
    receipt, = _source_snap_collapsed_fragment_inventory(graph,identities)['wall']
    assert receipt.geometry == (10.,0.,12.,0.)
    assert receipt.edge_id == str(collapsed[0]['id'])
    assert graph == before
    assert receipt.edge_id not in source_edges
