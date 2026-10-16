"""Zero-mode source equality must not be replaced by running-mean arithmetic."""
from copy import deepcopy
import math

import pytest

from pb_wall_room_topology_stage_a import _snap_geometry_indexed, build_wall_graph_for_viewport
from tests.test_w2_overlap_preservation_shadow import segment


def immutable(rows):
    return _snap_geometry_indexed(rows,tolerance_pt=0.,exact_endpoint_index_shadow=True,
                                 immutable_exact_endpoints_shadow=True)


@pytest.mark.parametrize("point", [(0.1,0.3),(737.76,426.24),(-0.1,-0.3),(1e308,1e308),(5e-324,-5e-324)])
def test_repeated_exact_source_point_retains_one_unchanged_node(point):
    rows=[segment(str(i),point,(float(i+10),float(-i-10))) for i in range(15)]
    before=deepcopy(rows)
    out=immutable(rows)
    assert len({e['a'] for e in out['edges']})==1
    node=out['nodes'][out['edges'][0]['a']]
    assert (node['x'],node['y'])==point and node['samples']==15
    assert rows==before
    assert immutable(rows)==out


def test_historical_exact_mode_keeps_its_original_arithmetic():
    rows=[segment(str(i),(0.1,0.3),(float(i+10),10.)) for i in range(8)]
    old=_snap_geometry_indexed(rows,tolerance_pt=0.,exact_endpoint_index_shadow=True)
    off=_snap_geometry_indexed(rows,tolerance_pt=0.,exact_endpoint_index_shadow=True,
                               immutable_exact_endpoints_shadow=False)
    assert old==off
    assert len({e['a'] for e in old['edges']})>1
    assert len({e['a'] for e in immutable(rows)['edges']})==1


def test_true_one_ulp_source_gap_is_not_rounded_or_elected():
    a=(.1,.3); b=(math.nextafter(.1,math.inf),.3)
    rows=[segment('a',a,(10.,0.)),segment('b',b,(20.,0.))]
    g=immutable(rows)
    assert g['edges'][0]['a']!=g['edges'][1]['a']
    assert len(g['nodes'])==4


@pytest.mark.parametrize("angle,scale,offset", [(0.,1.,(0.,0.)),(.7,3.,(101.,-207.)),(2.3,.125,(-19.,83.))])
def test_transformed_shared_source_vertices_keep_incidence(angle,scale,offset):
    def transform(p):
        x,y=p; c,s=math.cos(angle),math.sin(angle)
        return (offset[0]+scale*(c*x-s*y),offset[1]+scale*(s*x+c*y))
    shared=transform((.1,.3))
    rows=[segment(str(i),shared,transform(p)) for i,p in enumerate(
        [(-10.,.3),(10.,.3),(.1,-10.),(.1,10.)])]
    before=deepcopy(rows)
    for ordered in (rows,list(reversed(rows))):
        g=immutable(ordered)
        nodes=[n for n in g['nodes'] if (n['x'],n['y'])==shared]
        assert len(nodes)==1 and nodes[0]['degree']==4 and nodes[0]['samples']==4
    assert rows==before


@pytest.mark.parametrize("order", [False,True])
def test_source_splitting_and_unrelated_lines_keep_shared_vertex_incidence(order):
    c=(.1,.3)
    rows=[segment('left',(-10.,.3),c),segment('right',c,(10.,.3)),
          segment('down',c,(.1,10.)),segment('up',(.1,-10.),c),
          segment('remote',(100.,100.),(110.,100.))]
    if order:rows.reverse()
    g=immutable(rows)
    shared=[n for n in g['nodes'] if (n['x'],n['y'])==c]
    assert len(shared)==1 and shared[0]['degree']==4
    assert len(g['edges'])==5


@pytest.mark.parametrize("bad", [1,0,None,"true",[]])
def test_explicit_shadow_boolean_required(bad):
    with pytest.raises(ValueError,match='explicit boolean'):
        _snap_geometry_indexed([],tolerance_pt=0.,exact_endpoint_index_shadow=True,
                               immutable_exact_endpoints_shadow=bad)
    with pytest.raises(ValueError,match='explicit boolean'):
        build_wall_graph_for_viewport([],immutable_exact_endpoints_shadow=bad)


@pytest.mark.parametrize("tolerance,indexed", [(2.5,False),(0.,False),(2.5,True),(-1.,True)])
def test_no_changed_tolerance_or_implicit_mode_can_enable_immutable_vertices(tolerance,indexed):
    with pytest.raises(ValueError,match='indexed zero tolerance'):
        _snap_geometry_indexed([],tolerance_pt=tolerance,exact_endpoint_index_shadow=indexed,
                               immutable_exact_endpoints_shadow=True)


@pytest.mark.parametrize("bad", [float('inf'),float('-inf'),float('nan')])
def test_unknown_source_geometry_does_not_fall_back_to_legacy(bad):
    with pytest.raises(ValueError,match='must be finite'):
        immutable([segment('bad',(bad,0.),(1.,1.))])
